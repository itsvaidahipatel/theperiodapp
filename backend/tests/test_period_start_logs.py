from datetime import date

import period_start_logs as psl


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def insert(self, *_a, **_k):
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


def test_build_cycle_data_json_payload_marks_non_predicted(monkeypatch):
    import cycle_utils

    monkeypatch.setattr(
        cycle_utils,
        "calculate_phase_for_date_range",
        lambda **_k: [{"date": "2026-05-01", "phase": "Period", "is_predicted": True}],
    )
    rows = psl._build_cycle_data_json_payload("u1", "2026-05-01", "2026-05-29", [{"date": "2026-05-01"}])
    assert rows is not None
    assert rows[0]["is_predicted"] is False


def test_sync_period_start_logs_from_period_logs_empty(monkeypatch):
    monkeypatch.setattr(psl, "supabase", FakeClient({"period_logs": []}))
    monkeypatch.setattr(psl, "supabase_admin", None)
    out = psl.sync_period_start_logs_from_period_logs("u1")
    assert out == []


def test_sync_period_start_logs_from_period_logs_inserts(monkeypatch):
    monkeypatch.setattr(
        psl,
        "supabase",
        FakeClient(
            {
                "period_logs": [{"date": "2026-05-01"}, {"date": "2026-05-28"}],
                "period_start_logs": [],
            }
        ),
    )
    monkeypatch.setattr(psl, "supabase_admin", None)
    import cycle_utils

    monkeypatch.setattr(cycle_utils, "get_user_today", lambda *_a, **_k: date(2026, 6, 1))
    monkeypatch.setattr(psl, "_build_cycle_data_json_payload", lambda *_a, **_k: [{"date": "2026-05-01"}])
    out = psl.sync_period_start_logs_from_period_logs("u1")
    assert len(out) >= 1


def test_get_period_start_logs_confirmed_filter(monkeypatch):
    monkeypatch.setattr(psl, "supabase", FakeClient({"period_start_logs": [{"start_date": "2026-05-01", "is_confirmed": True}]}))
    out = psl.get_period_start_logs("u1", confirmed_only=True)
    assert out[0]["start_date"] == "2026-05-01"


def test_get_cycles_from_period_starts_derives_lengths():
    starts = [{"start_date": "2026-05-01", "is_confirmed": True}, {"start_date": "2026-05-29", "is_confirmed": True}]
    out = psl.get_cycles_from_period_starts("u1", period_starts=starts)
    assert out[0]["length"] == 28


def test_get_last_confirmed_period_start_none(monkeypatch):
    monkeypatch.setattr(psl, "get_period_start_logs", lambda *_a, **_k: [])
    assert psl.get_last_confirmed_period_start("u1") is None


def test_validate_cycle_length_short_long_normal():
    short = psl.validate_cycle_length(18)
    long = psl.validate_cycle_length(50)
    ok = psl.validate_cycle_length(28)
    assert short["is_outlier"] is True
    assert long["is_irregular"] is True
    assert ok["is_valid"] is True
