import cycle_stats as cs


def test_compute_cycle_stats_defaults_without_cycles(monkeypatch):
    monkeypatch.setattr(cs, "get_cycles_from_period_starts", lambda *_a, **_k: [])
    out = cs.compute_cycle_stats_from_period_starts("u1")
    assert out["cycle_count"] == 0
    assert out["cycle_length_mean"] == cs.POPULATION_PRIOR_MEAN


def test_compute_cycle_stats_with_valid_cycles(monkeypatch):
    cycles = [{"length": 27}, {"length": 29}, {"length": 28}]
    monkeypatch.setattr(cs, "get_cycles_from_period_starts", lambda *_a, **_k: cycles)
    out = cs.compute_cycle_stats_from_period_starts("u1")
    assert out["cycle_count"] == 3
    assert round(out["cycle_length_mean"], 1) == 28.0


def test_update_user_cycle_stats_calls_bayesian_update(monkeypatch):
    called = {}
    import cycle_utils

    monkeypatch.setattr(cs, "compute_cycle_stats_from_period_starts", lambda *_a, **_k: {"cycle_count": 2, "cycle_length_mean": 29.0, "outlier_count": 0, "irregular_count": 0})
    monkeypatch.setattr(cycle_utils, "update_cycle_length_bayesian", lambda uid, cl: called.update(uid=uid, cl=cl))
    cs.update_user_cycle_stats("u1")
    assert called["uid"] == "u1"
    assert called["cl"] == 29


def test_default_empty_stats_contract():
    out = cs._default_empty_stats()
    assert out["totalCycles"] == 0
    assert out["confidence"]["percentage"] == 0


def test_get_cycle_stats_returns_defaults_when_no_period_starts(monkeypatch):
    monkeypatch.setattr(cs, "get_period_start_logs", lambda *_a, **_k: [])
    import period_start_logs

    monkeypatch.setattr(period_start_logs, "sync_period_start_logs_from_period_logs", lambda *_a, **_k: [])
    out = cs.get_cycle_stats("u1", language="en")
    assert out["totalCycles"] == 0


def test_get_cycle_stats_happy_path(monkeypatch):
    period_starts = [{"start_date": "2026-05-01", "is_confirmed": True}, {"start_date": "2026-05-29", "is_confirmed": True}]
    monkeypatch.setattr(cs, "get_period_start_logs", lambda *_a, **_k: period_starts)
    monkeypatch.setattr(cs, "get_cycles_from_period_starts", lambda *_a, **_k: [{"length": 28, "is_outlier": False, "is_irregular": False}])

    class FakeQuery:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def order(self, *_a, **_k):
            return self

        def execute(self):
            return type("Resp", (), {"data": [{"date": "2026-05-01", "flow": "Medium"}]})()

    class FakeClient:
        def table(self, _name):
            return FakeQuery()

    monkeypatch.setattr(cs, "supabase", FakeClient())
    monkeypatch.setattr(cs, "calculate_rolling_average", lambda *_a, **_k: 28.0)
    monkeypatch.setattr(cs, "calculate_rolling_period_length", lambda *_a, **_k: 5.0)
    monkeypatch.setattr(cs, "calculate_prediction_confidence", lambda *_a, **_k: {"level": "High", "percentage": 90, "reason": "ok"})
    monkeypatch.setattr(cs, "group_logs_into_episodes", lambda *_a, **_k: [{"start_date": "2026-05-01", "end_date": "2026-05-05", "length": 5, "is_confirmed": True}])
    monkeypatch.setattr(cs, "get_phase_bounds_for_dots", lambda *_a, **_k: (5, 14, 13, 15))
    monkeypatch.setattr(cs, "calculate_phase_for_date_range", lambda **_k: [{"date": "2026-05-01", "phase": "Period"}])
    import i18n

    monkeypatch.setattr(i18n, "t", lambda key, *_a, **_k: key)
    out = cs.get_cycle_stats("u1", language="en")
    assert "averageCycleLength" in out
    assert "allCycles" in out
