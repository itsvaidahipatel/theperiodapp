from datetime import date

import pytest

import period_service as svc


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return type("Resp", (), {"data": self._data})()


class FakeClient:
    def __init__(self, users=None, dup=None):
        self._users = users or []
        self._dup = dup or []

    def table(self, name):
        if name == "users":
            return FakeQuery(self._users)
        if name == "period_start_logs":
            return FakeQuery(self._dup)
        return FakeQuery([])


def test_calculate_rolling_average_defaults_to_profile(monkeypatch):
    monkeypatch.setattr(svc, "get_cycles_from_period_starts", lambda *_a, **_k: [])
    monkeypatch.setattr(svc, "supabase", FakeClient(users=[{"cycle_length": 31}]))
    assert svc.calculate_rolling_average("u1") == 31.0


def test_calculate_rolling_average_weighted_recent_cycles(monkeypatch):
    cycles = [{"length": 26}, {"length": 28}, {"length": 30}]
    monkeypatch.setattr(svc, "get_cycles_from_period_starts", lambda *_a, **_k: cycles)
    assert svc.calculate_rolling_average("u1") == 28.7


def test_calculate_rolling_period_length_fallback(monkeypatch):
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "get_period_length_raw", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("x")))
    assert svc.calculate_rolling_period_length("u1") == float(svc.DEFAULT_PERIOD_DAYS)


def test_calculate_ovulation_day_clamps_range(monkeypatch):
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "estimate_luteal", lambda *_a, **_k: (40.0, 2.0))
    assert svc.calculate_ovulation_day("u1", 28) == 8


def test_calculate_prediction_confidence_no_data(monkeypatch):
    monkeypatch.setattr(svc, "get_cycles_from_period_starts", lambda *_a, **_k: [])
    import i18n

    monkeypatch.setattr(i18n, "t", lambda key, *_a, **_k: key)
    out = svc.calculate_prediction_confidence("u1", language="en")
    assert out["level"] == "Low"
    assert out["reason_key"] == "confidence.no_cycle_data"


def test_calculate_prediction_confidence_unpredictable(monkeypatch):
    cycles = [{"length": 21}, {"length": 45}, {"length": 22}, {"length": 44}]
    monkeypatch.setattr(svc, "get_cycles_from_period_starts", lambda *_a, **_k: cycles)
    monkeypatch.setattr(svc, "get_period_start_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    import i18n
    import cycle_utils

    monkeypatch.setattr(i18n, "t", lambda key, *_a, **_k: key)
    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 10))
    out = svc.calculate_prediction_confidence("u1", language="en")
    assert out["level"] in ("Unpredictable", "Low", "Medium")


def test_get_predictions_empty_without_anchor(monkeypatch):
    monkeypatch.setattr(svc, "get_period_start_logs", lambda *_a, **_k: [])
    out = svc.get_predictions("u1")
    assert out == {"predictions": [], "is_late": False}


def test_get_predictions_generates_rows(monkeypatch):
    monkeypatch.setattr(svc, "get_period_start_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    monkeypatch.setattr(svc, "calculate_rolling_average", lambda *_a, **_k: 28.0)
    monkeypatch.setattr(svc, "calculate_rolling_period_length", lambda *_a, **_k: 5.0)
    monkeypatch.setattr(svc, "calculate_prediction_confidence", lambda *_a, **_k: {"level": "High"})
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 5, 5))
    monkeypatch.setattr(cycle_utils, "estimate_luteal", lambda *_a, **_k: (14.0, 2.0))
    monkeypatch.setattr(cycle_utils, "estimate_cycle_start_sd", lambda *_a, **_k: 1.0)
    monkeypatch.setattr(cycle_utils, "select_ovulation_days", lambda *_a, **_k: {-1, 0, 1})
    out = svc.get_predictions("u1", count=2)
    assert len(out["predictions"]) == 2
    assert "predictedStart" in out["predictions"][0]


def test_can_log_period_blocks_duplicates(monkeypatch):
    monkeypatch.setattr(svc, "supabase", FakeClient(dup=[{"id": "x"}]))
    out = svc.can_log_period("u1", date(2026, 5, 1))
    assert out["canLog"] is False


def test_can_log_period_blocks_too_close(monkeypatch):
    monkeypatch.setattr(svc, "supabase", FakeClient())
    monkeypatch.setattr(svc, "get_period_start_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    out = svc.can_log_period("u1", date(2026, 5, 5))
    assert out["canLog"] is False


def test_check_anomaly_flags_outside_range(monkeypatch):
    monkeypatch.setattr(svc, "get_period_start_logs", lambda *_a, **_k: [{"start_date": "2026-05-01"}])
    assert svc.check_anomaly("u1", date(2026, 6, 20)) is True
