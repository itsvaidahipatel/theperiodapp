import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routes.cycles as cycles
from routes.cycles import (
    CyclePredictionRequest,
    PeriodStartLogCreate,
    _canonical_phase_name,
    _infer_phase_name_from_day_id,
    _late_anchor_shift_days_from_user,
    _phase_map_json_response,
    _reject_body_user_id_mismatch,
    _resolved_canonical_phase,
    _service_or_anon,
    _shift_calendar_months,
    _slim_phase_map_row,
    cycle_health_check,
    debug_cycle_data,
    get_current_phase,
    get_period_start_logs_endpoint,
    get_phase_map,
    post_period_start_logs,
    predict_cycles,
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

    def update(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class FakeClient:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, name):
        return FakeQuery(self.table_data.get(name, []))


async def _noop_async(*_a, **_k):
    return None


async def _fake_async_supabase_call(fn):
    return fn()


@pytest.mark.parametrize(
    ("start", "months_delta", "expected"),
    [
        # Leap-year February clamp
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        # Non-leap February clamp
        (date(2027, 1, 31), 1, date(2027, 2, 28)),
        # Cross-year backward shift
        (date(2026, 1, 15), -1, date(2025, 12, 15)),
        # Cross-year forward shift
        (date(2026, 12, 31), 2, date(2027, 2, 28)),
    ],
)
def test_shift_calendar_months_handles_clamps_and_year_rollover(start, months_delta, expected):
    assert _shift_calendar_months(start, months_delta) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("period", "Period"),
        (" menstrual ", "Period"),
        ("FOLLICULAR", "Follicular"),
        ("fertile", "Ovulation"),
        ("luteal", "Luteal"),
        ("Ovulation", "Ovulation"),
        ("unknown", None),
        ("", None),
        (None, None),
        (123, None),
    ],
)
def test_canonical_phase_name_normalizes_supported_inputs(raw, expected):
    assert _canonical_phase_name(raw) == expected


@pytest.mark.parametrize(
    ("phase_day_id", "expected"),
    [
        ("p1", "Period"),
        ("F4", "Follicular"),
        ("o2", "Ovulation"),
        ("L9", "Luteal"),
        ("x1", None),
        ("", None),
        (None, None),
        (7, None),
    ],
)
def test_infer_phase_name_from_day_id_prefix(phase_day_id, expected):
    assert _infer_phase_name_from_day_id(phase_day_id) == expected


@pytest.mark.parametrize(
    ("phase_raw", "phase_day_id", "expected"),
    [
        # Raw phase wins when canonicalizable.
        ("period", "f2", "Period"),
        # Fallback to day-id prefix when raw is unknown.
        ("mystery", "o1", "Ovulation"),
        # Double fallback defaults to Follicular.
        ("mystery", "z9", "Follicular"),
        (None, None, "Follicular"),
    ],
)
def test_resolved_canonical_phase_priority_and_fallback(phase_raw, phase_day_id, expected):
    assert _resolved_canonical_phase(phase_raw, phase_day_id) == expected


def test_slim_phase_map_row_returns_canonical_shape():
    row = _slim_phase_map_row(
        "2026-05-05T10:30:00Z",
        "p1",
        phase_raw="period",
        is_predicted=0,
    )

    assert row == {
        "date": "2026-05-05",
        "phase": "Period",
        "phase_day_id": "p1",
        "is_predicted": False,
    }


def test_phase_map_json_response_sets_cache_header_and_payload():
    body = {"phase_map": [{"date": "2026-05-05", "phase": "Period"}]}
    response = _phase_map_json_response(body, cache_max_age=1200)
    decoded = json.loads(response.body.decode("utf-8"))

    assert decoded == body
    assert response.headers["Cache-Control"] == "public, max-age=1200"


@pytest.mark.parametrize(
    ("user_dict", "expected"),
    [
        ({"late_period_anchor_shift_days": 3}, 3),
        ({"late_period_anchor_shift_days": -2}, 0),
        # Current helper uses max(0, value) before int(); string numerics fall back to 0.
        ({"late_period_anchor_shift_days": "4"}, 0),
        ({}, 0),
        ({"late_period_anchor_shift_days": "NaN"}, 0),
    ],
)
def test_late_anchor_shift_days_from_user_clamps_and_casts(user_dict, expected):
    assert _late_anchor_shift_days_from_user(user_dict) == expected


def test_reject_body_user_id_mismatch_allows_same_user_ids():
    payload = [
        {"user_id": "USER-123"},
        {"userId": "user-123"},
        {"note": "no user field"},
    ]
    _reject_body_user_id_mismatch(payload, "user-123")


def test_reject_body_user_id_mismatch_raises_for_other_user():
    payload = [{"user_id": "someone-else"}]
    with pytest.raises(HTTPException) as exc:
        _reject_body_user_id_mismatch(payload, "user-123")
    assert exc.value.status_code == 403


def test_service_or_anon_prefers_admin_when_available(monkeypatch):
    anon_client = object()
    admin_client = object()
    monkeypatch.setattr(cycles, "supabase", anon_client)
    monkeypatch.setattr(cycles, "supabase_admin", admin_client)
    assert _service_or_anon() is admin_client


def test_service_or_anon_falls_back_to_anon(monkeypatch):
    anon_client = object()
    monkeypatch.setattr(cycles, "supabase", anon_client)
    monkeypatch.setattr(cycles, "supabase_admin", None)
    assert _service_or_anon() is anon_client


@pytest.mark.asyncio
async def test_cycle_health_check_returns_safe_unknown_when_no_period_starts(monkeypatch):
    class FakeQuery:
        def __init__(self, data):
            self._data = data

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self._data)

    class FakeClient:
        def table(self, name):
            if name == "users":
                return FakeQuery(
                    [
                        {
                            "last_period_date": None,
                            "cycle_length": 28,
                            "late_period_anchor_shift_days": 0,
                        }
                    ]
                )
            return FakeQuery([])

    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles, "_service_or_anon", lambda: FakeClient())

    import period_start_logs

    monkeypatch.setattr(period_start_logs, "get_period_start_logs", lambda *_args, **_kwargs: [])

    result = await cycle_health_check(current_user={"sub": "u-1"})

    assert result["has_sufficient_data"] is False
    assert result["risk_level"] == "unknown"
    assert result["cycles_analyzed"] == 0


@pytest.mark.asyncio
async def test_predict_cycles_returns_phase_map_and_current_phase(monkeypatch):
    class FakeQuery:
        def __init__(self, data):
            self._data = data

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self._data)

    class FakeClient:
        def table(self, name):
            if name == "users":
                return FakeQuery(
                    [{"last_period_date": "2026-04-01", "cycle_length": 28, "late_period_anchor_shift_days": 0}]
                )
            if name == "period_logs":
                return FakeQuery([{"date": "2026-04-01", "end_date": "2026-04-05"}])
            return FakeQuery([])

    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles, "_service_or_anon", lambda: FakeClient())
    monkeypatch.setattr(cycles, "calculate_phase_for_date_range", lambda **_k: [{"date": "2026-05-05", "phase": "Follicular"}])
    monkeypatch.setattr(cycles, "get_user_phase_day", lambda *_a, **_k: {"phase": "Follicular", "phase_day_id": "f3"})

    import missing_period_handler
    import cycle_utils

    monkeypatch.setattr(missing_period_handler, "handle_missing_period", lambda *_a, **_k: None)
    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))

    body = CyclePredictionRequest(past_cycle_data=[], current_date="2026-05-05")
    result = await predict_cycles(body, current_user={"sub": "u-1"})

    assert "phase_mappings" in result
    assert result["current_phase"]["phase_day_id"] == "f3"


@pytest.mark.asyncio
async def test_get_current_phase_prefers_logged_period_data(monkeypatch):
    class FakeQuery:
        def __init__(self, data):
            self._data = data

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def update(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self._data)

    class FakeClient:
        def table(self, name):
            if name == "users":
                return FakeQuery([{"last_period_date": "2026-05-01", "cycle_length": 28, "late_period_anchor_shift_days": 0}])
            if name == "period_logs":
                return FakeQuery([{"date": "2026-05-01", "end_date": "2026-05-05"}])
            return FakeQuery([])

    async def _fake_async_supabase_call(fn):
        return fn()

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: FakeClient())
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles, "async_supabase_call", _fake_async_supabase_call)
    monkeypatch.setattr(cycles, "get_period_phase_day_from_logs", lambda *_a, **_k: "p2")

    import cycle_utils
    import missing_period_handler

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))

    async def _noop_async(*_a, **_k):
        return None

    monkeypatch.setattr(missing_period_handler, "handle_missing_period_async", _noop_async)

    result = await get_current_phase(date="2026-05-02", client_today="2026-05-05", current_user={"sub": "u-1"})

    assert result["phase"] == "Period"
    assert result["phase_day_id"] == "p2"
    assert result["is_actual"] is True


@pytest.mark.asyncio
async def test_get_phase_map_returns_slim_json_rows(monkeypatch):
    class FakeQuery:
        def __init__(self, data):
            self._data = data

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self._data)

    class FakeClient:
        def table(self, name):
            if name == "users":
                return FakeQuery([{"last_period_date": "2026-04-01", "cycle_length": 28, "late_period_anchor_shift_days": 0}])
            if name == "period_logs":
                return FakeQuery([{"date": "2026-04-01", "end_date": "2026-04-05"}])
            return FakeQuery([])

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: FakeClient())
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(
        cycles,
        "calculate_phase_for_date_range",
        lambda **_k: [{"date": "2026-05-05", "phase": "Ovulation", "phase_day_id": "o1", "is_predicted": True}],
    )
    monkeypatch.setattr(cycles, "get_period_phase_day_from_logs", lambda *_a, **_k: None)

    import cycle_utils
    import missing_period_handler
    import period_start_logs

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))
    monkeypatch.setattr(period_start_logs, "get_period_start_logs", lambda *_a, **_k: [])

    async def _noop_async(*_a, **_k):
        return None

    monkeypatch.setattr(missing_period_handler, "handle_missing_period_async", _noop_async)

    response = await get_phase_map(
        start_date="2026-05-05",
        end_date="2026-05-05",
        current_user={"sub": "u-1"},
    )
    payload = json.loads(response.body.decode("utf-8"))
    row = payload["phase_map"][0]

    assert row["date"] == "2026-05-05"
    assert row["phase"] == "Ovulation"
    assert row["phase_day_id"] == "o1"


@pytest.mark.asyncio
async def test_get_period_start_logs_endpoint_uses_authenticated_user(monkeypatch):
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    import period_start_logs

    monkeypatch.setattr(
        period_start_logs,
        "get_period_start_logs",
        lambda user_id, confirmed_only=False: [{"user_id": user_id, "confirmed_only": confirmed_only}],
    )

    result = await get_period_start_logs_endpoint(confirmed_only=True, current_user={"sub": "u-1"})
    assert result["period_start_logs"][0]["user_id"] == "u-1"
    assert result["period_start_logs"][0]["confirmed_only"] is True


@pytest.mark.asyncio
async def test_post_period_start_logs_delegates_to_record_period_log(monkeypatch):
    import routes.periods as periods

    async def _fake_record_period_log(req, client_today, current_user):
        return {
            "date": req.date,
            "bleeding_days": req.bleeding_days,
            "client_today": client_today,
            "sub": current_user.get("sub"),
        }

    monkeypatch.setattr(periods, "record_period_log", _fake_record_period_log)
    body = PeriodStartLogCreate(period_start_date="2026-05-01", bleeding_days=4)
    result = await post_period_start_logs(body, client_today="2026-05-05", current_user={"sub": "u-1"})

    assert result["date"] == "2026-05-01"
    assert result["bleeding_days"] == 4


@pytest.mark.asyncio
async def test_cycle_health_check_flags_high_risk_for_short_and_long_cycles(monkeypatch):
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

        def execute(self):
            return SimpleNamespace(data=self._data)

    class FakeClient:
        def table(self, name):
            if name == "users":
                return FakeQuery(
                    [{"last_period_date": "2026-05-01", "cycle_length": 28, "late_period_anchor_shift_days": 0}]
                )
            if name == "period_logs":
                return FakeQuery([{"date": "2026-05-01"}])
            return FakeQuery([])

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: FakeClient())
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles, "calculate_phase_for_date_range", lambda **_k: [])

    import period_start_logs
    import cycle_utils

    monkeypatch.setattr(
        period_start_logs,
        "get_period_start_logs",
        lambda *_a, **_k: [
            {"start_date": "2026-01-01"},
            {"start_date": "2026-01-19"},  # 18
            {"start_date": "2026-03-10"},  # 50
            {"start_date": "2026-04-01"},  # 22
        ],
    )
    monkeypatch.setattr(
        period_start_logs,
        "get_cycles_from_period_starts",
        lambda *_a, **_k: [{"length": 18}, {"length": 50}, {"length": 22}],
    )
    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 20))
    monkeypatch.setattr(cycles, "get_user_phase_day", lambda *_a, **_k: {"phase": "Follicular", "phase_day_id": "f2"})
    # Imported inside cycle_health_check from cycle_utils; patch there.
    monkeypatch.setattr(cycle_utils, "estimate_luteal", lambda *_a, **_k: (14.0, 2.0))
    monkeypatch.setattr(cycle_utils, "predict_ovulation", lambda *_a, **_k: ("2026-05-14", 2.0, 0))

    result = await cycle_health_check(current_user={"sub": "u-1"})
    types = {a["type"] for a in result["abnormalities"]}

    assert result["has_sufficient_data"] is True
    assert result["risk_level"] == "high"
    assert "short_cycles" in types
    assert "long_cycles" in types


@pytest.mark.asyncio
async def test_debug_cycle_data_hidden_when_debug_mode_off(monkeypatch):
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles.os, "getenv", lambda *_a, **_k: "0")

    with pytest.raises(HTTPException) as exc:
        await debug_cycle_data(current_user={"sub": "u-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_debug_cycle_data_returns_grouped_data_when_debug_mode_on(monkeypatch):
    class FakeQuery:
        def __init__(self, data):
            self._data = data

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=self._data)

    class FakeClient:
        def table(self, name):
            if name == "period_logs":
                return FakeQuery([{"date": "2026-05-01", "user_id": "u-1"}])
            if name == "user_cycle_days":
                return FakeQuery([{"date": "2026-05-01", "phase_day_id": "p1"}])
            if name == "users":
                return FakeQuery([{"last_period_date": "2026-05-01", "cycle_length": 28}])
            return FakeQuery([])

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: FakeClient())
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles.os, "getenv", lambda *_a, **_k: "true")
    monkeypatch.setattr(cycles, "group_logs_into_episodes", lambda logs: [{"count": len(logs)}])

    result = await debug_cycle_data(current_user={"sub": "u-1"})

    assert result["period_logs_count"] == 1
    assert result["cycle_days_count"] == 1
    assert result["bleeding_episodes"][0]["count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_cycle_length", [15, 60])
async def test_get_phase_map_medical_clamping_inputs_flow_to_cycle_engine(monkeypatch, raw_cycle_length):
    fake_client = FakeClient(
        {
            "users": [{"last_period_date": "2026-04-01", "cycle_length": raw_cycle_length, "late_period_anchor_shift_days": 0}],
            "period_logs": [{"date": "2026-04-01", "end_date": "2026-04-05"}],
        }
    )

    captured = {}

    def _fake_calculate_phase_for_date_range(**kwargs):
        captured["cycle_length"] = kwargs.get("cycle_length")
        return [{"date": "2026-05-05", "phase": "Follicular", "phase_day_id": "f1", "is_predicted": True}]

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: fake_client)
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles, "calculate_phase_for_date_range", _fake_calculate_phase_for_date_range)
    monkeypatch.setattr(cycles, "get_period_phase_day_from_logs", lambda *_a, **_k: None)

    import cycle_utils
    import missing_period_handler
    import period_start_logs

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))
    monkeypatch.setattr(period_start_logs, "get_period_start_logs", lambda *_a, **_k: [])

    monkeypatch.setattr(missing_period_handler, "handle_missing_period_async", _noop_async)

    await get_phase_map(start_date="2026-05-05", end_date="2026-05-05", current_user={"sub": "u-1"})
    assert captured["cycle_length"] == raw_cycle_length


@pytest.mark.asyncio
async def test_get_current_phase_accepts_leap_day_date(monkeypatch):
    fake_client = FakeClient(
        {
            "users": [{"last_period_date": "2028-02-01", "cycle_length": 28, "late_period_anchor_shift_days": 0}],
            "period_logs": [],
        }
    )

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: fake_client)
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(cycles, "async_supabase_call", _fake_async_supabase_call)
    monkeypatch.setattr(cycles, "get_period_phase_day_from_logs", lambda *_a, **_k: None)
    monkeypatch.setattr(
        cycles,
        "calculate_phase_for_date_range",
        lambda **_k: [{"date": "2028-02-29", "phase": "Follicular", "phase_day_id": "f1", "is_predicted": True}],
    )

    import cycle_utils
    import missing_period_handler

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2028, 2, 29))

    monkeypatch.setattr(missing_period_handler, "handle_missing_period_async", _noop_async)

    result = await get_current_phase(date="2028-02-29", client_today="2028-02-29", current_user={"sub": "u-1"})
    assert result["date"] == "2028-02-29"
    assert result["phase_day_id"] == "f1"


@pytest.mark.asyncio
async def test_get_phase_map_returns_empty_when_anchor_missing(monkeypatch):
    fake_client = FakeClient(
        {
            "users": [{"last_period_date": None, "cycle_length": 28, "late_period_anchor_shift_days": 0}],
            "period_logs": [],
        }
    )

    monkeypatch.setattr(cycles, "_service_or_anon", lambda: fake_client)
    monkeypatch.setattr(cycles, "authenticated_subject_id", lambda _u: "u-1")

    import cycle_utils
    import missing_period_handler

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))

    monkeypatch.setattr(missing_period_handler, "handle_missing_period_async", _noop_async)

    response = await get_phase_map(start_date="2026-05-01", end_date="2026-05-05", current_user={"sub": "u-1"})
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["phase_map"] == []
