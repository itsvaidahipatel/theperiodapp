import pytest
from datetime import date
from cycle_utils import calculate_phase_for_date_range

def test_cycle_length_clamping():
    """Test: 15-day cycle should be treated as 21 days for medical safety."""
    # We pass 15, but we expect the logic to treat it as 21
    result = calculate_phase_for_date_range("test_user", date(2026, 5, 1), 15)
    # Check if a 'Luteal' phase exists (unlikely in a true 15-day cycle, but required in 21)
    has_luteal = any(day['phase_name'] == 'Luteal' for day in result)
    assert has_luteal is True

def test_leap_year_handling():
    """Test: Backend shouldn't crash on Feb 29th."""
    try:
        calculate_phase_for_date_range("test_user", date(2028, 2, 28), 28)
        assert True
    except Exception as e:
        pytest.fail(f"Leap year logic crashed with: {e}")