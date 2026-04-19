"""
Cycle phase mapping and prediction utilities.
Uses adaptive, medically credible algorithms to predict cycles and generate phase-day mappings.
All calculations are performed locally without external API dependencies.
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from database import supabase

logger = logging.getLogger(__name__)

# Deprecated RapidAPI stubs moved to legacy_utils.py. All cycle predictions use calculate_phase_for_date_range().

# Max day-in-phase bounds for phase_day_id (wellness agents expect these ranges)
PHASE_DAY_CAPS = {"Period": 10, "Menstrual": 10, "Follicular": 14, "Ovulation": 3, "Luteal": 14}


def get_user_today(client_today_str: Optional[str] = None) -> date:
    """
    Resolve "today" as a naive calendar date in the user's perspective.

    Device-first, IST-fallback contract:
    - Priority 1: If the client sends `YYYY-MM-DD`, treat it as absolute truth.
    - Priority 2 (last resort): Use Asia/Kolkata calendar day.

    Prohibition: never use naive `datetime.now()` which depends on server timezone (often UTC).
    """
    if client_today_str:
        return datetime.strptime(str(client_today_str).strip()[:10], "%Y-%m-%d").date()
    try:
        import pytz  # type: ignore

        return datetime.now(pytz.timezone("Asia/Kolkata")).date()
    except Exception:
        # Fallback without external deps (Python stdlib offset). Kept as last resort.
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(ist).date()


def group_logs_into_episodes(
    logs: List[Dict],
    *,
    reference_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Group consecutive bleeding days from period_logs-style rows into episodes (no I/O).

    A day counts as bleeding when ``flow`` is present and not ``none`` (case-insensitive).
    Consecutive calendar days (gap == 1) belong to the same episode. A larger gap ends the
    current episode and starts a new one.

    Returns dicts: ``start_date``, ``end_date`` (YYYY-MM-DD), ``length`` (days), ``is_confirmed``.
    Intermediate episodes are confirmed when the gap to the next bleeding day is > 1 day.
    The trailing episode uses ``reference_date`` (default: today) to mirror legacy behavior:
    confirmed when at least one full day has passed since ``end_date``.
    """
    if not logs:
        return []

    bleeding_days: List[date] = []
    for log in logs:
        flow_raw = log.get("flow")
        flow = str(flow_raw).lower().strip() if flow_raw is not None else ""
        if not flow or flow == "none":
            continue
        date_str = log.get("date")
        if not date_str:
            continue
        try:
            if isinstance(date_str, str):
                d = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").date()
            elif hasattr(date_str, "date"):
                d = date_str.date()
            else:
                d = date_str
            bleeding_days.append(d)
        except (TypeError, ValueError):
            continue

    bleeding_days = sorted(set(bleeding_days))
    if not bleeding_days:
        return []

    # Avoid server-local naive date.today(); default to device-first resolver.
    ref = reference_date if reference_date is not None else get_user_today(None)
    episodes: List[Dict[str, Any]] = []

    current_start = bleeding_days[0]
    current_end = bleeding_days[0]

    for i in range(1, len(bleeding_days)):
        days_gap = (bleeding_days[i] - current_end).days
        if days_gap == 1:
            current_end = bleeding_days[i]
            continue

        period_length = (current_end - current_start).days + 1
        is_confirmed = days_gap > 1
        episodes.append(
            {
                "start_date": current_start.strftime("%Y-%m-%d"),
                "end_date": current_end.strftime("%Y-%m-%d"),
                "length": period_length,
                "is_confirmed": is_confirmed,
            }
        )
        current_start = bleeding_days[i]
        current_end = bleeding_days[i]

    period_length = (current_end - current_start).days + 1
    days_since_end = (ref - current_end).days
    episodes.append(
        {
            "start_date": current_start.strftime("%Y-%m-%d"),
            "end_date": current_end.strftime("%Y-%m-%d"),
            "length": period_length,
            "is_confirmed": days_since_end >= 1,
        }
    )

    return episodes


def generate_phase_day_id(phase: str, day_in_phase: int) -> str:
    """
    Generate phase-day ID based on phase and day.
    Capped to match wellness DB (p1-p10, f1-f14, o1-o3, l1-l14).
    """
    phase_prefix = {
        "Period": "p",
        "Menstrual": "p",
        "Follicular": "f",
        "Ovulation": "o",
        "Luteal": "l"
    }
    prefix = phase_prefix.get(phase, "p")
    cap = PHASE_DAY_CAPS.get(phase, 14)
    day_in_phase = max(1, min(int(day_in_phase), cap))
    return f"{prefix}{day_in_phase}"


def _calendar_phase_day_id(phase: str, day_in_phase: int, *, ovulation_cap: int = 5) -> str:
    """
    Phase-day IDs for calendar/phase-map responses.

    Unlike `generate_phase_day_id`, this intentionally does NOT cap ovulation at 3 days:
    the calendar may represent a wider ovulation-uncertainty window (up to 5 days),
    and collapsing those to `o3` causes repeated IDs in the UI.
    """
    phase_prefix = {
        "Period": "p",
        "Menstrual": "p",
        "Follicular": "f",
        "Ovulation": "o",
        "Luteal": "l",
    }
    prefix = phase_prefix.get(phase, "p")
    if prefix == "o":
        cap = max(1, int(ovulation_cap))
    else:
        cap = PHASE_DAY_CAPS.get(phase, 14)
    day = max(1, min(int(day_in_phase), cap))
    return f"{prefix}{day}"


def parse_phase_day_id(phase_day_id: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """Parse phase-day ID like 'f7' into phase prefix ('f') and day number (7)."""
    if not phase_day_id or len(phase_day_id) < 2:
        return None, None
    phase_prefix = phase_day_id[0].lower()
    try:
        day_num = int(phase_day_id[1:])
        return phase_prefix, day_num
    except ValueError:
        return None, None


def parse_hormone_value(value: Any) -> float:
    """
    Coerce hormones_data numeric hormone columns to float for charts.

    Post-migration: estrogen/progesterone/fsh/lh are DECIMAL; legacy rows may still hold
    parseable numeric strings. Non-numeric text (e.g. old 'Low'/'High' labels) returns 0.0 —
    use estrogen_text / *_text columns for display labels, not this helper.
    """
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def get_previous_phase_day_ids(current_phase_day_id: str, total_ids: int) -> List[str]:
    """
    Walk backward in phase-day space to produce a chronological list of phase_day_id strings
    (oldest first, current last). Used for wellness hormone history charts.

    Phase bounds match the legacy wellness navigator (wider than PHASE_DAY_CAPS used when persisting IDs).
    """
    try:
        phase_prefix, day_num = parse_phase_day_id(current_phase_day_id)
        if not phase_prefix or day_num is None:
            logger.debug("Could not parse phase_day_id: %s", current_phase_day_id)
            return [current_phase_day_id.lower()] if current_phase_day_id else []

        phase_limits = {"p": 12, "f": 30, "o": 8, "l": 25}
        phase_order = ["p", "f", "o", "l"]
        phase_day_ids: List[str] = []

        current_day = day_num
        current_phase = phase_prefix
        phase_day_ids.append(current_phase_day_id.lower())

        for _ in range(max(0, total_ids - 1)):
            current_day -= 1
            if current_day < 1:
                try:
                    phase_index = phase_order.index(current_phase)
                    if phase_index > 0:
                        current_phase = phase_order[phase_index - 1]
                    else:
                        current_phase = phase_order[-1]
                    current_day = phase_limits.get(current_phase, 1)
                except ValueError:
                    logger.debug("Phase %s not in phase_order", current_phase)
                    break
                except Exception:
                    logger.exception("Phase transition error")
                    break

            phase_limit = phase_limits.get(current_phase, 1)
            if current_day > phase_limit:
                current_day = phase_limit
            if current_day < 1:
                current_day = 1

            try:
                phase_name = {
                    "p": "Period",
                    "f": "Follicular",
                    "o": "Ovulation",
                    "l": "Luteal",
                }.get(current_phase, "Period")
                prev_phase_day_id = generate_phase_day_id(phase_name, current_day)
                phase_day_ids.insert(0, prev_phase_day_id.lower())
            except Exception:
                logger.exception("Error generating phase_day_id for phase=%s day=%s", current_phase, current_day)
                break

        return phase_day_ids
    except Exception:
        logger.exception("get_previous_phase_day_ids failed")
        return [current_phase_day_id.lower()] if current_phase_day_id else []


def normal_pdf(x: float, mean: float, sd: float) -> float:
    """
    Calculate probability density function of normal distribution.
    
    Args:
        x: Value to evaluate
        mean: Mean of the distribution
        sd: Standard deviation
    
    Returns:
        PDF value
    """
    if sd <= 0:
        return 0.0
    variance = sd * sd
    coefficient = 1.0 / (sd * math.sqrt(2 * math.pi))
    exponent = -0.5 * ((x - mean) / sd) ** 2
    return coefficient * math.exp(exponent)

def estimate_luteal(user_id: str, user_observations: Optional[List[float]] = None) -> tuple[float, float]:
    """
    Estimate luteal phase length using Bayesian smoothing.
    
    Args:
        user_id: User ID
        user_observations: List of observed luteal lengths (optional, will fetch from DB if None)
    
    Returns:
        Tuple of (mean, sd) for luteal phase length
    """
    # Population prior
    prior_mean = 14.0
    prior_sd = 2.0
    min_luteal = 10.0
    max_luteal = 18.0
    
    # Get user observations from database if not provided
    if user_observations is None:
        try:
            # Try to get from user_cycle_days or calculate from period logs
            user_response = supabase.table("users").select("luteal_observations").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("luteal_observations"):
                import json
                user_observations = json.loads(user_response.data[0]["luteal_observations"])
            else:
                user_observations = []
        except:
            user_observations = []
    
    if not user_observations or len(user_observations) == 0:
        # No user data, use prior
        return prior_mean, prior_sd
    
    # Calculate user statistics
    n = len(user_observations)
    obs_mean = sum(user_observations) / n
    if n > 1:
        variance = sum((x - obs_mean) ** 2 for x in user_observations) / (n - 1)
        obs_sd = math.sqrt(variance)
    else:
        obs_sd = 1.5  # Default SD if only one observation
    
    # Proper Bayesian smoothing with sample-size weighting
    # Weight increases with number of observations: weight = n / (n + k)
    # k = 5 means we need 5 observations to trust data 50%, 10 observations for 67%, etc.
    k = 5  # Prior strength constant
    weight = n / (n + k)
    
    # Weighted combination: more observations → trust data more
    mean = (1 - weight) * prior_mean + weight * obs_mean
    
    # SD: weighted average, but also account for sample size
    sd = (1 - weight) * prior_sd + weight * obs_sd
    
    # Clamp to allowed range
    mean = max(min_luteal, min(max_luteal, mean))
    
    return mean, sd

def get_user_avg_bleeding_days(user_id: str) -> Optional[int]:
    """
    Get user's typical bleeding length from users.avg_bleeding_days (2-8).
    Used for auto end_date when logging period start and for phase map period length.
    Returns None if column missing or not set (caller should fall back to estimate_period_length).
    """
    try:
        r = supabase.table("users").select("avg_bleeding_days").eq("id", user_id).limit(1).execute()
        if r.data and len(r.data) > 0:
            v = r.data[0].get("avg_bleeding_days")
            if v is not None:
                n = int(v)
                return max(2, min(8, n))
    except Exception:
        pass
    return None


def estimate_period_length(user_id: str, user_observations: Optional[List[float]] = None, normalized: bool = False) -> float:
    """
    Estimate period length using Bayesian smoothing.
    Adaptive period length based on user history.
    
    ARCHITECTURE:
    - raw_estimate: True period length from user data (no clamping)
    - normalized_estimate: Clamped to medically typical range (3-8 days) for phase calculations
    
    Usage:
    - Stats & insights: Use raw_estimate (get_period_length_raw())
    - Phase calculations: Use normalized_estimate (this function with normalized=True)
    - UI: Show raw_estimate with explanation if outside typical range
    
    Args:
        user_id: User ID
        user_observations: List of observed period lengths (optional, will fetch from DB if None)
        normalized: If True, returns normalized (clamped 3-8 days). If False, returns raw estimate.
    
    Returns:
        Estimated period length (mean) in days
        - If normalized=False: Raw estimate (actual pattern, may be outside 3-8 days)
        - If normalized=True: Normalized estimate (clamped to 3-8 days for phase calculations)
    """
    # Population prior
    prior_mean = 5.0
    min_period = 3.0
    max_period = 8.0
    
    # Get user observations from database if not provided
    if user_observations is None:
        try:
            # Try to get from period_logs table
            # Note: period_logs table uses 'date' column (each row is one day of period)
            period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(60).execute()
            
            if period_logs_response.data and len(period_logs_response.data) > 0:
                # Group consecutive dates to form periods
                dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d") for log in period_logs_response.data if log.get("date")])
                
                # Group consecutive dates into periods
                periods = []
                if dates:
                    current_period_start = dates[0]
                    for i in range(1, len(dates)):
                        # If gap > 1 day, start new period
                        if (dates[i] - dates[i-1]).days > 1:
                            periods.append({
                                "start": current_period_start,
                                "end": dates[i-1]
                            })
                            current_period_start = dates[i]
                    # Add last period
                    periods.append({
                        "start": current_period_start,
                        "end": dates[-1]
                    })
                
                user_observations = []
                for period in periods[-12:]:  # Last 12 periods
                    period_length = (period["end"] - period["start"]).days + 1
                    user_observations.append(float(period_length))
        except Exception as e:
            print(f"⚠️ Error calculating period length from logs: {str(e)}")
            user_observations = []
    
    if not user_observations or len(user_observations) == 0:
        # No user data, use prior
        raw_estimate = prior_mean
    else:
        # Calculate user mean
        n = len(user_observations)
        obs_mean = sum(user_observations) / n
        
        # Proper Bayesian smoothing with sample-size weighting
        # Weight increases with number of observations: weight = n / (n + k)
        # k = 5 means we need 5 observations to trust data 50%, 10 observations for 67%, etc.
        k = 5  # Prior strength constant
        weight = n / (n + k)
        
        # Weighted combination: more observations → trust data more
        raw_estimate = (1 - weight) * prior_mean + weight * obs_mean
    
    # Return raw or normalized based on parameter
    if normalized:
        # Clamp to medically typical range for phase calculations
        normalized_estimate = max(min_period, min(max_period, raw_estimate))
        return round(normalized_estimate, 1)
    else:
        # Return raw estimate (actual pattern, may be outside 3-8 days)
        return round(raw_estimate, 1)


def get_phase_bounds_for_dots(
    user_id: str, cycle_length: int, avg_period_length: float
) -> Tuple[int, int, int, int]:
    """
    Period and ovulation day bounds for dashboard dots (aligned with calculate_phase_for_date_range).

    Returns:
        (period_length_days, ovulation_day, ovulation_start, ovulation_end) — all 1-based day-in-cycle indices.
    """
    try:
        luteal_mean, _ = estimate_luteal(user_id)
        period_days_raw = estimate_period_length(user_id, normalized=True)
        period_length_days = int(round(max(3.0, min(8.0, period_days_raw))))
        actual_cl = max(21, min(45, int(cycle_length)))
        ov_day = int(max(period_length_days + 1, actual_cl - luteal_mean))
        ov_start = max(period_length_days + 1, ov_day - 1)
        ov_end = min(actual_cl, ov_day + 1)
        return (period_length_days, ov_day, ov_start, ov_end)
    except Exception:
        logger.warning("get_phase_bounds_for_dots fallback for user_id=%s", user_id, exc_info=True)
        pl = int(round(max(3, min(8, avg_period_length))))
        cl = max(21, min(45, int(cycle_length)))
        ov = max(pl + 1, cl - 14)
        return (pl, ov, max(pl + 1, ov - 1), min(cl, ov + 1))


def get_period_length_raw(user_id: str) -> float:
    """
    Get raw period length estimate (actual pattern, not clamped).
    Use for stats, insights, and medical flags.
    
    Args:
        user_id: User ID
    
    Returns:
        Raw period length estimate (may be outside 3-8 days)
    """
    return estimate_period_length(user_id, normalized=False)


def get_period_length_normalized(user_id: str) -> float:
    """
    Get normalized period length estimate (clamped to 3-8 days).
    Use for phase calculations and predictions.
    
    Args:
        user_id: User ID
    
    Returns:
        Normalized period length estimate (3-8 days)
    """
    return estimate_period_length(user_id, normalized=True)

def ovulation_probability(offset_from_ovulation: float, ovulation_sd: float) -> float:
    """
    Calculate ovulation probability for a day based on offset from ovulation.
    This is used for phase determination (Ovulation phase should be 1-3 days).
    Uses only the normal distribution component, NOT the sperm survival kernel.
    
    Args:
        offset_from_ovulation: Days from predicted ovulation (negative = before, positive = after)
        ovulation_sd: Standard deviation of ovulation prediction
    
    Returns:
        Ovulation probability between 0 and 1 (normalized)
    """
    # Early return for dates far from ovulation (performance optimization)
    if abs(offset_from_ovulation) > 10:  # More than 10 days away
        return 0.0
    
    # Normal distribution component (ovulation probability only)
    p_ov = normal_pdf(offset_from_ovulation, 0.0, ovulation_sd)
    
    # Normalize to peak at 1.0 on ovulation day
    peak_prob = normal_pdf(0.0, 0.0, ovulation_sd)
    
    if peak_prob <= 0:
        return 0.0
    
    normalized_prob = p_ov / peak_prob
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, normalized_prob))

def select_ovulation_days(ovulation_sd: float, max_days: int = 3) -> set:
    """
    Select the Ovulation-phase day offsets (relative to predicted ovulation day 0).
    This should represent the ovulation event timing uncertainty (NOT the broader fertile window).
    
    Strategy:
    1. Always include day 0 (predicted ovulation date)
    2. Add adjacent days based on ovulation_probability as uncertainty increases
    
    Args:
        ovulation_sd: Standard deviation of ovulation prediction
        max_days: Maximum number of ovulation days (default 3, range 1-3)
    
    Returns:
        Set of day offsets from ovulation_date that are in ovulation phase
        e.g., {-1, 0, 1} means days -1, 0, +1 from ovulation
    """
    # Allow 3–5 days: regular cycles use narrower window, irregular use wider
    max_days = max(1, min(5, int(max_days)))

    selected_offsets = {0}
    if max_days == 1:
        return selected_offsets

    # Consider only near-ovulation event timing uncertainty
    candidates = []
    for offset in range(-2, 3):
        if offset == 0:
            continue
        candidates.append((offset, ovulation_probability(offset, ovulation_sd)))

    # Prefer high probability, then closer to 0
    candidates.sort(key=lambda x: (-x[1], abs(x[0])))

    for offset, _ in candidates:
        if len(selected_offsets) >= max_days:
            break
        test_set = selected_offsets | {offset}
        min_offset = min(test_set)
        max_offset = max(test_set)
        if all(i in test_set for i in range(min_offset, max_offset + 1)):
            selected_offsets.add(offset)

    # Enforce contiguity around 0 (e.g., {-1,0,1})
    min_offset = min(selected_offsets)
    max_offset = max(selected_offsets)
    contiguous = set(range(min_offset, max_offset + 1))
    if len(contiguous) > max_days:
        contiguous = set(sorted(contiguous, key=lambda x: abs(x))[:max_days])

    return contiguous

def get_ovulation_fertility_threshold(ovulation_sd: float) -> float:
    """
    Get adaptive fertility threshold for determining ovulation window.
    
    Ensures ovulation phase is 1-3 days maximum.
    Regular cycles (low uncertainty): higher threshold → 1-2 day window
    Irregular cycles (high uncertainty): lower threshold → 2-3 day window
    
    Threshold is monotonically decreasing with SD:
    - Lower SD (regular) → Higher threshold → Fewer days (1-2)
    - Higher SD (irregular) → Lower threshold → More days (2-3)
    
    Args:
        ovulation_sd: Standard deviation of ovulation prediction (uncertainty)
    
    Returns:
        Fertility probability threshold (monotonically decreasing from 0.85 to 0.70)
    """
    # Regular cycles: ovulation_sd < 2.0 → threshold 0.80-0.85 → 1-2 days
    # Irregular cycles: ovulation_sd >= 2.0 → threshold 0.70-0.80 → 2-3 days
    # Threshold decreases monotonically with SD
    
    if ovulation_sd < 1.5:
        # Very regular: very high threshold → narrow window (1 day)
        return 0.85
    elif ovulation_sd < 2.0:
        # Regular: high threshold → typical window (1-2 days)
        return 0.80
    elif ovulation_sd < 2.5:
        # Somewhat regular: medium-high threshold → wider window (2 days)
        return 0.75
    elif ovulation_sd < 3.0:
        # Moderate irregularity: medium threshold → wider window (2-3 days)
        return 0.72
    elif ovulation_sd < 3.5:
        # Irregular: lower threshold → wider window (3 days)
        return 0.70
    elif ovulation_sd < 4.0:
        # Very irregular: lower threshold → wider window (3 days)
        return 0.68
    elif ovulation_sd < 4.5:
        # Extremely irregular: even lower threshold → wider window (3 days)
        return 0.66
    elif ovulation_sd < 5.0:
        # Pathologically irregular: very low threshold → wider window (3 days)
        return 0.64
    else:
        # Extremely pathologically irregular: minimum threshold → maximum window (3 days)
        return 0.62

def fertility_probability(offset_from_ovulation: float, ovulation_sd: float) -> float:
    """
    Calculate fertility probability for a day based on offset from ovulation.
    Biologically accurate version that reflects real conception data.
    
    Medical accuracy:
    - Peak conception probability is typically day -1 or -2 (before ovulation)
    - Sperm survival decays over time (not binary)
    - Ovulation day (day 0) is important but not always the peak
    
    Args:
        offset_from_ovulation: Days from predicted ovulation (negative = before, positive = after)
        ovulation_sd: Standard deviation of ovulation prediction
    
    Returns:
        Fertility probability between 0 and 1
    """
    # Early return for dates far from ovulation (performance optimization)
    if abs(offset_from_ovulation) > 10:  # More than 10 days away
        return 0.0
    
    # Fertility is driven by sperm viability in the days BEFORE ovulation plus uncertainty in ovulation timing.
    # Medical intent:
    # - Day -2 and Day -1 should be highest probability days
    # - Steeper decay after Day -3 (older sperm viability drops quickly)
    # - Rapid drop after Day 0

    def _interp_weight(day: float) -> float:
        # Discrete conception-weight curve (normalized peak at -2/-1), linearly interpolated for floats.
        # Values are unitless and shaped for medically reasonable relative weighting.
        anchors = {
            -5.0: 0.05,
            -4.0: 0.15,
            -3.0: 0.40,
            -2.0: 1.00,
            -1.0: 1.00,
            0.0: 0.60,
            1.0: 0.05,
        }
        if day <= -5.0:
            return 0.0
        if day >= 1.0:
            return 0.0
        lo = math.floor(day)
        hi = math.ceil(day)
        lo = max(-5, min(1, int(lo)))
        hi = max(-5, min(1, int(hi)))
        if float(lo) not in anchors or float(hi) not in anchors:
            return 0.0
        if lo == hi:
            return anchors[float(lo)]
        t = (day - lo) / (hi - lo)
        return anchors[float(lo)] * (1 - t) + anchors[float(hi)] * t

    # "Ovulation ahead" factor: fertility on day d depends on ovulation occurring in the next 1-2 days.
    p_ov_ahead = max(
        ovulation_probability(offset_from_ovulation + 1.0, ovulation_sd),
        ovulation_probability(offset_from_ovulation + 2.0, ovulation_sd),
    )

    w = _interp_weight(offset_from_ovulation)
    raw = w * (0.5 + 0.5 * p_ov_ahead)

    # Normalize so that peak days (-2/-1) are 1.0 (before any confidence gating)
    peak = max(
        _interp_weight(-2.0) * (0.5 + 0.5 * max(ovulation_probability(-1.0, ovulation_sd), ovulation_probability(0.0, ovulation_sd))),
        _interp_weight(-1.0) * (0.5 + 0.5 * max(ovulation_probability(0.0, ovulation_sd), ovulation_probability(1.0, ovulation_sd))),
        1e-9,
    )
    prob = raw / peak

    # Confidence gate: extreme irregularity should reduce certainty
    if ovulation_sd > 4.0:
        prob = min(prob * 0.6, 0.35)

    return max(0.0, min(1.0, prob))

def estimate_cycle_start_sd(user_id: str, cycle_length_estimate: float) -> float:
    """
    Estimate cycle start uncertainty (SD) based on cycle length variance and logging consistency.
    
    Uncertainty increases when:
    - Cycle length variance is high (irregular cycles)
    - Periods are missed (gaps in logging)
    - Few observations available
    
    Args:
        user_id: User ID
        cycle_length_estimate: Current cycle length estimate
    
    Returns:
        Standard deviation of cycle start prediction (typically 0.5 to 3.0 days)
    """
    try:
        # Base uncertainty (for users with no data)
        base_sd = 1.5
        
        # Get cycle length history from period logs
        period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(60).execute()
        
        if not period_logs_response.data or len(period_logs_response.data) < 2:
            # Not enough data, use base uncertainty
            return base_sd
        
        # Group consecutive dates into periods (period starts)
        dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d") for log in period_logs_response.data if log.get("date")])
        
        if len(dates) < 2:
            return base_sd
        
        # Find period starts (first day of each period = dates with gap > 1 day from previous)
        period_starts = [dates[0]]  # First date is always a period start
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            if gap > 1:  # Gap > 1 day indicates new period start
                period_starts.append(dates[i])
        
        if len(period_starts) < 2:
            # Not enough periods, use base uncertainty
            return base_sd
        
        # Calculate cycle lengths (gaps between period starts)
        cycle_lengths = []
        for i in range(1, len(period_starts)):
            cycle_length = (period_starts[i] - period_starts[i-1]).days
            if 21 <= cycle_length <= 45:  # Valid cycle length range
                cycle_lengths.append(cycle_length)
        
        if len(cycle_lengths) < 2:
            # Not enough cycles, use base uncertainty
            return base_sd
        
        # Calculate cycle length variance
        cycle_mean = sum(cycle_lengths) / len(cycle_lengths)
        if len(cycle_lengths) > 1:
            variance = sum((x - cycle_mean) ** 2 for x in cycle_lengths) / (len(cycle_lengths) - 1)
            cycle_sd = math.sqrt(variance)
        else:
            cycle_sd = 0.0
        
        # Calculate logging consistency (gaps between period starts)
        # Large gaps between period starts indicate missed periods
        max_cycle_length = max(cycle_lengths) if cycle_lengths else 0
        
        # Estimate missed periods (cycle lengths > 35 days likely indicate missed periods)
        missed_periods_penalty = 0.0
        if max_cycle_length > 35:
            # Likely missed at least one period
            missed_periods_penalty = min(1.0, (max_cycle_length - 35) / 30.0)  # Penalty up to 1.0
        
        # Calculate adaptive SD
        # Base: 0.5 (very regular, consistent logging)
        # Cycle variance component: cycle_sd / 5.0 (normalize to ~0-1 range)
        # Missed periods component: missed_periods_penalty (0-1)
        # Sample size component: fewer observations = more uncertainty
        
        cycle_variance_component = min(1.5, cycle_sd / 5.0)  # Cap at 1.5 days
        missed_periods_component = missed_periods_penalty * 1.0  # Up to 1.0 day
        sample_size_component = max(0.0, (5 - len(cycle_lengths)) / 5.0) * 0.5  # Up to 0.5 days if < 5 cycles
        
        adaptive_sd = 0.5 + cycle_variance_component + missed_periods_component + sample_size_component
        
        # Clamp to reasonable range (0.5 to 3.0 days)
        adaptive_sd = max(0.5, min(3.0, adaptive_sd))
        
        return adaptive_sd
    
    except Exception as e:
        print(f"⚠️ Error estimating cycle_start_sd: {str(e)}")
        # Fallback to base uncertainty
        return 1.5

def predict_ovulation(
    cycle_start_date: str,
    cycle_length_estimate: float,
    luteal_mean: float,
    luteal_sd: float,
    cycle_start_sd: Optional[float] = None,
    user_id: Optional[str] = None
) -> tuple[str, float]:
    """
    Predict ovulation date and uncertainty.
    
    Args:
        cycle_start_date: Start date of cycle (YYYY-MM-DD)
        cycle_length_estimate: Estimated cycle length
        luteal_mean: Mean luteal phase length
        luteal_sd: Standard deviation of luteal phase
        cycle_start_sd: Standard deviation of cycle start prediction (optional, will be estimated if None)
        user_id: User ID (required if cycle_start_sd is None, for adaptive estimation)
    
    Returns:
        Tuple of (ovulation_date_str, ovulation_sd)
    """
    cycle_start = datetime.strptime(cycle_start_date, "%Y-%m-%d")
    
    # Estimate cycle_start_sd if not provided
    if cycle_start_sd is None:
        if user_id is None:
            cycle_start_sd = 1.0  # Default fallback
        else:
            cycle_start_sd = estimate_cycle_start_sd(user_id, cycle_length_estimate)
    
    # Ovulation date = cycle_start + (cycle_length - luteal_mean)
    ovulation_offset = int(cycle_length_estimate - luteal_mean)  # Store as integer
    ovulation_date = cycle_start + timedelta(days=ovulation_offset)
    
    # Combined uncertainty
    ovulation_sd = math.sqrt(cycle_start_sd ** 2 + luteal_sd ** 2)
    
    return ovulation_date.strftime("%Y-%m-%d"), ovulation_sd, ovulation_offset

def update_luteal_estimate(user_id: str, observed_luteal_length: float, has_markers: bool = False) -> None:
    """
    Update user's luteal phase estimate when period is logged.
    
    ⚠️ IMPORTANT: This function should only be called with high-confidence ovulation predictions.
    Caller must verify ovulation_sd <= 1.5 before calling this function to avoid training on:
    - Incorrect ovulation predictions (stress cycles, PCOS patterns)
    - Anovulatory cycles
    - Missed ovulation
    - Early app usage (limited data)
    
    Args:
        user_id: User ID
        observed_luteal_length: Observed luteal length (period_start - predicted_ovulation)
        has_markers: Whether LH/BBT markers exist (affects weighting)
    """
    try:
        # Get current observations
        user_response = supabase.table("users").select("luteal_observations, luteal_mean, luteal_sd").eq("id", user_id).execute()
        
        if user_response.data and user_response.data[0].get("luteal_observations"):
            import json
            observations = json.loads(user_response.data[0]["luteal_observations"])
            old_mean = user_response.data[0].get("luteal_mean", 14.0)
        else:
            observations = []
            old_mean = 14.0
        
        # Add new observation
        observations.append(observed_luteal_length)
        # Keep only last 12 observations
        if len(observations) > 12:
            observations = observations[-12:]
        
        # Proper Bayesian smoothing with sample-size weighting
        n = len(observations)
        k = 5  # Prior strength constant (equivalent to having 5 prior observations)
        
        # Adjust k based on marker presence (markers = more reliable)
        if has_markers:
            k = 3  # Lower k = trust data more when markers exist
        
        # Weight increases with number of observations: weight = n / (n + k)
        weight = n / (n + k)
        
        # Calculate observed mean from all observations
        obs_mean = sum(observations) / n
        
        # Weighted combination: more observations → trust data more
        updated_mean = (1 - weight) * old_mean + weight * obs_mean
        
        # Calculate SD
        if len(observations) > 1:
            obs_mean = sum(observations) / len(observations)
            variance = sum((x - obs_mean) ** 2 for x in observations) / (len(observations) - 1)
            updated_sd = math.sqrt(variance)
        else:
            updated_sd = 2.0
        
        # Store in database
        import json
        supabase.table("users").update({
            "luteal_observations": json.dumps(observations),
            "luteal_mean": updated_mean,
            "luteal_sd": updated_sd
        }).eq("id", user_id).execute()
        
        print(f"Updated luteal estimate for user {user_id}: mean={updated_mean:.2f}, sd={updated_sd:.2f}")
    except Exception as e:
        print(f"Warning: Failed to update luteal estimate: {str(e)}")

def update_cycle_length_bayesian(user_id: str, new_cycle_length: int) -> int:
    """
    Update cycle length using proper Bayesian smoothing with sample-size weighting.
    
    Uses sample-size weighting: weight = n / (n + k)
    More observations → trust new data more
    
    Returns the updated cycle length.
    """
    try:
        # Get current cycle length and count of observations
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        
        # Try to get number of cycle observations (approximate from past cycles)
        # For simplicity, we'll use a fixed k, but in practice you'd count actual observations
        # This is a single update, so we treat it as adding 1 observation
        k = 3  # Prior strength constant (adapt faster to new normal)
        n = 1  # This is 1 new observation
        
        if user_response.data and user_response.data[0].get("cycle_length"):
            old_cycle_length = int(user_response.data[0]["cycle_length"])
            # Proper Bayesian: weight increases with observations
            weight = n / (n + k)
            updated_cycle_length = int((1 - weight) * old_cycle_length + weight * new_cycle_length)
        else:
            updated_cycle_length = new_cycle_length
        
        supabase.table("users").update({
            "cycle_length": updated_cycle_length
        }).eq("id", user_id).execute()
        
        print(f"Updated cycle_length using Bayesian smoothing: {old_cycle_length if user_response.data else 'N/A'} -> {updated_cycle_length}")
        return updated_cycle_length
    except Exception as e:
        print(f"Warning: Failed to update cycle_length with Bayesian smoothing: {str(e)}")
        return new_cycle_length

def store_cycle_phase_map(
    user_id: str, 
    phase_mappings: List[Dict],
    update_future_only: bool = False,
    current_date: Optional[str] = None
):
    """
    DEPRECATED: This function is now a no-op.
    
    Phase mappings are now calculated on-demand in RAM and not stored in the database.
    This eliminates the 181+ individual database upserts that were causing Errno 35 errors.
    
    Args:
        user_id: User ID (ignored)
        phase_mappings: List of phase mappings (ignored)
        update_future_only: Ignored
        current_date: Ignored
    """
    # NO-OP: Phase mappings are now computed on-demand, not stored in DB
    print(f"⚠️ store_cycle_phase_map() called but is now disabled (compute-on-demand architecture). "
          f"Phase mappings are calculated in RAM when requested.")
    return

def get_effective_period_end(user_id: str, start_date: str):
    """
    Get effective period end date for a cycle start date.
    
    This is the core logic that determines the boundary of the "Period" phase.
    Prioritizes manual end date if user clicked "Period Ended".
    Otherwise uses rolling period average (AI estimate).
    
    Args:
        user_id: User ID
        start_date: Period start date (YYYY-MM-DD)
    
    Returns:
        Effective end date as date object
    """
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        
        # Get period log for this start date
        log_response = supabase.table("period_logs").select("*").eq("user_id", user_id).eq("date", start_date).limit(1).execute()
        
        if log_response.data and log_response.data[0].get("end_date"):
            # User manually told us when it ended (is_manual_end = True)
            end_date_str = log_response.data[0]["end_date"]
            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            print(f"✅ Using manual end date for {start_date}: {end_date_str}")
            return end_date_obj
        else:
            # User hasn't logged end yet, or it was auto-closed
            # Use normalized estimate_period_length (3-8 days) to avoid importing period_service in hot path.
            estimated_days = int(round(max(3.0, min(8.0, estimate_period_length(user_id, normalized=True)))))
            end_date_obj = start_date_obj + timedelta(days=estimated_days - 1)
            print(f"📊 Using rolling period average ({estimated_days} days) for {start_date}")
            return end_date_obj
    
    except Exception as e:
        print(f"Error getting effective period end: {str(e)}")
        # Fallback to estimate
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        estimated_days = int(round(max(3.0, min(8.0, estimate_period_length(user_id, normalized=True)))))
        return start_date_obj + timedelta(days=estimated_days - 1)


def get_period_range(user_id: str, cycle_start: str) -> tuple:
    """
    Get period range (start and end dates) for a cycle start date.
    
    Uses get_effective_period_end() internally.
    
    Args:
        user_id: User ID
        cycle_start: Cycle start date (YYYY-MM-DD)
    
    Returns:
        Tuple of (start_date, end_date) as date objects
    """
    try:
        cycle_start_obj = datetime.strptime(cycle_start, "%Y-%m-%d").date()
        end_date_obj = get_effective_period_end(user_id, cycle_start)
        return cycle_start_obj, end_date_obj
    
    except Exception as e:
        print(f"Error getting period range: {str(e)}")
        # Fallback
        cycle_start_obj = datetime.strptime(cycle_start, "%Y-%m-%d").date()
        estimated_days = int(round(max(3.0, min(8.0, estimate_period_length(user_id, normalized=True)))))
        return cycle_start_obj, cycle_start_obj + timedelta(days=estimated_days - 1)


def get_period_phase_day_from_logs(user_id: str, period_logs: List[Dict], date_str: str) -> Optional[str]:
    """
    If date_str falls within any period log (start..end), return phase_day_id e.g. 'p1', 'p2'.
    Otherwise return None. Uses same period-end logic as calculate_phase_for_date_range (estimate_period_length when end_date missing).
    """
    try:
        check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        for period_log in period_logs or []:
            period_start_str = period_log.get("date")
            if not period_start_str:
                continue
            try:
                period_start = datetime.strptime(period_start_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if period_log.get("end_date"):
                try:
                    period_end = datetime.strptime(period_log["end_date"], "%Y-%m-%d").date()
                except Exception:
                    period_length_days = int(round(max(3.0, min(8.0, estimate_period_length(user_id, normalized=True)))))
                    period_end = period_start + timedelta(days=period_length_days - 1)
            else:
                period_length_days = int(round(max(3.0, min(8.0, estimate_period_length(user_id, normalized=True)))))
                period_end = period_start + timedelta(days=period_length_days - 1)
            if period_start <= check_date <= period_end:
                day_in_period = (check_date - period_start).days + 1
                return f"p{day_in_period}"
        return None
    except Exception:
        return None


def is_date_in_logged_period(user_id: str, date: str) -> bool:
    """
    Check if a date falls within any logged period range.
    
    Uses actual end dates if available, otherwise uses estimated period length.
    
    Args:
        user_id: User ID
        date: Date to check (YYYY-MM-DD)
    
    Returns:
        True if date is within a logged period, False otherwise
    """
    try:
        # timedelta is already imported at module level
        
        check_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        # Get all period logs with their end dates
        period_logs_response = supabase.table("period_logs").select("date, end_date").eq("user_id", user_id).order("date", desc=True).execute()
        
        if not period_logs_response.data:
            return False
        
        # Check if date falls within any logged period range
        for period_log in period_logs_response.data:
            period_start = datetime.strptime(period_log["date"], "%Y-%m-%d").date()
            
            if period_log.get("end_date"):
                # Use actual end date
                period_end = datetime.strptime(period_log["end_date"], "%Y-%m-%d").date()
            else:
                # Use estimated period length
                period_length = estimate_period_length(user_id, normalized=True)
                period_length_days = int(round(max(3.0, min(8.0, period_length))))
                period_end = period_start + timedelta(days=period_length_days - 1)
            
            if period_start <= check_date <= period_end:
                return True
        
        return False
    
    except Exception as e:
        print(f"Error checking if date is in logged period: {str(e)}")
        return False

def get_user_phase_day(user_id: str, date: Optional[str] = None, prefer_actual: bool = True) -> Optional[Dict]:
    """
    Get phase-day information for a specific date (defaults to today).
    
    Args:
        user_id: User ID
        date: Date to check (YYYY-MM-DD), defaults to today
        prefer_actual: If True, prefer actual logged data over predicted. If False, return any available data.
    
    Returns:
        Dict with phase, phase_day_id, or None if not found
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # First, check if date is within a logged period (actual data)
        is_actual = is_date_in_logged_period(user_id, date)
        
        # Get data from database
        response = supabase.table("user_cycle_days").select("*").eq("user_id", user_id).eq("date", date).execute()
        
        if response.data:
            phase_data = response.data[0]
            
            # If prefer_actual is True and date is not in logged period, 
            # still return the data (it's predicted, but we'll use it as fallback)
            # The key is: if date IS in logged period, we know it's actual
            # If date is NOT in logged period, it's predicted, but we still return it if prefer_actual=False
            # or if no actual data exists
            if prefer_actual and not is_actual:
                # Date is not in logged period, but we have predicted data
                # Return it anyway (this is the fallback behavior)
                return phase_data
            else:
                # Either actual data or we don't care about actual vs predicted
                return phase_data
        
        return None
    
    except Exception as e:
        return None

def get_predicted_cycle_starts_from_db(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[str]:
    """
    Get predicted cycle start dates from database (p1 days).
    These are more accurate than modulo math as they account for actual cycle variations.
    
    Args:
        user_id: User ID
        start_date: Optional start date to filter (YYYY-MM-DD)
        end_date: Optional end date to filter (YYYY-MM-DD)
    
    Returns:
        List of cycle start dates (YYYY-MM-DD) sorted chronologically
    """
    try:
        query = supabase.table("user_cycle_days").select("date").eq("user_id", user_id).eq("phase_day_id", "p1")
        
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)
        
        response = query.order("date").execute()
        
        if response.data:
            cycle_starts = [item["date"] for item in response.data]
            return cycle_starts
        
        return []
    except Exception as e:
        print(f"Error getting predicted cycle starts from DB: {str(e)}")
        return []

def calculate_rolling_cycle_starts(last_period_date: str, cycle_length: float, start_date: datetime, end_date: datetime, max_cycles: int = 12) -> List[datetime]:
    """
    Calculate rolling cycle starts that account for cycle length variations.
    Uses adaptive cycle length estimation instead of fixed modulo math.
    
    Args:
        last_period_date: Last known period date (YYYY-MM-DD)
        cycle_length: Average cycle length (can vary)
        start_date: Start of date range
        end_date: End of date range
        max_cycles: Maximum number of cycles to generate
    
    Returns:
        List of cycle start dates (datetime objects)
    """
    last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
    cycle_starts = [last_period]
    
    # Generate cycles forward until we cover the end_date
    current_cycle_start = last_period
    cycles_generated = 0
    
    while current_cycle_start <= end_date and cycles_generated < max_cycles:
        # Add cycle_length days (can vary slightly)
        next_cycle_start = current_cycle_start + timedelta(days=int(cycle_length))
        cycle_starts.append(next_cycle_start)
        current_cycle_start = next_cycle_start
        cycles_generated += 1
    
    # Also generate cycles backward if needed (for start_date before last_period)
    if start_date < last_period:
        current_cycle_start = last_period
        cycles_generated = 0
        while current_cycle_start > start_date and cycles_generated < max_cycles:
            # Go backward by cycle_length
            prev_cycle_start = current_cycle_start - timedelta(days=int(cycle_length))
            cycle_starts.insert(0, prev_cycle_start)
            current_cycle_start = prev_cycle_start
            cycles_generated += 1
    
    return sorted(cycle_starts)

def predict_cycle_starts_from_period_logs(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None, max_cycles: int = 12) -> List[datetime]:
    """
    Predict future cycle start dates from period logs using adaptive cycle length estimation.
    
    This is medically credible because it:
    - Uses actual period log data (most accurate source)
    - Calculates cycle lengths from real observations
    - Uses Bayesian smoothing for cycle length estimation
    - Accounts for cycle length variance (irregular cycles)
    - Predicts forward from most recent period
    
    Args:
        user_id: User ID
        start_date: Optional start date for predictions (YYYY-MM-DD)
        end_date: Optional end date for predictions (YYYY-MM-DD)
        max_cycles: Maximum number of cycles to predict (default 12)
    
    Returns:
        List of predicted cycle start dates (datetime objects) sorted chronologically
    """
    try:
        # Get period logs (all dates where user logged period)
        period_logs_response = supabase.table("period_logs").select("date").eq("user_id", user_id).order("date", desc=True).limit(60).execute()
        
        if not period_logs_response.data or len(period_logs_response.data) < 1:
            # No period logs - use last_period_date and cycle_length from user table
            user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
            if user_response.data and user_response.data[0].get("last_period_date"):
                last_period = datetime.strptime(user_response.data[0]["last_period_date"], "%Y-%m-%d")
                cycle_length = float(user_response.data[0].get("cycle_length", 28))
                
                # Generate rolling predictions
                today = datetime.now()
                if not start_date:
                    start_date_obj = datetime(today.year, today.month - 1, 1)
                else:
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                if not end_date:
                    end_date_obj = datetime(today.year, today.month + 2, 0)
                else:
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                
                return calculate_rolling_cycle_starts(
                    user_response.data[0]["last_period_date"],
                    cycle_length,
                    start_date_obj,
                    end_date_obj,
                    max_cycles
                )
            return []
        
        # Group consecutive dates into periods (period starts)
        dates = sorted([datetime.strptime(log["date"], "%Y-%m-%d") for log in period_logs_response.data if log.get("date")])
        
        if len(dates) < 1:
            return []
        
        # MEDICAL FIX: Find period starts with proper validation
        # A new period start must be at least MIN_CYCLE_DAYS (21 days) from the previous period start
        # This prevents multiple periods in one cycle (medically impossible)
        MIN_CYCLE_DAYS = 21  # Minimum cycle length (medically accurate)
        MAX_CYCLE_DAYS = 45  # Maximum cycle length (medically accurate)
        
        period_starts = [dates[0]]  # First date is always a period start
        
        # Get estimated period length to check if dates are within the same period
        period_length = estimate_period_length(user_id)
        period_length_days = int(round(max(3.0, min(8.0, period_length))))
        
        for i in range(1, len(dates)):
            current_date = dates[i]
            last_period_start = period_starts[-1]
            
            # Calculate gap from last period start
            gap_from_last_period = (current_date - last_period_start).days
            
            # Check if this date is within the previous period range (same period)
            period_end = last_period_start + timedelta(days=period_length_days - 1)
            is_within_previous_period = last_period_start <= current_date <= period_end
            
            if is_within_previous_period:
                # This date is within the previous period - skip it (not a new period start)
                # User might have logged multiple days of the same period
                print(f"⚠️ Date {current_date.strftime('%Y-%m-%d')} is within previous period ({last_period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}), skipping as duplicate")
                continue
            
            # Check if gap is at least minimum cycle length (new period start)
            if gap_from_last_period >= MIN_CYCLE_DAYS:
                # Valid new period start (at least 21 days from previous)
                period_starts.append(current_date)
                print(f"✅ New period start: {current_date.strftime('%Y-%m-%d')} (gap: {gap_from_last_period} days from {last_period_start.strftime('%Y-%m-%d')})")
            elif gap_from_last_period < MIN_CYCLE_DAYS:
                # Gap is too short - this might be:
                # 1. A duplicate log (same period, different day)
                # 2. An error in logging
                # Skip it to prevent multiple periods in one cycle
                print(f"⚠️ Date {current_date.strftime('%Y-%m-%d')} is only {gap_from_last_period} days from last period start {last_period_start.strftime('%Y-%m-%d')} (minimum {MIN_CYCLE_DAYS} days required). Skipping to prevent duplicate periods.")
                continue
        
        if len(period_starts) < 1:
            return []
        
        # Calculate cycle lengths (gaps between period starts)
        # MEDICAL FIX: Validate all cycle lengths are in valid range (21-45 days)
        cycle_lengths = []
        validated_period_starts = [period_starts[0]]  # First period is always valid
        
        for i in range(1, len(period_starts)):
            cycle_length = (period_starts[i] - period_starts[i-1]).days
            
            if MIN_CYCLE_DAYS <= cycle_length <= MAX_CYCLE_DAYS:
                # Valid cycle length
                cycle_lengths.append(float(cycle_length))
                validated_period_starts.append(period_starts[i])
                print(f"✅ Valid cycle: {cycle_length} days from {period_starts[i-1].strftime('%Y-%m-%d')} to {period_starts[i].strftime('%Y-%m-%d')}")
            elif cycle_length < MIN_CYCLE_DAYS:
                # Too short - likely duplicate or error, skip this period start
                print(f"⚠️ Invalid cycle length: {cycle_length} days (minimum {MIN_CYCLE_DAYS} days). Skipping period start {period_starts[i].strftime('%Y-%m-%d')}")
                continue
            elif cycle_length > MAX_CYCLE_DAYS:
                # Too long - likely missed period(s)
                # Mark as missed period but still use it for calculations
                missed_periods = int((cycle_length - MAX_CYCLE_DAYS) / MAX_CYCLE_DAYS) + 1
                print(f"⚠️ Long cycle: {cycle_length} days (likely {missed_periods} missed period(s)). Including but marking for review.")
                cycle_lengths.append(float(cycle_length))
                validated_period_starts.append(period_starts[i])
        
        # Use validated period starts (removed duplicates/invalid cycles)
        period_starts = validated_period_starts
        
        # Get user's current cycle_length estimate
        user_response = supabase.table("users").select("cycle_length").eq("id", user_id).execute()
        current_cycle_length = float(user_response.data[0].get("cycle_length", 28)) if user_response.data else 28.0
        
        # OUTLIER DETECTION: Statistical (Mean ± 2×SD) + manual flags on period_start_logs
        # Do not auto-clear is_outlier in DB (user / API may set it for Bayesian exclusion).
        non_outlier_cycles = []
        if len(cycle_lengths) > 0:
            outlier_flags = {}
            try:
                _or = supabase.table("period_start_logs").select("start_date, is_outlier").eq("user_id", user_id).execute()
                for row in (_or.data or []):
                    sd = row.get("start_date")
                    if sd:
                        outlier_flags[str(sd)] = bool(row.get("is_outlier"))
            except Exception:
                pass

            # Calculate statistics
            cycle_mean = sum(cycle_lengths) / len(cycle_lengths)
            if len(cycle_lengths) > 1:
                variance = sum((x - cycle_mean) ** 2 for x in cycle_lengths) / (len(cycle_lengths) - 1)
                cycle_sd = math.sqrt(variance)
            else:
                cycle_sd = 2.0  # Default SD if only one cycle
            
            # Outlier threshold: Mean ± 2×SD
            outlier_threshold_low = cycle_mean - (2 * cycle_sd)
            outlier_threshold_high = cycle_mean + (2 * cycle_sd)
            
            print(f"📊 Cycle statistics: mean={cycle_mean:.1f}, sd={cycle_sd:.1f}, outlier_range=[{outlier_threshold_low:.1f}, {outlier_threshold_high:.1f}]")
            
            for i in range(1, len(period_starts)):
                cycle_length = (period_starts[i] - period_starts[i-1]).days
                cycle_start_str = period_starts[i - 1].strftime("%Y-%m-%d")
                manual_outlier = outlier_flags.get(cycle_start_str, False)
                statistical_outlier = cycle_length < outlier_threshold_low or cycle_length > outlier_threshold_high
                
                if statistical_outlier:
                    print(f"⚠️ Cycle {cycle_start_str} to {period_starts[i].strftime('%Y-%m-%d')} ({cycle_length} days) is OUTLIER (outside Mean ± 2×SD)")
                    try:
                        supabase.table("period_start_logs").update({"is_outlier": True}).eq("user_id", user_id).eq("start_date", cycle_start_str).execute()
                    except Exception as e:
                        print(f"⚠️ Could not mark cycle as outlier: {str(e)}")
                
                exclude_from_mean = manual_outlier or statistical_outlier
                if not exclude_from_mean and cycle_length in cycle_lengths:
                    non_outlier_cycles.append(cycle_length)
            
            # Use only non-outlier cycles for Bayesian smoothing
            if len(non_outlier_cycles) > 0:
                cycle_lengths = non_outlier_cycles
                print(f"✅ Using {len(cycle_lengths)} non-outlier cycles for estimation (excluded outliers)")
        
        # Bayesian smoothing for cycle length estimate (using only non-outlier cycles)
        if len(cycle_lengths) > 0:
            # Use recent cycle lengths (last 12) for better accuracy
            recent_cycles = cycle_lengths[-12:]
            obs_mean = sum(recent_cycles) / len(recent_cycles)
            
            # Bayesian smoothing: weight increases with observations
            k = 5  # Prior strength
            n = len(recent_cycles)
            weight = n / (n + k)
            estimated_cycle_length = (1 - weight) * current_cycle_length + weight * obs_mean
        else:
            estimated_cycle_length = current_cycle_length
        
        # Clamp to valid range
        estimated_cycle_length = max(21.0, min(45.0, estimated_cycle_length))
        
        # Most recent period start
        most_recent_period = period_starts[-1]
        
        # Determine date range
        today = datetime.now()
        if not start_date:
            start_date_obj = datetime(today.year, today.month - 1, 1)
        else:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        if not end_date:
            end_date_obj = datetime(today.year, today.month + 2, 0)
        else:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Start with ALL actual logged period starts (regardless of date range)
        # This ensures past logged periods are always included for accurate calculations
        predicted_starts = list(period_starts)  # Copy all logged period starts
        
        # Predict BACKWARD from earliest logged period (if start_date is before it)
        earliest_logged = period_starts[0]
        if start_date_obj < earliest_logged:
            current_start = earliest_logged
            cycles_predicted = 0
            # Predict backward
            while current_start >= start_date_obj and cycles_predicted < max_cycles:
                if current_start not in predicted_starts:
                    predicted_starts.append(current_start)
                    cycles_predicted += 1
                # Subtract estimated cycle length to go backward
                current_start -= timedelta(days=int(round(estimated_cycle_length)))
        
        # Predict FORWARD from most recent period
        # MEDICAL FIX: Ensure predicted cycles maintain minimum 21-day spacing
        current_start = most_recent_period
        cycles_predicted = 0
        while current_start <= end_date_obj and cycles_predicted < max_cycles:
            # Validate this predicted start is at least MIN_CYCLE_DAYS from previous
            if predicted_starts:
                last_start = predicted_starts[-1]
                gap = (current_start - last_start).days
                if gap < MIN_CYCLE_DAYS:
                    # Adjust to maintain minimum cycle length
                    current_start = last_start + timedelta(days=MIN_CYCLE_DAYS)
                    print(f"⚠️ Adjusted predicted cycle start to maintain minimum {MIN_CYCLE_DAYS}-day cycle: {current_start.strftime('%Y-%m-%d')}")
            
            if current_start not in predicted_starts:
                predicted_starts.append(current_start)
                cycles_predicted += 1
            
            # Add estimated cycle length (use integer days, but ensure minimum)
            next_start = current_start + timedelta(days=int(round(estimated_cycle_length)))
            # Ensure next cycle is at least MIN_CYCLE_DAYS away
            if (next_start - current_start).days < MIN_CYCLE_DAYS:
                next_start = current_start + timedelta(days=MIN_CYCLE_DAYS)
            current_start = next_start
        
        # Filter to only include cycle starts within the date range
        # BUT: Keep all logged periods even if outside range (they're needed for calculations)
        filtered_starts = []
        for s in predicted_starts:
            if s in period_starts:
                # Always include logged periods (even if outside range) - needed for accurate calculations
                filtered_starts.append(s)
            elif start_date_obj <= s <= end_date_obj:
                # Include predicted periods only if in range
                filtered_starts.append(s)
        
        print(f"📊 Cycle starts: {len(period_starts)} logged, {len(predicted_starts)} total (including predictions), {len(filtered_starts)} returned (all logged + predictions in range)")
        
        return sorted(filtered_starts)
    
    except Exception as e:
        print(f"Error predicting cycle starts from period logs: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def _apply_late_anchor_shift_to_cycle_starts(
    cycle_starts: List[datetime],
    cycle_metadata: Dict[datetime, Dict],
    shift_days: int,
    min_cycle_days: int = 21,
) -> Tuple[List[datetime], Dict[datetime, Dict]]:
    """
    Shift future *predicted* cycle starts forward when the next period is late.
    Real logged anchors and virtual back-fill anchors are not moved.
    """
    if shift_days <= 0 or not cycle_starts:
        return cycle_starts, cycle_metadata

    last_real: Optional[datetime] = None
    for cs in sorted(cycle_starts):
        if cycle_metadata.get(cs, {}).get("source") == "real":
            last_real = cs

    bucket: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
    for cs in sorted(cycle_starts):
        meta = dict(cycle_metadata.get(cs, {}))
        src = meta.get("source")
        if src == "predicted" and (last_real is None or cs > last_real):
            ncs = cs + timedelta(days=shift_days)
        else:
            ncs = cs
        key = ncs.strftime("%Y-%m-%d")
        if key not in bucket:
            bucket[key] = (ncs, meta)
        else:
            _existing_ncs, old_meta = bucket[key]
            if meta.get("source") == "real" or (
                meta.get("source") == "predicted" and old_meta.get("source") != "real"
            ):
                bucket[key] = (ncs, meta)

    sorted_pairs = sorted(bucket.values(), key=lambda p: p[0])
    sorted_cs = [p[0] for p in sorted_pairs]
    fixed_meta: Dict[datetime, Dict] = {p[0]: p[1] for p in sorted_pairs}

    final_cs: List[datetime] = [sorted_cs[0]]
    final_meta: Dict[datetime, Dict] = {sorted_cs[0]: fixed_meta[sorted_cs[0]]}
    for idx in range(1, len(sorted_cs)):
        cur = sorted_cs[idx]
        prev = final_cs[-1]
        gap = (cur - prev).days
        src = fixed_meta[cur].get("source", "unknown")
        if src == "real" or gap >= min_cycle_days:
            final_cs.append(cur)
            final_meta[cur] = fixed_meta[cur]
        else:
            logger.debug(
                "Late-anchor shift: dropping predicted start %s (gap=%s < %s)",
                cur.strftime("%Y-%m-%d"),
                gap,
                min_cycle_days,
            )

    return final_cs, final_meta


def calculate_phase_for_date_range(
    user_id: str,
    last_period_date: Optional[str],
    cycle_length: int,
    period_logs: Optional[List[Dict]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    diagnostic_log: Optional[List[Dict[str, Any]]] = None,
    late_anchor_shift_days: int = 0,
    client_today_str: Optional[str] = None,
) -> List[Dict]:
    """
    Calculate phase mappings for a date range using adaptive, medically credible algorithms.
    
    CONTRACT: period_logs must be pre-sorted by date (e.g. .order("date") in the database query).
    No redundant .sort() or grouping is performed here; pass in sorted data to save CPU.
    
    ZERO-DATA STATE (Log to See Data):
    - If user has no data in period_logs AND no last_period_date, returns [] (empty calendar).
    - No virtual/fallback cycles are generated from today's date.
    
    STATELESS PURE RAM VERSION:
    - Accepts period_logs as input (caller must provide sorted by date)
    - All calculations performed in memory
    - No writes to user_cycle_days table
    
    ANCHOR LOGIC (when user has logged data):
    - For each current_date: find the nearest "Real" cycle start (the Anchor).
    - Dates before the first logged period are not assigned a phase (no Predicted-Backward fill).
    - If date is between two real logs with a gap > 45 days: projected "Predicted" starts fill the gap (forward only).
    - Phase (P1-P5, F1-F10, O1-O4, L1-L14) is calculated from day-in-cycle relative to that anchor.
    
    This is the PRIMARY method for cycle prediction. It uses:
    - Adaptive luteal phase estimation (Bayesian smoothing from actual observations)
    - Adaptive period length estimation (from period logs)
    - Ovulation prediction with uncertainty quantification
    - Fertility probability calculations (biologically accurate)
    - Cycle start prediction from period logs (most accurate)
    
    Medical Credibility:
    - All algorithms are based on established medical research
    - Uses actual user data (period logs) for predictions
    - Adaptive learning improves accuracy over time
    - Confidence gating prevents unreliable predictions
    - Fertility probabilities reflect biological reality (sperm survival, peak fertility timing)
    
    Args:
        user_id: User ID (for adaptive estimates like luteal_mean, period_length)
        last_period_date: Last known period date (YYYY-MM-DD), or None when no data (returns [])
        cycle_length: Estimated cycle length (days)
        period_logs: Period log dicts with "date" (and optional "end_date"); sorted by date. Defaults to [].
        start_date: Optional start date for calculation range (YYYY-MM-DD)
        end_date: Optional end date for calculation range (YYYY-MM-DD)
        late_anchor_shift_days: Forward shift (days) applied only to predicted future cycle starts
            (late-period handler); real logs and virtual back-fill are unchanged.
    
    Returns:
        List of dicts with date, phase, phase_day_id, fertility_prob, and other fields; [] when no data.
    """
    try:
        if period_logs is None:
            period_logs = []

        # ZERO-DATA: No period_logs and no last_period_date -> empty calendar (Log to See Data)
        has_logs = bool(period_logs and len(period_logs) > 0)
        has_last_period = bool(last_period_date and (isinstance(last_period_date, str) and last_period_date.strip()))
        print(f"DEBUG: Calculating phases for User {user_id} (has_logs={has_logs}, has_last_period={has_last_period}), last_period_date={last_period_date}")
        if not has_logs and not has_last_period:
            print("📭 Zero data: no period_logs and no last_period_date - returning empty phase map")
            return []

        # Default date range: 3 months around "user today" (client-provided or IST fallback).
        # IMPORTANT: never use naive datetime.now() for calendar-day decisions.
        today_d = get_user_today(client_today_str)
        if not start_date:
            start_date_obj = datetime(today_d.year, today_d.month - 1, 1)
        else:
            if isinstance(start_date, str):
                start_date_obj = datetime.strptime(start_date[:10], "%Y-%m-%d")
            elif hasattr(start_date, "year") and hasattr(start_date, "month"):
                d = start_date.date() if hasattr(start_date, "date") else start_date
                start_date_obj = datetime(d.year, d.month, d.day)
            else:
                start_date_obj = datetime.strptime(str(start_date)[:10], "%Y-%m-%d")

        if not end_date:
            end_date_obj = datetime(today_d.year, today_d.month + 2, 0)
        else:
            if isinstance(end_date, str):
                end_date_obj = datetime.strptime(end_date[:10], "%Y-%m-%d")
            elif hasattr(end_date, "year") and hasattr(end_date, "month"):
                d = end_date.date() if hasattr(end_date, "date") else end_date
                end_date_obj = datetime(d.year, d.month, d.day)
            else:
                end_date_obj = datetime.strptime(str(end_date)[:10], "%Y-%m-%d")
        
        # Hoist statistics: compute once at start, pass into loops (no per-day recalculation)
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        period_days = estimate_period_length(user_id, normalized=True)
        period_length_days = int(round(max(3.0, min(8.0, period_days))))
        
        phase_mappings = []
        current_date = start_date_obj
        
        # Initialize phase counters dictionary for tracking phase days per cycle
        phase_counters_by_cycle = {}
        
        # last_period is only needed when we have no logs (for fallback path we exit early) or for backward ref; set after we have validated_period_starts
        last_period = None
        
        # STATELESS: Derive cycle starts from provided period_logs (no DB calls)
        # Each period_log entry with "date" represents a cycle start
        # We'll extract unique dates and validate minimum 21-day spacing

        # Helper: normalize cycle_starts after ANY insertion/extension.
        # - Deduplicates by DATE-ONLY equality (ignores time component)
        # - Sorts ascending
        # - Enforces minimum 21-day spacing (medical safety)
        #
        # NOTE: This is intentionally local to this function to keep changes minimal
        # and avoid redesigning the pipeline.
        def _normalize_cycle_starts_in_place(
            starts: List[datetime],
            meta_by_start: Dict[datetime, Dict],
            min_cycle_days: int = 21
        ) -> List[datetime]:
            # Deduplicate by date-only equality, preserving earliest datetime instance
            seen = set()
            unique: List[datetime] = []
            for cs in sorted(starts):
                d = cs.date()
                if d in seen:
                    continue
                seen.add(d)
                unique.append(cs)

            # Enforce min spacing
            validated: List[datetime] = []
            for cs in unique:
                if not validated:
                    validated.append(cs)
                    continue
                gap = (cs - validated[-1]).days
                if gap >= min_cycle_days:
                    validated.append(cs)
                else:
                    # Expected to happen with noisy predictions; keep log low-noise.
                    src = meta_by_start.get(cs, {}).get("source", "unknown")
                    print(f"DEBUG: Dropping cycle_start {cs.strftime('%Y-%m-%d')} (gap={gap}d < {min_cycle_days}, source={src})")

            # Clean meta dict keys that were deduped out (best-effort)
            keep_dates = {cs.date() for cs in validated}
            for k in list(meta_by_start.keys()):
                if k.date() not in keep_dates:
                    meta_by_start.pop(k, None)

            return validated
        
        # ====================================================================
        # A) CYCLE START NORMALIZATION (BEFORE any phase calculation)
        # ====================================================================
        # Collect cycle_start dates from all sources, deduplicate, and sort
        # This prevents duplicate cycles and ensures clean cycle boundaries
        
        cycle_starts_raw = []
        cycle_sources = {}  # Track source of each cycle: "real", "predicted", "fallback"
        
        # STATELESS: Extract cycle starts from provided period_logs
        # Each period_log entry with "date" represents a cycle start
        MIN_CYCLE_DAYS = 21
        MAX_CYCLE_DAYS = 45
        
        # Extract unique period start dates from period_logs
        period_start_dates = []
        seen_dates = set()
        for log in period_logs or []:
            date_str = log.get("date")
            if not date_str or date_str in seen_dates:
                continue
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                period_start_dates.append(date_obj)
                seen_dates.add(date_str)
            except Exception:
                continue
        
        # Assume period_logs was pre-sorted by caller (.order("date")); no redundant sort here.
        
        # MEDICAL GUARDRAIL: 21-day minimum between cycle starts (ACOG).
        # Logs closer than 21 days are treated as Spotting / same cycle - ignored as new cycle start.
        validated_period_starts = []
        if period_start_dates:
            validated_period_starts.append(period_start_dates[0])  # First is always valid
            
            # Use hoisted period_length_days for same-period check
            for i in range(1, len(period_start_dates)):
                current_date = period_start_dates[i]
                last_start = validated_period_starts[-1]
                
                gap = (current_date - last_start).days
                period_end = last_start + timedelta(days=period_length_days - 1)
                is_within_same_period = last_start <= current_date <= period_end
                
                if is_within_same_period:
                    # Same period, skip
                    continue
                elif gap >= MIN_CYCLE_DAYS:
                    # Valid new cycle start
                    validated_period_starts.append(current_date)
                else:
                    # Too close: treat as Spotting, do not add as cycle start (medical guardrail)
                    print(f"⚠️ Spotting/ignored: {current_date.strftime('%Y-%m-%d')} only {gap} days from previous cycle start (min {MIN_CYCLE_DAYS} days) - not counted as new cycle")
                    continue
        
        # Add validated period starts as "real" cycles
        for cs in validated_period_starts:
            cycle_starts_raw.append(cs)
            cycle_sources[cs] = "real"

        # COLD START: If period_logs is empty but user.last_period_date exists, use as Real anchor
        # Treat as 'Real' for forward predictions (Persist Fallback)
        if not validated_period_starts and has_last_period:
            anchor_date = datetime.strptime(str(last_period_date).strip()[:10], "%Y-%m-%d")
            cycle_starts_raw.append(anchor_date)
            cycle_sources[anchor_date] = "real"
            print(f"📌 Cold start: using last_period_date {last_period_date} as Real anchor for projections")
        
        # Set last_period for backward-reference paths
        if has_last_period:
            last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
        elif validated_period_starts:
            last_period = validated_period_starts[0]
        
        # GAP FILL: When gap between two real logs > MAX_CYCLE_DAYS, MUST insert predicted
        # cycle starts every cycle_length days so the daily loop has anchors (no giant Follicular block).
        cycle_days_fill = max(MIN_CYCLE_DAYS, min(MAX_CYCLE_DAYS, int(cycle_length)))
        for i in range(len(validated_period_starts) - 1):
            earlier = validated_period_starts[i]
            later = validated_period_starts[i + 1]
            gap_days = (later - earlier).days
            if gap_days > MAX_CYCLE_DAYS:
                # Insert predicted cycle start every cycle_length days until we would reach or pass 'later'
                fill_start = earlier + timedelta(days=cycle_days_fill)
                while fill_start < later:
                    if fill_start not in cycle_starts_raw:
                        cycle_starts_raw.append(fill_start)
                        cycle_sources[fill_start] = "predicted"
                    fill_start += timedelta(days=cycle_days_fill)
                print(f"📅 GAP FILL: inserted {(later - earlier).days // cycle_days_fill} predicted cycle(s) between {earlier.strftime('%Y-%m-%d')} and {later.strftime('%Y-%m-%d')} (gap={gap_days}d)")
        
        # Predict future cycles from the most recent anchor (real log, fallback, or validated start)
        # Continuous projection until end_date (e.g. July 2026)
        if cycle_starts_raw:
            most_recent_period = cycle_starts_raw[-1]
            current_start = most_recent_period
            cycle_days_step = max(MIN_CYCLE_DAYS, min(MAX_CYCLE_DAYS, int(cycle_length)))

            while current_start <= end_date_obj:
                next_start = current_start + timedelta(days=cycle_days_step)
                if next_start > end_date_obj:
                    break
                if next_start not in cycle_starts_raw:
                    cycle_starts_raw.append(next_start)
                    cycle_sources[next_start] = "predicted"
                current_start = next_start
        
        # No real/predicted cycles -> return empty list (Log to See Data; no virtual/fallback cycles)
        use_fallback = False
        if not cycle_starts_raw:
            use_fallback = True
            print("📭 No period logs found - returning empty phase map (use_fallback, no virtual anchor)")
            return []
        
        # DEDUPLICATE: Remove duplicates using date-only equality
        # Convert to date objects for comparison, then back to datetime
        seen_dates = set()
        cycle_starts_deduped = []
        for cs in cycle_starts_raw:
            cs_date = cs.date()  # Date-only comparison
            if cs_date not in seen_dates:
                seen_dates.add(cs_date)
                cycle_starts_deduped.append(cs)
            else:
                # Duplicate found - log but don't add
                source = cycle_sources.get(cs, "unknown")
                print(f"⚠️ Skipping duplicate cycle start: {cs.strftime('%Y-%m-%d')} (source={source})")
        
        # SORT: Ascending order
        cycle_starts_deduped.sort()
        
        # FINAL VALIDATION: Ensure minimum 21-day spacing
        MIN_CYCLE_DAYS = 21
        cycle_starts = []
        cycle_metadata = {}  # Store metadata per cycle (source, etc.)
        
        if cycle_starts_deduped:
            cycle_starts.append(cycle_starts_deduped[0])
            cycle_metadata[cycle_starts_deduped[0]] = {
                "source": cycle_sources.get(cycle_starts_deduped[0], "unknown"),
                "is_fallback": cycle_sources.get(cycle_starts_deduped[0], "unknown") == "fallback"
            }
            
            for i in range(1, len(cycle_starts_deduped)):
                current_start = cycle_starts_deduped[i]
                last_valid_start = cycle_starts[-1]
                gap = (current_start - last_valid_start).days
                source = cycle_sources.get(current_start, "unknown")
                # Always keep "real" period starts; enforce MIN_CYCLE_DAYS only for predicted/predicted or predicted/real
                if source == "real" or gap >= MIN_CYCLE_DAYS:
                    cycle_starts.append(current_start)
                    cycle_metadata[current_start] = {
                        "source": source,
                        "is_fallback": source == "fallback"
                    }
                else:
                    print(f"⚠️ Skipping cycle start {current_start.strftime('%Y-%m-%d')} - only {gap} days from previous (minimum {MIN_CYCLE_DAYS} days, source={source})")
        
        # Log cycle normalization result
        real_count = sum(1 for cs in cycle_starts if cycle_metadata.get(cs, {}).get("source") == "real")
        predicted_count = sum(1 for cs in cycle_starts if cycle_metadata.get(cs, {}).get("source") == "predicted")
        fallback_count = sum(1 for cs in cycle_starts if cycle_metadata.get(cs, {}).get("is_fallback"))
        print(f"✅ Cycle normalization complete: {len(cycle_starts)} cycles (real={real_count}, predicted={predicted_count}, fallback={fallback_count})")
        
        # VIRTUAL BACKWARD FILL (Option B): Project cycles backward before first log to populate calendar
        # This ensures the calendar and history are fully populated even before the first log
        if cycle_starts and start_date_obj < cycle_starts[0]:
            first_cycle = cycle_starts[0]
            cycle_days = max(int(cycle_length), MIN_CYCLE_DAYS)
            extended_cycle = first_cycle - timedelta(days=cycle_days)
            cycles_added = 0
            max_backward_cycles = 24  # Safety cap
            # Keep adding backward until we have a cycle start on or before start_date_obj
            while cycles_added < max_backward_cycles and extended_cycle >= start_date_obj:
                cycle_starts.append(extended_cycle)
                # Mark backward-projected cycles as virtual
                cycle_metadata[extended_cycle] = {"source": "virtual", "is_fallback": False, "is_virtual": True}
                cycles_added += 1
                if extended_cycle <= start_date_obj:
                    break
                extended_cycle -= timedelta(days=cycle_days)

            # Re-normalize after extension: sort and enforce min spacing
            cycle_starts = _normalize_cycle_starts_in_place(cycle_starts, cycle_metadata, min_cycle_days=MIN_CYCLE_DAYS)
            print(f"✅ VIRTUAL BACKWARD FILL: Extended {cycles_added} virtual cycles backwards to cover start_date (post-normalization cycles={len(cycle_starts)})")

        # Initial anchor: ensure at least one cycle start is on or before start_date_obj so the daily loop never sees None
        if cycle_starts and cycle_starts[0] > start_date_obj:
            anchor_start = cycle_starts[0] - timedelta(days=max(int(cycle_length), MIN_CYCLE_DAYS))
            cycle_starts.insert(0, anchor_start)
            cycle_metadata[anchor_start] = {"source": "virtual", "is_fallback": False, "is_virtual": True}
            cycle_starts.sort()
            print(f"✅ Initial anchor: added virtual cycle start {anchor_start.strftime('%Y-%m-%d')} so range is covered")

        late_shift = int(max(0, late_anchor_shift_days or 0))
        if late_shift > 0:
            cycle_starts, cycle_metadata = _apply_late_anchor_shift_to_cycle_starts(
                cycle_starts, cycle_metadata, late_shift, MIN_CYCLE_DAYS
            )
            print(
                f"📌 Late-period anchor adjustment: shifted predicted starts by +{late_shift}d "
                f"({len(cycle_starts)} cycle anchors)"
            )
        
        # ====================================================================
        # B) LUTEAL ANCHORING (PER-CYCLE, NOT PER-DAY)
        # ====================================================================
        # Pre-calculate cycle metadata (luteal_mean, ovulation, fertile window) ONCE per cycle
        # This prevents redundant calculations inside the date loop
        
        cycle_metadata_cache = {}  # Cache cycle-level calculations
        
        for cycle_start in cycle_starts:
            cycle_start_str = cycle_start.strftime("%Y-%m-%d")
            
            # Calculate actual cycle length for this cycle
            cycle_index = cycle_starts.index(cycle_start)
            if cycle_index < len(cycle_starts) - 1:
                next_cycle_start = cycle_starts[cycle_index + 1]
                actual_cycle_length = (next_cycle_start - cycle_start).days
                if actual_cycle_length < 21 or actual_cycle_length > 45:
                    actual_cycle_length = float(cycle_length)
            else:
                # Last cycle (future) - calculate median from in-memory cycle lengths
                # Extract cycle lengths from cycle_starts (already validated above)
                in_memory_cycle_lengths = []
                for i in range(len(cycle_starts) - 1):
                    length = (cycle_starts[i + 1] - cycle_starts[i]).days
                    if 21 <= length <= 45:
                        in_memory_cycle_lengths.append(length)
                
                if in_memory_cycle_lengths:
                    cycle_lengths_sorted = sorted(in_memory_cycle_lengths)
                    median_idx = len(cycle_lengths_sorted) // 2
                    actual_cycle_length = cycle_lengths_sorted[median_idx] if len(cycle_lengths_sorted) % 2 == 1 else (cycle_lengths_sorted[median_idx - 1] + cycle_lengths_sorted[median_idx]) / 2
                else:
                    actual_cycle_length = float(cycle_length)
                
                if actual_cycle_length < 21:
                    actual_cycle_length = 21
                if actual_cycle_length > 45:
                    actual_cycle_length = 45
            
            # LUTEAL ANCHORING: Calculate ONCE per cycle (not per day)
            # Formula: Predicted Ovulation = Next Period Start - avg(Last 3 Luteal Phases)
            calculated_ovulation_day = max(period_days + 1, actual_cycle_length - luteal_mean)
            
            # Fertile window calculation
            fertile_window_start = max(period_days + 1, calculated_ovulation_day - 3)
            fertile_window_end = min(int(actual_cycle_length), calculated_ovulation_day)
            
            if fertile_window_end < fertile_window_start:
                fertile_window_end = fertile_window_start + 1
                if fertile_window_end > int(actual_cycle_length):
                    fertile_window_end = int(actual_cycle_length)
            
            if fertile_window_end >= int(actual_cycle_length):
                fertile_window_end = max(fertile_window_start, int(actual_cycle_length) - 1)
            
            # Predict ovulation
            ovulation_date_str, ovulation_sd, ovulation_offset = predict_ovulation(
                cycle_start_str,
                actual_cycle_length,
                luteal_mean,
                luteal_sd,
                cycle_start_sd=None,
                user_id=user_id
            )
            
            # Adaptive window: 3 days for regular cycles, up to 5 for irregular (ovulation_sd)
            max_ov_days = 5 if ovulation_sd >= 2.5 else 3
            ovulation_days = select_ovulation_days(ovulation_sd, max_days=max_ov_days)
            
            # Cache all cycle-level metadata
            cycle_metadata_cache[cycle_start_str] = {
                "actual_cycle_length": actual_cycle_length,
                "calculated_ovulation_day": calculated_ovulation_day,
                "fertile_window_start": fertile_window_start,
                "fertile_window_end": fertile_window_end,
                "ovulation_date_str": ovulation_date_str,
                "ovulation_sd": ovulation_sd,
                "ovulation_days": ovulation_days,
                "luteal_mean": luteal_mean  # Cache for reuse
            }
            
            # Log luteal anchoring ONCE per cycle (not per day)
            source = cycle_metadata.get(cycle_start, {}).get("source", "unknown")
            is_fallback = cycle_metadata.get(cycle_start, {}).get("is_fallback", False)
            fallback_note = " (FALLBACK - not persisted)" if is_fallback else ""
            print(f"🔬 Cycle {cycle_start_str}: luteal_mean={luteal_mean:.1f}, ovulation_day={calculated_ovulation_day}, fertile_window=[{fertile_window_start}-{fertile_window_end}], source={source}{fallback_note}")
        
        # ====================================================================
        # C) DAILY PHASE CALCULATION (per-date loop)
        # ====================================================================
        total_days = (end_date_obj - start_date_obj).days + 1
        print(f"📊 Processing {total_days} dates from {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}")
        
        dates_processed = 0
        dates_with_phases = 0
        
        cycle_days_int = max(MIN_CYCLE_DAYS, min(MAX_CYCLE_DAYS, int(cycle_length)))
        first_cycle_start_dt = cycle_starts[0] if cycle_starts else None
        # Earliest REAL log (for "before first log" anchor): find future real, subtract cycle_length to get predicted start <= current_date
        real_cycle_starts = sorted([cs for cs in cycle_starts if cycle_metadata.get(cs, {}).get("source") == "real"]) if cycle_starts else []
        earliest_real_dt = real_cycle_starts[0] if real_cycle_starts else None
        
        while current_date <= end_date_obj:
            # Find which cycle this date belongs to (anchor)
            # 1) If current_date >= some known cycle start: use the most recent cycle start <= current_date
            # 2) If current_date is before all real logs: find earliest real log in the future, subtract cycle_length repeatedly until predicted_start <= current_date; use that as anchor
            current_cycle_start = None
            use_metadata_from_cycle_str = None  # when projecting backward, use first real cycle's metadata
            
            for i in range(len(cycle_starts) - 1, -1, -1):
                cycle_start = cycle_starts[i]
                if cycle_start <= current_date:
                    current_cycle_start = cycle_start
                    break
            
            anchor_source_for_diagnostic = None
            is_virtual_date = False  # Track if this date is from virtual backward projection
            
            # VIRTUAL BACKWARD FILL: Use backward-projected cycle starts if available
            if current_cycle_start is None and cycle_starts:
                # Find the nearest cycle start (including virtual ones)
                for cs in reversed(cycle_starts):
                    if cs <= current_date:
                        current_cycle_start = cs
                        cycle_meta_info = cycle_metadata.get(cs, {})
                        if cycle_meta_info.get("is_virtual") or cycle_meta_info.get("source") == "virtual":
                            is_virtual_date = True
                            anchor_source_for_diagnostic = "Virtual-Backward"
                        break
            
            # Date validation: skip this date if we have no cycle anchor (graceful fallback)
            if current_cycle_start is None:
                current_date += timedelta(days=1)
                continue

            # Calculate day_in_cycle (1-indexed); ensure never negative or None
            if current_cycle_start:
                days_in_current_cycle = (current_date - current_cycle_start).days + 1
            else:
                days_in_current_cycle = 1
            if days_in_current_cycle is None or days_in_current_cycle < 1:
                days_in_current_cycle = 1
            
            # Get cycle metadata from cache (pre-calculated per-cycle, not per-day)
            cycle_start_str = current_cycle_start.strftime("%Y-%m-%d")
            metadata_key = use_metadata_from_cycle_str if use_metadata_from_cycle_str else cycle_start_str
            
            # Phase counters are per-cycle (keyed by cycle_start_str). When date moves to a new
            # anchor (e.g. predicted cycle in a gap), this lookup creates a new counter set at 0,
            # so the cycle starts over at P1 -> F1 -> O1 -> L1.
            if cycle_start_str not in phase_counters_by_cycle:
                phase_counters_by_cycle[cycle_start_str] = {
                    "Period": 0, "Follicular": 0, "Ovulation": 0, "Luteal": 0
                }
            
            # Get cached cycle metadata (when projecting backward/virtual, use nearest real cycle's metadata if available)
            cycle_meta = cycle_metadata_cache.get(metadata_key)
            # If virtual cycle has no metadata, use first real cycle's metadata as fallback
            if not cycle_meta and is_virtual_date and cycle_starts:
                for cs in cycle_starts:
                    cs_meta = cycle_metadata.get(cs, {})
                    if cs_meta.get("source") == "real":
                        real_meta_key = cs.strftime("%Y-%m-%d")
                        cycle_meta = cycle_metadata_cache.get(real_meta_key)
                        if cycle_meta:
                            break
            if not cycle_meta:
                # Should not happen - all cycles should have metadata
                print(f"⚠️ WARNING: No metadata for cycle {cycle_start_str}, using fallback")
                cycle_meta = {
                    "actual_cycle_length": float(cycle_length),
                    "calculated_ovulation_day": cycle_length - 14,
                    "fertile_window_start": max(period_days + 1, (cycle_length - 14) - 3),
                    "fertile_window_end": min(int(cycle_length), cycle_length - 14),
                    "ovulation_date_str": (current_cycle_start + timedelta(days=int(cycle_length - 14))).strftime("%Y-%m-%d"),
                    "ovulation_sd": 2.0,
                    "ovulation_days": {-1, 0, 1},
                    "luteal_mean": 14.0
                }
            
            # Use cached values (no per-day calculation)
            actual_cycle_length = cycle_meta["actual_cycle_length"]
            calculated_ovulation_day = cycle_meta["calculated_ovulation_day"]
            fertile_window_start = cycle_meta["fertile_window_start"]
            fertile_window_end = cycle_meta["fertile_window_end"]
            ovulation_date_str = cycle_meta["ovulation_date_str"]
            ovulation_sd = cycle_meta["ovulation_sd"]
            ovulation_days = cycle_meta["ovulation_days"]
            ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
            
            # Calculate offset from ovulation
            offset_from_ov = (current_date - ovulation_date).days
            
            # Calculate ovulation probability for phase determination (NOT fertility probability)
            # This ensures Ovulation phase is 1-4 days, not 6+ days
            ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
            
            # Also calculate fertility probability for tracking purposes
            fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
            # Confidence gate: extreme irregularity should reduce fertility certainty
            if ovulation_sd > 4.0:
                fert_prob *= 0.7
            
            # Get phase counters for this cycle
            phase_counters = phase_counters_by_cycle[cycle_start_str]
            
            # Explicitly reset phase counters at cycle boundary
            # This prevents counters from continuing from previous cycle if phases are skipped
            if current_date == current_cycle_start:
                phase_counters["Period"] = 0
                phase_counters["Follicular"] = 0
                phase_counters["Ovulation"] = 0
                phase_counters["Luteal"] = 0
            
            # MEDICALLY ACCURATE PHASE CALCULATION (inspired by reference code)
            # This ensures fast, accurate phase assignment based on cycle day
            day_in_cycle = days_in_current_cycle if days_in_current_cycle is not None else 1
            if not isinstance(day_in_cycle, (int, float)) or day_in_cycle < 1:
                day_in_cycle = 1
            phase = None
            is_fertile_window = False
            is_ovulation_event = False

            # Fertile window: sperm can survive up to ~5 days; represent a 5-day window ending on ovulation day.
            # We keep the calendar IDs o1..o5 for this window (o5 is the ovulation event day itself).
            fertile_window_offsets = set(range(-4, 1))  # {-4,-3,-2,-1,0} => 5 days total
            
            # VALIDATION: Ensure day_in_cycle is reasonable (never negative or None)
            if day_in_cycle < 1:
                day_in_cycle = 1
            # Phase ID overflow guard: if day_in_cycle exceeds cycle_length, switch to next predicted cycle (L14 -> P1)
            cycle_len_threshold = int(actual_cycle_length) + 3 if actual_cycle_length else 60
            if day_in_cycle > cycle_len_threshold:
                for cs in cycle_starts:
                    if cs > current_cycle_start and cs <= current_date:
                        gap = (current_date - cs).days
                        if gap < day_in_cycle and gap >= 0:
                            current_cycle_start = cs
                            day_in_cycle = gap + 1
                            cycle_start_str = current_cycle_start.strftime("%Y-%m-%d")
                            cycle_meta = cycle_metadata_cache.get(cycle_start_str)
                            if not cycle_meta and cycle_metadata_cache:
                                cycle_meta = cycle_metadata_cache.get(list(cycle_metadata_cache.keys())[0])
                            if cycle_meta:
                                ovulation_date_str = cycle_meta["ovulation_date_str"]
                                ovulation_date = datetime.strptime(ovulation_date_str, "%Y-%m-%d")
                                offset_from_ov = (current_date - ovulation_date).days
                                ovulation_days = cycle_meta.get("ovulation_days", {-1, 0, 1})
                            break
            
            # MEDICAL FIX: Phase assignment with clear priority (medically accurate)
            # CRITICAL: Ensure only ONE period phase per cycle (days 1 to period_days)
            # Validate day_in_cycle is within valid cycle range
            if day_in_cycle < 1:
                # Invalid - day_in_cycle should never be < 1
                print(f"⚠️ WARNING: day_in_cycle < 1 for date {current_date.strftime('%Y-%m-%d')}, cycle start {current_cycle_start.strftime('%Y-%m-%d')}. Setting to 1.")
                day_in_cycle = 1
            
            # 1. Period Phase: Days 1 to period_days (IDs: p1-p12)
            # MEDICAL RULE: Only days 1-period_days can be Period phase in a cycle
            if 1 <= day_in_cycle <= period_days:
                phase = "Period"
            # 2. Ovulation event: a single day (offset 0)
            elif offset_from_ov == 0:
                phase = "Ovulation"
                is_ovulation_event = True
                is_fertile_window = True
            # 3. Fertile window: 5-day sperm survival window ending on ovulation day
            elif offset_from_ov in fertile_window_offsets:
                phase = "Fertile"
                is_fertile_window = True
            # 3. Follicular Phase: After period, before ovulation block
            elif day_in_cycle > period_days and offset_from_ov < min(fertile_window_offsets):
                phase = "Follicular"
            # 4. Luteal Phase: After ovulation block until next period
            elif day_in_cycle > period_days and offset_from_ov > 0:
                phase = "Luteal"
            else:
                phase = "Follicular"  # Between period and ovulation start, or edge case
            
            # MEDICAL VALIDATION: Period only on days 1–period_days
            if phase == "Period" and (day_in_cycle < 1 or day_in_cycle > period_days):
                print(f"❌ ERROR: Attempted to assign Period phase to day {day_in_cycle} (valid range: 1-{period_days}). Fixing to correct phase.")
                if offset_from_ov in ovulation_days:
                    phase = "Ovulation"
                elif ovulation_days and offset_from_ov > max(ovulation_days):
                    phase = "Luteal"
                else:
                    phase = "Follicular"
            
            # CRITICAL: Override phase if date is in a logged period (from provided period_logs)
            # This ensures logged periods ALWAYS show as Period phase, regardless of predictions
            # This check happens BEFORE incrementing counters to ensure correct phase_day_id
            current_date_str = current_date.strftime("%Y-%m-%d")
            current_date_date = current_date.date()
            
            # STATELESS: Check provided period_logs instead of DB query
            is_in_logged_period = False
            day_in_period = None
            
            for period_log in period_logs or []:
                period_start_str = period_log.get("date")
                if not period_start_str:
                    continue
                try:
                    period_start = datetime.strptime(period_start_str, "%Y-%m-%d").date()
                except Exception:
                    continue
                
                # Determine period end
                if period_log.get("end_date"):
                    try:
                        period_end = datetime.strptime(period_log["end_date"], "%Y-%m-%d").date()
                    except Exception:
                        period_end = period_start + timedelta(days=period_length_days - 1)
                else:
                    period_end = period_start + timedelta(days=period_length_days - 1)
                
                if period_start <= current_date_date <= period_end:
                    # This date is in this logged period - override phase
                    day_in_period = (current_date_date - period_start).days + 1
                    is_in_logged_period = True
                    break
            
            if is_in_logged_period:
                # Date is in a logged period - override phase to Period (cap for wellness DB)
                phase = "Period"
                phase_day_id = f"p{min(day_in_period, PHASE_DAY_CAPS.get('Period', 10))}"
                # Reset Period counter for this cycle to match logged period day
                phase_counters["Period"] = day_in_period
                day_in_phase = day_in_period
                print(f"✅ OVERRIDE: Date {current_date_str} is in logged period, forcing Period phase (p{day_in_period})")
            else:
                # Normal phase assignment.
                #
                # IMPORTANT: Calendar "O*" IDs represent the *fertile window* (5-day sperm survival window).
                # `o5` is the ovulation event day (offset 0). Window days are `o1..o4`.
                if phase in ("Ovulation", "Fertile") and offset_from_ov in fertile_window_offsets:
                    sorted_offsets = sorted(list(fertile_window_offsets))
                    try:
                        day_in_phase = sorted_offsets.index(offset_from_ov) + 1  # -4=>1 ... 0=>5
                    except ValueError:
                        day_in_phase = 1
                    phase_day_id = _calendar_phase_day_id("Ovulation", day_in_phase, ovulation_cap=5)
                    phase_counters["Ovulation"] = max(phase_counters.get("Ovulation", 0), day_in_phase)
                else:
                    phase_counters[phase] += 1
                    day_in_phase = phase_counters[phase]
                    phase_day_id = generate_phase_day_id(phase, day_in_phase)
            
            dates_processed += 1
            
            # CATCH-ALL: Ensure every date gets a phase assignment
            # This prevents gaps where dates don't fall perfectly into phase buckets
            if not phase:
                phase = "Follicular"  # Default fallback phase
                print(f"⚠️ Catch-all: Date {current_date.strftime('%Y-%m-%d')} assigned Follicular phase (no phase was set)")
            
            # Ensure phase_day_id is set if phase exists
            if phase and not phase_day_id:
                # Increment counter for the phase and generate phase_day_id
                phase_counters[phase] += 1
                day_in_phase = phase_counters[phase]
                phase_day_id = generate_phase_day_id(phase, day_in_phase)
                print(f"⚠️ Catch-all: Generated phase_day_id {phase_day_id} for date {current_date.strftime('%Y-%m-%d')}")
            
            # Determine if this date is predicted/virtual
            cycle_meta_info = cycle_metadata.get(current_cycle_start, {}) if current_cycle_start else {}
            is_predicted_value = cycle_meta_info.get("source") != "real" or is_virtual_date
            is_virtual_value = cycle_meta_info.get("is_virtual") or is_virtual_date or cycle_meta_info.get("source") == "virtual"
            
            # CRITICAL: Every date MUST result in a phase mapping
            phase_mappings.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "phase": phase,
                "phase_day_id": phase_day_id,
                "source": "local",
                "is_predicted": is_predicted_value,
                "is_virtual": is_virtual_value,
                "is_fertile_window": bool(is_fertile_window),
                "is_ovulation_event": bool(is_ovulation_event),
                "prediction_confidence": 0.6 if ovulation_sd > 4.0 else 0.8,
                "fertility_prob": float(fert_prob),
                "predicted_ovulation_date": ovulation_date_str,
                "luteal_estimate": round(luteal_mean, 2),
                "luteal_sd": round(luteal_sd, 2),
                "ovulation_sd": round(ovulation_sd, 2)
            })
            dates_with_phases += 1
            if diagnostic_log is not None and current_cycle_start is not None:
                diff_days = (current_date - current_cycle_start).days
                source = anchor_source_for_diagnostic if anchor_source_for_diagnostic else cycle_metadata.get(current_cycle_start, {}).get("source", "predicted")
                if source == "real":
                    source = "Real"
                elif source == "predicted":
                    source = "Predicted"
                elif source == "fallback":
                    source = "Fallback"
                diagnostic_log.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "anchor": current_cycle_start.strftime("%Y-%m-%d"),
                    "days_from_anchor": diff_days,
                    "phase": phase,
                    "phase_day_id": phase_day_id if phase_day_id else "",
                    "source": source or "Predicted",
                })
            current_date += timedelta(days=1)

        # Post-pass: enforce exactly one fertility peak per cycle.
        #
        # `fertility_probability` intentionally shapes peak around day -2/-1, which can yield
        # ties at exactly 1.0. For UI/contract simplicity we guarantee a single peak day
        # (fertility_prob == 1.0) per predicted ovulation date; other days are nudged below.
        try:
            by_ov_date: Dict[str, List[Dict[str, Any]]] = {}
            for row in phase_mappings:
                key = str(row.get("predicted_ovulation_date") or "")
                if not key:
                    continue
                by_ov_date.setdefault(key, []).append(row)

            for _ov_date, rows in by_ov_date.items():
                if not rows:
                    continue
                # Choose max fertility_prob; if tie, prefer offset -1, then -2, then closest to 0.
                def _tie_key(r: Dict[str, Any]) -> Tuple[float, int, int]:
                    try:
                        d = datetime.strptime(str(r.get("date")), "%Y-%m-%d")
                        ov = datetime.strptime(str(r.get("predicted_ovulation_date")), "%Y-%m-%d")
                        off = (d - ov).days
                    except Exception:
                        off = 999
                    pref = 0 if off == -1 else 1 if off == -2 else 2
                    return (float(r.get("fertility_prob") or 0.0), -pref, -abs(off))

                peak_row = max(rows, key=_tie_key)
                for r in rows:
                    if r is peak_row:
                        r["fertility_prob"] = 1.0
                    else:
                        # Ensure strictly below peak; keep 3dp-friendly values.
                        r["fertility_prob"] = min(float(r.get("fertility_prob") or 0.0), 0.999)
        except Exception:
            logger.exception("Failed to enforce single fertility peak per cycle")
        
        # Build final list: include all dates in range (including virtual backward fill)
        by_date = {m["date"]: m for m in phase_mappings}
        follicular_default = {
            "phase": "Follicular",
            "source": "local",
            "is_predicted": True,
            "is_virtual": True,
            "prediction_confidence": 0.5,
            "fertility_prob": 0.0,
            "predicted_ovulation_date": None,
            "luteal_estimate": 14.0,
            "luteal_sd": 2.0,
            "ovulation_sd": 2.0
        }
        final_phase_mappings = []
        d = start_date_obj
        while d <= end_date_obj:
            date_str = d.strftime("%Y-%m-%d")
            m = by_date.get(date_str)
            if m:
                final_phase_mappings.append(m)
            else:
                # Fill gaps with predicted/virtual phases (including before first log)
                # More intelligent default: increment follicular day based on distance from range start,
                # instead of showing f1 for long gaps.
                day_in_range = (d - start_date_obj).days + 1
                phase_day_id = generate_phase_day_id("Follicular", day_in_range)
                final_phase_mappings.append({"date": date_str, "phase_day_id": phase_day_id, **follicular_default})
            d += timedelta(days=1)
        print(f"✅ Generated {len(final_phase_mappings)} phase mappings (includes virtual backward fill before first log)")
        return final_phase_mappings
    
    except Exception as e:
        print(f"Error calculating phase for date range: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def detect_early_late_period(user_id: str, logged_period_date: str) -> Optional[Dict]:
    """
    Detect if a logged period is early or late compared to predictions.
    
    Args:
        user_id: User ID
        logged_period_date: The actual period start date (YYYY-MM-DD)
    
    Returns:
        Dict with:
        - is_early_late: bool
        - difference_days: int (positive = late, negative = early)
        - predicted_date: str (predicted period start date)
        - should_adjust: bool (True if difference >= 2 days)
    """
    try:
        logged_date = datetime.strptime(logged_period_date, "%Y-%m-%d")
        
        # Get the most recent predicted cycle start
        response = supabase.table("user_cycle_days").select("date, phase_day_id").eq("user_id", user_id).eq("phase_day_id", "p1").order("date", desc=True).limit(1).execute()
        
        if not response.data:
            return None
        
        predicted_date_str = response.data[0]["date"]
        predicted_date = datetime.strptime(predicted_date_str, "%Y-%m-%d")
        
        # Calculate difference
        difference_days = (logged_date - predicted_date).days
        
        # If difference is >= 2 days, we should adjust
        should_adjust = abs(difference_days) >= 2
        
        return {
            "is_early_late": should_adjust,
            "difference_days": difference_days,
            "predicted_date": predicted_date_str,
            "should_adjust": should_adjust
        }
    except Exception as e:
        print(f"Error detecting early/late period: {str(e)}")
        return None

def calculate_today_phase_day_id(user_id: str) -> Optional[str]:
    """
    Calculate today's phase-day ID based on user's last_period_date and cycle_length.
    This is a fallback if cycle predictions haven't been generated yet.
    
    Returns:
        phase_day_id (e.g., "p5", "f10", "o2", "l15") or None
    """
    try:
        # Get user data
        user_response = supabase.table("users").select("last_period_date, cycle_length").eq("id", user_id).execute()
        
        if not user_response.data:
            return None
        
        user = user_response.data[0]
        last_period_date = user.get("last_period_date")
        cycle_length = user.get("cycle_length", 28)
        
        if not last_period_date:
            return None
        
        # Get predicted cycle starts from database (prevents drift)
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        predicted_cycle_starts = get_predicted_cycle_starts_from_db(user_id, None, today_str)
        
        # Find which cycle today belongs to
        last_period = datetime.strptime(last_period_date, "%Y-%m-%d")
        current_cycle_start = None
        
        if predicted_cycle_starts:
            # Use predicted cycle starts (more accurate)
            cycle_starts = [datetime.strptime(d, "%Y-%m-%d") for d in predicted_cycle_starts]
            # Find the most recent cycle start <= today
            for cycle_start in cycle_starts:
                if cycle_start <= today:
                    current_cycle_start = cycle_start
                else:
                    break
        else:
            # Fallback: use last_period_date as cycle start
            current_cycle_start = last_period
        
        if current_cycle_start is None:
            current_cycle_start = last_period
        
        # ⚠️ CRITICAL: Calculate which day of the cycle we're on (1-INDEXED)
        # Formula: (today - current_cycle_start).days + 1
        # Cycle start = day 1, not day 0
        # Example: If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
        days_since_cycle_start = (today - current_cycle_start).days
        if days_since_cycle_start < 0:
            return None
        
        day_in_cycle = days_since_cycle_start + 1
        
        # Get adaptive estimates (not fixed!)
        luteal_mean, luteal_sd = estimate_luteal(user_id)
        period_days = estimate_period_length(user_id, normalized=True)  # Use normalized for phase calculations
        
        # Calculate actual cycle length for this cycle
        if predicted_cycle_starts and len(cycle_starts) > 1:
            cycle_index = cycle_starts.index(current_cycle_start)
            if cycle_index < len(cycle_starts) - 1:
                next_cycle_start = cycle_starts[cycle_index + 1]
                actual_cycle_length = (next_cycle_start - current_cycle_start).days
            else:
                actual_cycle_length = float(cycle_length)
        else:
            actual_cycle_length = float(cycle_length)
        
        # Calculate ovulation date for this cycle using actual cycle length
        ovulation_offset = actual_cycle_length - luteal_mean
        ovulation_date = current_cycle_start + timedelta(days=int(ovulation_offset))
        today_date = datetime.now()
        
        # Calculate ovulation probability for today to determine ovulation window dynamically
        offset_from_ov = (today_date - ovulation_date).days
        ovulation_sd = math.sqrt(1.5 ** 2 + luteal_sd ** 2)  # Approximate ovulation_sd
        ov_prob = ovulation_probability(offset_from_ov, ovulation_sd)
        
        # Also calculate fertility probability for tracking purposes
        fert_prob = fertility_probability(offset_from_ov, ovulation_sd)
        
        # Pre-calculate ovulation days using top-N by probability approach
        ovulation_days = select_ovulation_days(ovulation_sd, max_days=3)
        
        # Determine phase dynamically based on top-N ovulation days
        # This ensures Ovulation phase represents actual ovulation event (1-3 days max)
        # Follicular phase extends until ovulation phase starts
        # ⚠️ CRITICAL: day_in_cycle is 1-INDEXED
        # If period_days = 5, then days 1, 2, 3, 4, 5 are Period phase (5 days inclusive)
        # DO NOT change to < period_days or period_days + 1 - this will break silently
        if day_in_cycle <= period_days:
            phase = "Period"
            day_in_phase = day_in_cycle
        elif offset_from_ov in ovulation_days:
            # Ovulation window: Top-N days by probability (1-3 days max, pre-calculated)
            # Uses adaptive selection based on actual probability distribution
            phase = "Ovulation"
            # Calculate day_in_phase: count days in ovulation window
            # Find position within the ovulation days set
            sorted_ovulation_days = sorted(ovulation_days)
            day_in_phase = sorted_ovulation_days.index(offset_from_ov) + 1
        else:
            # Follicular phase: extends from end of period until ovulation phase starts
            if today_date < ovulation_date:
                # Before predicted ovulation date and not in ovulation phase = Follicular
                phase = "Follicular"
                # Calculate day_in_phase: days after period ends
                day_in_phase = max(1, day_in_cycle - int(period_days))
            else:
                # After predicted ovulation date but not in ovulation phase = Luteal
                phase = "Luteal"
                # Calculate day_in_phase: days after ovulation
                days_after_ov = (today_date - ovulation_date).days
                day_in_phase = max(1, days_after_ov)
        
        # Generate phase-day ID
        return generate_phase_day_id(phase, day_in_phase)
    
    except Exception as e:
        print(f"Error calculating today phase-day ID: {str(e)}")
        return None

