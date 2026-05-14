import datetime as dt

import pytest
from fastapi import BackgroundTasks, HTTPException

import routes.auth as auth

from routes.auth import (
    FinalizePasswordResetRequest,
    LoginRequest,
    RegisterRequest,
    VerifyResetOtpRequest,
    _json_safe_user,
    _json_safe_value,
    _post_registration_sync,
    _warm_cycle_state_on_login,
    check_email,
    delete_account,
    finalize_password_reset,
    get_current_user,
    get_me,
    login,
    logout,
    _merge_login_user_compliance_fields,
    _validate_password_reset_strength,
    register,
    update_fcm_token,
    verify_reset_otp,
    authenticated_subject_id,
)


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def insert(self, *_args, **_kwargs):
        return self

    def update(self, *_args, **_kwargs):
        return self

    def delete(self, *_args, **_kwargs):
        return self

    def execute(self):
        return type("Resp", (), {"data": self._data})()


class FakeClient:
    def __init__(self, table_map):
        self.table_map = table_map

    def table(self, name):
        return FakeQuery(self.table_map.get(name, []))


def test_json_safe_value_converts_nested_dates_and_datetimes():
    payload = {
        "created": dt.datetime(2026, 5, 1, 10, 30, 0),
        "period_start": dt.date(2026, 5, 1),
        "nested": [{"at": dt.datetime(2026, 5, 2, 9, 0, 0)}],
        "name": "A",
    }
    safe = _json_safe_value(payload)

    assert safe["created"] == "2026-05-01T10:30:00"
    assert safe["period_start"] == "2026-05-01"
    assert safe["nested"][0]["at"] == "2026-05-02T09:00:00"
    assert safe["name"] == "A"


def test_json_safe_user_returns_copy_and_serializes_values():
    user = {
        "id": "u-1",
        "last_period_date": dt.date(2026, 5, 1),
    }
    safe = _json_safe_user(user)

    assert safe["last_period_date"] == "2026-05-01"
    assert user["last_period_date"] == dt.date(2026, 5, 1)
    assert safe is not user


@pytest.mark.parametrize(
    "password",
    [
        "Password1",
        "abcdefgh!",
        "abcdEFGH",
        "A2345678",
    ],
)
def test_validate_password_reset_strength_accepts_strong_passwords(password):
    _validate_password_reset_strength(password)


@pytest.mark.parametrize("password", ["short1A", "abcdefgh", "lowercaseonly"])
def test_validate_password_reset_strength_rejects_weak_passwords(password):
    with pytest.raises(HTTPException) as exc:
        _validate_password_reset_strength(password)
    assert exc.value.status_code == 422


def test_merge_login_user_compliance_fields_sets_defaults_only_when_missing():
    user = {
        "id": "u-1",
        "consent_accepted": None,
        "consent_language": "en",
    }
    _merge_login_user_compliance_fields(user)

    assert user["consent_accepted"] is False
    assert user["consent_language"] == "en"
    assert "consent_timestamp" in user and user["consent_timestamp"] is None
    assert "privacy_policy_version" in user and user["privacy_policy_version"] is None


def test_authenticated_subject_id_returns_trimmed_id():
    assert authenticated_subject_id({"id": "  abc-123  "}) == "abc-123"


@pytest.mark.parametrize("bad_user", [{}, {"id": None}, {"id": ""}, {"id": "   "}])
def test_authenticated_subject_id_rejects_missing_or_blank_id(bad_user):
    with pytest.raises(HTTPException) as exc:
        authenticated_subject_id(bad_user)
    assert exc.value.status_code == 401


def test_post_registration_sync_calls_both_sync_steps(monkeypatch):
    called = {}
    import period_start_logs
    import cycle_stats

    monkeypatch.setattr(period_start_logs, "sync_period_start_logs_from_period_logs", lambda uid, **_k: [{"id": uid}])
    monkeypatch.setattr(cycle_stats, "update_user_cycle_stats", lambda uid, period_starts=None: called.update(uid=uid, starts=period_starts))
    _post_registration_sync("u-1")
    assert called["uid"] == "u-1"
    assert called["starts"] == [{"id": "u-1"}]


def test_warm_cycle_state_on_login_is_non_fatal(monkeypatch):
    import cycle_utils

    monkeypatch.setattr(auth, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycle_utils, "calculate_phase_for_date_range", lambda **_k: [{"date": "2026-05-01"}])
    _warm_cycle_state_on_login({"id": "u-1", "cycle_length": "bad", "avg_bleeding_days": 99})


@pytest.mark.asyncio
async def test_check_email_reports_available(monkeypatch):
    monkeypatch.setattr(auth, "supabase", FakeClient({"users": []}))
    result = await check_email("test@example.com")
    assert result["available"] is True


@pytest.mark.asyncio
async def test_check_email_rejects_empty():
    with pytest.raises(HTTPException) as exc:
        await check_email("   ")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_get_current_user_valid_token_returns_user(monkeypatch):
    async def _fake_async(func, *args):
        return func(*args)

    monkeypatch.setattr(auth, "verify_token", lambda _t: {"sub": "11111111-1111-1111-1111-111111111111"})
    monkeypatch.setattr(auth, "async_supabase_call", _fake_async)
    monkeypatch.setattr(auth, "_fetch_user_from_db", lambda _uid: type("Resp", (), {"data": [{"id": _uid, "email": "a@b.com"}]})())
    creds = type("Creds", (), {"credentials": "token"})()
    user = await get_current_user(creds)
    assert user["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_sub(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda _t: {"sub": "not-a-uuid"})
    creds = type("Creds", (), {"credentials": "token"})()
    with pytest.raises(HTTPException) as exc:
        await get_current_user(creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_register_success_with_last_period_inserts_user(monkeypatch):
    async def _fake_async(func, *args):
        return func(*args)

    monkeypatch.setattr(auth, "async_supabase_call", _fake_async)
    monkeypatch.setattr(auth, "get_password_hash", lambda _p: "hashed")
    monkeypatch.setattr(auth, "create_access_token", lambda data: f"token-{data['sub']}")
    monkeypatch.setattr(auth, "_post_registration_sync", lambda *_a, **_k: None)
    monkeypatch.setattr(auth, "supabase", FakeClient({"users": []}))
    monkeypatch.setattr(
        auth,
        "supabase_admin",
        FakeClient(
            {
                "users": [{"id": "u-1", "email": "new@example.com", "password_hash": "hashed"}],
                "period_logs": [{"id": "p-1"}],
            }
        ),
    )

    req = RegisterRequest(
        name="A",
        email="new@example.com",
        password="Password1!",
        last_period_date="2026-05-01",
        avg_bleeding_days=4,
        cycle_length=28,
        language="en",
        language_choice="en",
        consent_accepted=True,
    )
    result = await register(req, BackgroundTasks(), None)
    assert result["msg"] == "User registered successfully"
    assert result["access_token"] == "token-u-1"


@pytest.mark.asyncio
async def test_register_rejects_cycle_length_out_of_range():
    req = RegisterRequest(
        name="A",
        email="new@example.com",
        password="Password1!",
        last_period_date="2026-05-01",
        avg_bleeding_days=4,
        cycle_length=50,
        language="en",
        language_choice="en",
        consent_accepted=True,
    )
    with pytest.raises(HTTPException) as exc:
        await register(req, BackgroundTasks(), None)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_login_success_returns_token_and_user(monkeypatch):
    async def _fake_async(func, *args):
        return func(*args)

    monkeypatch.setattr(auth, "async_supabase_call", _fake_async)
    monkeypatch.setattr(auth, "supabase", FakeClient({"users": [{"id": "u-1", "email": "a@b.com", "password_hash": "h"}]}))
    monkeypatch.setattr(auth, "verify_password", lambda _p, _h: True)
    monkeypatch.setattr(auth, "_warm_cycle_state_on_login", lambda *_a, **_k: None)
    monkeypatch.setattr(auth, "create_access_token", lambda data: f"token-{data['sub']}")
    result = await login(LoginRequest(email="a@b.com", password="Password1"))
    assert result["msg"] == "Login successful"
    assert result["access_token"] == "token-u-1"


@pytest.mark.asyncio
async def test_login_rejects_bad_password(monkeypatch):
    async def _fake_async(func, *args):
        return func(*args)

    monkeypatch.setattr(auth, "async_supabase_call", _fake_async)
    monkeypatch.setattr(auth, "supabase", FakeClient({"users": [{"id": "u-1", "email": "a@b.com", "password_hash": "h"}]}))
    monkeypatch.setattr(auth, "verify_password", lambda _p, _h: False)
    with pytest.raises(HTTPException) as exc:
        await login(LoginRequest(email="a@b.com", password="wrong"))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_me_hides_password_hash():
    result = await get_me({"id": "u-1", "password_hash": "x", "email": "a@b.com"})
    assert "password_hash" not in result
    assert result["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_delete_account_success(monkeypatch):
    async def _fake_async(func, *args):
        return func(*args)

    monkeypatch.setattr(auth, "async_supabase_call", _fake_async)
    monkeypatch.setattr(auth, "supabase", FakeClient({"users": [{"id": "u-1"}]}))
    result = await delete_account({"id": "u-1"})
    assert "permanently deleted" in result["msg"]


@pytest.mark.asyncio
async def test_update_fcm_token_requires_non_empty_token():
    with pytest.raises(HTTPException) as exc:
        await update_fcm_token(type("R", (), {"fcm_token": "   "})(), {"id": "u-1"})
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_fcm_token_success(monkeypatch):
    monkeypatch.setattr(auth, "supabase", FakeClient({"users": [{"id": "u-1"}]}))
    req = type("R", (), {"fcm_token": "abc"})()
    result = await update_fcm_token(req, {"id": "u-1"})
    assert result["msg"] == "FCM token updated successfully"


@pytest.mark.asyncio
async def test_verify_reset_otp_requires_service_role(monkeypatch):
    monkeypatch.setattr(auth, "supabase_admin", None)
    with pytest.raises(HTTPException) as exc:
        await verify_reset_otp(VerifyResetOtpRequest(email="a@b.com", otp="123456"))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_reset_otp_success(monkeypatch):
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)).isoformat()
    admin = FakeClient({"password_resets": [{"id": "r1", "expires_at": future}]})
    monkeypatch.setattr(auth, "supabase_admin", admin)
    result = await verify_reset_otp(VerifyResetOtpRequest(email="a@b.com", otp="123456"))
    assert result["message"] == "OTP verified"
    assert result["reset_token"]


@pytest.mark.asyncio
async def test_finalize_password_reset_requires_token():
    with pytest.raises(HTTPException) as exc:
        await finalize_password_reset(FinalizePasswordResetRequest(email="a@b.com", reset_token="", new_password="Password1!"))
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_finalize_password_reset_success(monkeypatch):
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)).isoformat()
    admin = FakeClient(
        {
            "password_resets": [{"id": "r1", "reset_token_expires_at": future}],
            "users": [{"id": "u-1"}],
        }
    )
    monkeypatch.setattr(auth, "supabase_admin", admin)
    monkeypatch.setattr(auth, "get_password_hash", lambda _p: "hashed")
    req = FinalizePasswordResetRequest(email="a@b.com", reset_token="tok", new_password="Password1!")
    result = await finalize_password_reset(req)
    assert result["message"] == "Password reset successful"


@pytest.mark.asyncio
async def test_logout_returns_message():
    result = await logout()
    assert result["msg"] == "logged out"
