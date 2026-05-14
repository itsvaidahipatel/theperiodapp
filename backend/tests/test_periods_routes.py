from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import routes.periods as periods
from routes.periods import (
    PeriodEndRequest,
    PeriodLogRequest,
    PeriodLogUpdate,
    UpdateLastAnchorRequest,
    _assemble_period_log_response,
    _medical_overlap_exception,
    _next_predicted_period_start,
    _parse_db_timestamp,
    _within_idempotency_window,
    delete_period_log,
    get_period_episodes,
    get_period_logs,
    get_predictions_endpoint,
    get_stats,
    log_period,
    log_period_end,
    parse_period_date,
    record_period_log,
    toggle_anomaly,
    update_last_anchor,
    update_period_log,
)


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def lt(self, *_a, **_k):
        return self

    def neq(self, *_a, **_k):
        return self

    def is_(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, *_a, **_k):
        return self

    def update(self, *_a, **_k):
        return self

    def delete(self, *_a, **_k):
        return self

    def execute(self):
        return type("Resp", (), {"data": self._data})()


class FakeClient:
    def __init__(self, table_map):
        self.table_map = table_map

    def table(self, name):
        return FakeQuery(self.table_map.get(name, []))


def test_parse_period_date_accepts_string_date_datetime():
    assert parse_period_date("2026-05-01").isoformat() == "2026-05-01"
    assert parse_period_date(date(2026, 5, 1)).isoformat() == "2026-05-01"
    assert parse_period_date(datetime(2026, 5, 1, 8, 0, 0)).isoformat() == "2026-05-01"


def test_parse_period_date_rejects_none():
    with pytest.raises(ValueError):
        parse_period_date(None)


def test_parse_db_timestamp_parses_iso_and_zulu():
    ts = _parse_db_timestamp("2026-05-05T10:00:00Z")
    assert ts is not None
    assert ts.tzinfo is not None


def test_within_idempotency_window_true_for_recent_row():
    row = {"updated_at": datetime.now(timezone.utc).isoformat()}
    assert _within_idempotency_window(row, seconds=5) is True


def test_medical_overlap_exception_has_expected_contract():
    exc = _medical_overlap_exception("2026-05-01")
    assert exc.status_code == 409
    assert exc.detail["code"] == "MEDICAL_OVERLAP"
    assert exc.detail["existingPeriodStart"] == "2026-05-01"


def test_assemble_period_log_response_shape():
    payload = _assemble_period_log_response(
        saved_row={"id": "1", "date": "2026-05-01", "end_date": "2026-05-05"},
        logs=[{"id": "1", "date": "2026-05-01", "end_date": "2026-05-05"}],
        predictions=[{"date": "2026-05-28"}],
        rolling_average=28.0,
        rolling_period_average=5.0,
        is_anomaly=False,
        estimated_end_date=date(2026, 5, 5),
    )
    assert payload["log"]["date"] == "2026-05-01"
    assert payload["rollingAverage"] == 28.0
    assert isinstance(payload["logs"], list)


def test_next_predicted_period_start_clamps_cycle_length(monkeypatch):
    monkeypatch.setattr(periods, "get_period_start_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    monkeypatch.setattr(periods, "calculate_rolling_average", lambda *_a, **_k: 100.0)
    nxt = _next_predicted_period_start("u-1")
    assert nxt == date(2026, 5, 1) + timedelta(days=periods.MAX_CYCLE_DAYS)


@pytest.mark.asyncio
async def test_record_period_log_rejects_future_dates(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 1))
    with pytest.raises(HTTPException) as exc:
        await record_period_log(PeriodLogRequest(date="2026-05-02"), "2026-05-01", {"id": "u-1"})
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_log_period_delegates_to_record_period_log(monkeypatch):
    async def _fake_record(log_data, client_today, current_user):
        return {"ok": True, "date": log_data.date, "user": current_user["id"], "client_today": client_today}

    monkeypatch.setattr(periods, "record_period_log", _fake_record)
    result = await log_period(PeriodLogRequest(date="2026-05-01"), "2026-05-05", {"id": "u-1"})
    assert result["ok"] is True
    assert result["date"] == "2026-05-01"


@pytest.mark.asyncio
async def test_get_period_logs_maps_response(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": [{"id": "1", "date": "2026-05-01", "end_date": "2026-05-05"}]}))
    result = await get_period_logs({"id": "u-1"})
    assert result[0]["startDate"] == "2026-05-01"
    assert result[0]["endDate"] == "2026-05-05"


@pytest.mark.asyncio
async def test_get_predictions_endpoint_returns_bundle(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "get_predictions", lambda *_a, **_k: {"predictions": [{"date": "2026-06-01"}], "is_late": True})
    monkeypatch.setattr(periods, "calculate_rolling_average", lambda *_a, **_k: 28.0)
    monkeypatch.setattr(periods, "calculate_rolling_period_length", lambda *_a, **_k: 5.0)
    monkeypatch.setattr(periods, "get_cycle_stats", lambda *_a, **_k: {"confidence": {"level": "high"}})
    result = await get_predictions_endpoint(6, "2026-05-05", {"id": "u-1", "language": "en"})
    assert result["isLate"] is True
    assert result["rollingAverage"] == 28.0


@pytest.mark.asyncio
async def test_get_stats_returns_validated_model(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "get_cycle_stats", lambda *_a, **_k: {"totalCycles": 3, "averageCycleLength": 29.0})
    result = await get_stats({"id": "u-1", "language": "en"})
    assert result.totalCycles == 3
    assert result.averageCycleLength == 29.0


@pytest.mark.asyncio
async def test_get_period_episodes_builds_predicted_end(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "get_period_start_logs", lambda *_a, **_k: [{"start_date": "2026-05-01", "is_confirmed": True}])
    result = await get_period_episodes({"id": "u-1"})
    assert result[0]["predicted_end_date"] == "2026-05-05"


@pytest.mark.asyncio
async def test_update_period_log_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": []}))
    with pytest.raises(HTTPException) as exc:
        await update_period_log("missing", PeriodLogUpdate(date="2026-05-01"), "2026-05-05", {"id": "u-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_period_log_not_found(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": []}))
    with pytest.raises(HTTPException) as exc:
        await delete_period_log("missing", "2026-05-05", {"id": "u-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_period_log_success(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": [{"id": "1"}]}))
    monkeypatch.setattr(periods, "sync_period_start_logs_from_period_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    monkeypatch.setattr(periods, "update_user_cycle_stats", lambda *_a, **_k: None)
    result = await delete_period_log("1", "2026-05-05", {"id": "u-1"})
    assert result["message"] == "Period log deleted"


@pytest.mark.asyncio
async def test_log_period_end_no_open_period(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": []}))
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))
    with pytest.raises(HTTPException) as exc:
        await log_period_end(PeriodEndRequest(date="2026-05-05"), "2026-05-05", {"id": "u-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_log_period_end_success(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": [{"id": "1", "date": "2026-05-01"}]}))
    monkeypatch.setattr(periods, "sync_period_start_logs_from_period_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    monkeypatch.setattr(periods, "update_user_cycle_stats", lambda *_a, **_k: None)
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 10))
    result = await log_period_end(PeriodEndRequest(date="2026-05-05"), "2026-05-10", {"id": "u-1"})
    assert result["duration"] == 5


@pytest.mark.asyncio
async def test_toggle_anomaly_not_found(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": []}))
    with pytest.raises(HTTPException) as exc:
        await toggle_anomaly("missing", "2026-05-05", {"id": "u-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_toggle_anomaly_success(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(
        periods,
        "_service_or_anon",
        lambda: FakeClient({"period_logs": [{"id": "1", "date": "2026-05-01"}], "period_start_logs": [{"is_outlier": False}]}),
    )
    monkeypatch.setattr(periods, "sync_period_start_logs_from_period_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    result = await toggle_anomaly("1", "2026-05-05", {"id": "u-1"})
    assert result["isOutlier"] is True


@pytest.mark.asyncio
async def test_update_last_anchor_no_logs(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": []}))
    with pytest.raises(HTTPException) as exc:
        await update_last_anchor(UpdateLastAnchorRequest(date="2026-05-01"), {"id": "u-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_last_anchor_success(monkeypatch):
    monkeypatch.setattr(periods, "authenticated_subject_id", lambda _u: "u-1")
    monkeypatch.setattr(periods, "_service_or_anon", lambda: FakeClient({"period_logs": [{"id": "1", "date": "2026-04-01"}], "users": [{"id": "u-1"}]}))
    monkeypatch.setattr(periods, "_post_registration_sync", lambda *_a, **_k: None)
    result = await update_last_anchor(UpdateLastAnchorRequest(date="2026-05-01"), {"id": "u-1", "avg_bleeding_days": 5})
    assert result["message"] == "Last anchor updated successfully"
