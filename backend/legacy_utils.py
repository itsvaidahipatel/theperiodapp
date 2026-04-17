"""
Legacy / deprecated utilities kept for reference only.
RapidAPI-related and deprecated cycle logic. Do not use in production.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional


def get_cached_request_id(user_id: str) -> Optional[str]:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("get_cached_request_id is deprecated. Use local adaptive algorithms.")


def cache_request_id(user_id: str, request_id: str, expires_in_hours: int = 24) -> None:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("cache_request_id is deprecated. Use local adaptive algorithms.")


def process_cycle_data(
    past_cycle_data: List[Dict], current_date: str, max_predictions: int = 6, user_id: Optional[str] = None
) -> str:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("process_cycle_data is deprecated. Use local adaptive algorithms instead.")


def get_predicted_cycle_starts(request_id: str) -> List[str]:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("get_predicted_cycle_starts is deprecated. Use local adaptive algorithms instead.")


def get_average_period_length(request_id: str) -> float:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("get_average_period_length is deprecated. Use estimate_period_length() instead.")


def get_average_cycle_length(request_id: str) -> float:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError(
        "get_average_cycle_length is deprecated. Use compute_cycle_stats_from_period_starts() in cycle_stats instead."
    )


def get_cycle_phases(request_id: str) -> List[Dict]:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("get_cycle_phases is deprecated. Use calculate_phase_for_date_range() instead.")


def predict_cycle_phases(
    cycle_start_date: str, next_cycle_start_date: str, period_length: int
) -> dict:
    """DEPRECATED: RapidAPI. Raises if called."""
    raise NotImplementedError("predict_cycle_phases is deprecated. Use calculate_phase_for_date_range() instead.")


def generate_cycle_phase_map(
    user_id: str,
    past_cycle_data: List[Dict],
    current_date: str,
    update_future_only: bool = False,
) -> List[Dict]:
    """
    DEPRECATED: RapidAPI version. No longer used.
    Use calculate_phase_for_date_range() in cycle_utils for local adaptive calculations.
    This function raises if called.
    """
    raise NotImplementedError(
        "generate_cycle_phase_map (RapidAPI) is deprecated. Use calculate_phase_for_date_range() instead."
    )
