import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from cycle_utils import (
    calculate_today_phase_day_id,
    get_previous_phase_day_ids,
    get_user_phase_day,
    parse_hormone_value,
)
from database import supabase
from routes.auth import get_current_user

router = APIRouter()
logger = logging.getLogger("periodcycle_ai.wellness")

HORMONE_DISCLAIMER = (
    "Hormone values are based on standard cycle mapping and are for educational tracking only."
)


def _normalize_interests_list(raw: Any) -> List[str]:
    """Coerce users.interests (JSONB list, JSON string, or list) into non-empty trimmed strings."""
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                raw = parsed
            else:
                return [s]
        except json.JSONDecodeError:
            return [s]
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        if x is None:
            continue
        t = str(x).strip()
        if t:
            out.append(t)
    return out


def _text_matches_interest(text: Optional[Any], interest: str) -> bool:
    """Case-insensitive overlap: substring either way or equality."""
    if text is None or not interest:
        return False
    t = str(text).strip().lower()
    i = interest.strip().lower()
    if not t or not i:
        return False
    return i in t or t in i or t == i


def _nutrition_interest_score(
    row: Dict[str, Any],
    interests: List[str],
    cuisine_boost: Optional[str],
) -> int:
    """Higher score = better match to profile interests / favorite cuisine."""
    score = 0
    cuisine = row.get("cuisine")
    recipe_name = row.get("recipe_name")
    for interest in interests:
        if _text_matches_interest(cuisine, interest) or _text_matches_interest(recipe_name, interest):
            score += 2
    if cuisine_boost and (
        _text_matches_interest(cuisine, cuisine_boost) or _text_matches_interest(recipe_name, cuisine_boost)
    ):
        score += 1
    return score


def _exercise_interest_score(
    row: Dict[str, Any],
    interests: List[str],
    category_boost: Optional[str],
) -> int:
    score = 0
    cat = row.get("category")
    name = row.get("exercise_name")
    desc = row.get("description")
    for interest in interests:
        if (
            _text_matches_interest(cat, interest)
            or _text_matches_interest(name, interest)
            or _text_matches_interest(desc, interest)
        ):
            score += 2
    if category_boost and _text_matches_interest(cat, category_boost):
        score += 1
    return score


def _rank_rows_by_score(
    rows: List[Dict[str, Any]],
    score_fn: Callable[[Dict[str, Any]], int],
) -> List[Dict[str, Any]]:
    """Stable sort: higher score first; original order preserved among ties."""
    if not rows:
        return rows
    keyed: List[Tuple[int, int, Dict[str, Any]]] = [
        (-score_fn(r), i, r) for i, r in enumerate(rows)
    ]
    keyed.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in keyed]

# Explicit columns for hormones_data (numeric levels + text labels + directional trends).
_HORMONES_DATA_SELECT = (
    "id, phase_id, day_number, energy_level, "
    "estrogen, progesterone, fsh, lh, "
    "estrogen_text, progesterone_text, fsh_text, lh_text, "
    "estrogen_trend, progesterone_trend, fsh_trend, lh_trend, "
    "mood, energy, best_work_type, brain_note, created_at"
)


class HormoneHistoryPoint(BaseModel):
    """One day in /wellness/hormones?days>1 history (charts + labels)."""

    model_config = ConfigDict(extra="ignore")

    phase_day_id: str
    estrogen_value: float = Field(0.0, description="Numeric level for charts; 0.0 if not backfilled yet")
    progesterone_value: float = 0.0
    fsh_value: float = 0.0
    lh_value: float = 0.0
    estrogen_label: Optional[str] = Field(None, description="Display text e.g. Low/High from estrogen_text")
    progesterone_label: Optional[str] = None
    fsh_label: Optional[str] = None
    lh_label: Optional[str] = None


def get_hormone_trends_summary_for_llm(user_id: str) -> str:
    """
    Short hormone trend summary for AI system prompts (same source as /wellness/hormones reference data).
    Safe to import from other modules; does not require a FastAPI request context.
    """
    resolved = _resolve_phase_day_id(user_id, None)
    if not resolved:
        return (
            "Hormone reference: no phase-day ID available for this user yet "
            "(they may need to log a period)."
        )
    try:
        r = (
            supabase.table("hormones_data")
            .select(
                "id, estrogen, progesterone, fsh, lh, "
                "estrogen_text, progesterone_text, fsh_text, lh_text, "
                "estrogen_trend, progesterone_trend, fsh_trend, lh_trend"
            )
            .eq("id", resolved)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("hormones_data lookup for LLM context failed")
        return f"Hormone reference: could not load trend data for phase day {resolved}."

    if not r.data:
        return f"Hormone reference: no trend row in database for phase day {resolved}."

    h = r.data[0]
    parts: List[str] = []
    for text_key, trend_key, label in (
        ("estrogen_text", "estrogen_trend", "Estrogen"),
        ("progesterone_text", "progesterone_trend", "Progesterone"),
        ("fsh_text", "fsh_trend", "FSH"),
        ("lh_text", "lh_trend", "LH"),
    ):
        ttxt = h.get(text_key)
        lab = str(ttxt).strip() if ttxt is not None and str(ttxt).strip() else None
        tr = h.get(trend_key)
        trend_s = str(tr).strip() if tr is not None and str(tr).strip() else None
        if lab and trend_s:
            parts.append(f"{label}: {lab} (trend {trend_s})")
        elif trend_s:
            parts.append(f"{label}: trend {trend_s}")
        elif lab:
            parts.append(f"{label}: {lab}")

    nums = []
    for label, col in (
        ("E", "estrogen"),
        ("P", "progesterone"),
        ("FSH", "fsh"),
        ("LH", "lh"),
    ):
        v = parse_hormone_value(h.get(col))
        if v != 0.0:
            nums.append(f"{label}={v:.2f}")

    if nums:
        parts.append("reference scale (numeric): " + ", ".join(nums))

    if not parts:
        return f"Hormone reference for phase day {resolved}: trend/label fields empty in reference data."

    return (
        "Typical mapped hormone trends for today (phase day "
        f"{resolved}): "
        + "; ".join(parts)
        + ". These are educational reference patterns only, not lab measurements."
    )


def _resolve_phase_day_id(user_id: str, phase_day_id: Optional[str]) -> Optional[str]:
    if phase_day_id:
        return phase_day_id.strip().lower()
    today_phase = get_user_phase_day(user_id, datetime.now().strftime("%Y-%m-%d"), prefer_actual=True)
    if today_phase and today_phase.get("phase_day_id"):
        return str(today_phase["phase_day_id"]).strip().lower()
    calculated = calculate_today_phase_day_id(user_id)
    return str(calculated).strip().lower() if calculated else None


def _optional_hormone_label(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def _hormone_row_to_today_payload(hormone_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build API dict: *_label from *_text columns; *_value from numeric columns (0.0 if null)."""
    phase_day_id_from_db = hormone_data.get("id")
    e_val = parse_hormone_value(hormone_data.get("estrogen"))
    p_val = parse_hormone_value(hormone_data.get("progesterone"))
    f_val = parse_hormone_value(hormone_data.get("fsh"))
    l_val = parse_hormone_value(hormone_data.get("lh"))
    return {
        "id": phase_day_id_from_db,
        "phase_day_id": phase_day_id_from_db,
        "phase_id": hormone_data.get("phase_id"),
        "day_number": hormone_data.get("day_number"),
        "estrogen_label": _optional_hormone_label(hormone_data.get("estrogen_text")),
        "progesterone_label": _optional_hormone_label(hormone_data.get("progesterone_text")),
        "fsh_label": _optional_hormone_label(hormone_data.get("fsh_text")),
        "lh_label": _optional_hormone_label(hormone_data.get("lh_text")),
        "estrogen_value": e_val,
        "progesterone_value": p_val,
        "fsh_value": f_val,
        "lh_value": l_val,
        # Backward compatibility: same numeric series pre-*_value keys
        "estrogen": e_val,
        "progesterone": p_val,
        "fsh": f_val,
        "lh": l_val,
        "estrogen_trend": hormone_data.get("estrogen_trend"),
        "progesterone_trend": hormone_data.get("progesterone_trend"),
        "fsh_trend": hormone_data.get("fsh_trend"),
        "lh_trend": hormone_data.get("lh_trend"),
        "mood": hormone_data.get("mood"),
        "energy": hormone_data.get("energy"),
        "best_work_type": hormone_data.get("best_work_type"),
        "brain_note": hormone_data.get("brain_note"),
        "energy_level": hormone_data.get("energy", {}).get("level")
        if isinstance(hormone_data.get("energy"), dict)
        else hormone_data.get("energy_level"),
        "emotional_summary": hormone_data.get("mood", {}).get("summary")
        if isinstance(hormone_data.get("mood"), dict)
        else None,
        "physical_summary": hormone_data.get("brain_note", {}).get("summary")
        if isinstance(hormone_data.get("brain_note"), dict)
        else None,
    }


def _history_point_from_row(hormone_data: Dict[str, Any], phase_day_id: str) -> Dict[str, Any]:
    row = HormoneHistoryPoint(
        phase_day_id=phase_day_id,
        estrogen_value=parse_hormone_value(hormone_data.get("estrogen")),
        progesterone_value=parse_hormone_value(hormone_data.get("progesterone")),
        fsh_value=parse_hormone_value(hormone_data.get("fsh")),
        lh_value=parse_hormone_value(hormone_data.get("lh")),
        estrogen_label=_optional_hormone_label(hormone_data.get("estrogen_text")),
        progesterone_label=_optional_hormone_label(hormone_data.get("progesterone_text")),
        fsh_label=_optional_hormone_label(hormone_data.get("fsh_text")),
        lh_label=_optional_hormone_label(hormone_data.get("lh_text")),
    )
    return row.model_dump()


def _empty_hormone_response(
    language: str,
    phase_day_id: Optional[str],
    message: str,
    include_history: bool = False,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "today": {},
        "language": language,
        "phase_day_id": phase_day_id,
        "message": message,
        "disclaimer": HORMONE_DISCLAIMER,
    }
    if include_history:
        out["history"] = []
    return out


@router.get("/hormones")
async def get_hormones(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID (e.g., p1, f5, o2, l10). If not provided, uses today's phase-day ID"),
    days: int = Query(5, description="Number of days to fetch (default 5: last 4 days + today)"),
    current_user: dict = Depends(get_current_user),
):
    """Get hormone data for a specific phase day. Defaults to today's phase-day ID. Can fetch multiple days for graphs."""
    try:
        user_id = current_user["id"]
        language = current_user.get("language", "en")

        today_phase_day_id = _resolve_phase_day_id(user_id, phase_day_id)

        if not today_phase_day_id:
            logger.info("Hormones requested but no phase_day_id could be resolved")
            return _empty_hormone_response(
                language,
                None,
                "No phase-day ID available. Please set your last period date or log a period.",
                include_history=days > 1,
            )

        if days > 1:
            phase_day_ids_list = get_previous_phase_day_ids(today_phase_day_id, max(1, days))
            unique_ids = list(dict.fromkeys(phase_day_ids_list))

            try:
                hormone_response = (
                    supabase.table("hormones_data")
                    .select(_HORMONES_DATA_SELECT)
                    .in_("id", unique_ids)
                    .execute()
                )
            except Exception:
                logger.exception("hormones_data batch query failed")
                raise

            rows = hormone_response.data or []
            by_id_lower = {}
            for row in rows:
                rid = row.get("id")
                if rid is not None:
                    by_id_lower[str(rid).lower()] = row

            hormone_history: List[Dict[str, Any]] = []
            for pid in phase_day_ids_list:
                key = pid.lower()
                hormone_data = by_id_lower.get(key)
                if hormone_data:
                    hormone_history.append(_history_point_from_row(hormone_data, pid))

            today_row = by_id_lower.get(today_phase_day_id.lower())
            if today_row:
                today_data: Dict[str, Any] = _hormone_row_to_today_payload(today_row)
                msg = None
            else:
                today_data = {}
                msg = "No data for this specific day"
                logger.info("No hormones_data row for phase_day_id=%s (multi-day response)", today_phase_day_id)

            out: Dict[str, Any] = {
                "today": today_data,
                "history": hormone_history,
                "language": language,
                "phase_day_id": today_phase_day_id,
                "disclaimer": HORMONE_DISCLAIMER,
            }
            if msg:
                out["message"] = msg
            return out

        try:
            response = (
                supabase.table("hormones_data")
                .select(_HORMONES_DATA_SELECT)
                .eq("id", today_phase_day_id)
                .execute()
            )
        except Exception:
            logger.exception("hormones_data single lookup failed")
            raise

        if response.data:
            return {
                **_hormone_row_to_today_payload(response.data[0]),
                "language": language,
                "disclaimer": HORMONE_DISCLAIMER,
                "phase_day_id": today_phase_day_id,
            }

        logger.info("No hormones_data row for phase_day_id=%s", today_phase_day_id)
        return {
            "today": {},
            "phase_day_id": today_phase_day_id,
            "language": language,
            "message": "No data for this specific day",
            "disclaimer": HORMONE_DISCLAIMER,
        }

    except Exception as e:
        logger.exception("get_hormones failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch hormones data: {str(e)}") from e


@router.get("/nutrition")
async def get_nutrition(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID. If not provided, uses today's phase-day ID"),
    language: str = Query("en", description="Language code"),
    cuisine: Optional[str] = Query(None, description="Optional strict cuisine filter (query); falls back to all rows if no match"),
    current_user: dict = Depends(get_current_user),
):
    """
    Nutrition for the resolved phase day.

    Rows are ranked by ``users.interests`` (e.g. South Indian) against ``cuisine`` / ``recipe_name``,
    then by ``favorite_cuisine`` as a boost. Optional ``cuisine`` query narrows results when matches exist;
    otherwise all phase-day recipes are returned, interest-matched first.
    """
    try:
        user_id = current_user["id"]

        resolved = _resolve_phase_day_id(user_id, phase_day_id)
        if not resolved:
            return {"recipes": [], "wholefoods": []}

        interests = _normalize_interests_list(current_user.get("interests"))
        favorite_cuisine = current_user.get("favorite_cuisine")
        favorite_cuisine = str(favorite_cuisine).strip() if favorite_cuisine else None
        cuisine_query = str(cuisine).strip() if cuisine is not None and str(cuisine).strip() else None

        table_name = f"nutrition_{language}"
        recipes_response = supabase.table(table_name).select("*").eq("hormone_id", resolved).execute()
        rows: List[Dict[str, Any]] = list(recipes_response.data or [])

        if cuisine_query:
            narrowed = [
                r
                for r in rows
                if _text_matches_interest(r.get("cuisine"), cuisine_query)
                or _text_matches_interest(r.get("recipe_name"), cuisine_query)
            ]
            if narrowed:
                rows = narrowed

        cuisine_boost = favorite_cuisine if cuisine_query is None else None
        ranked = _rank_rows_by_score(
            rows,
            lambda r: _nutrition_interest_score(r, interests, cuisine_boost),
        )

        return {
            "recipes": ranked,
            "wholefoods": [],
        }

    except Exception as e:
        logger.exception("get_nutrition failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch nutrition data: {str(e)}") from e


@router.get("/exercises")
async def get_exercises(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID. If not provided, uses today's phase-day ID"),
    language: str = Query("en", description="Language code"),
    category: Optional[str] = Query(None, description="Optional category filter; falls back to all rows if no match"),
    current_user: dict = Depends(get_current_user),
):
    """
    Exercises for the resolved phase day.

    Rows are ranked by ``users.interests`` (e.g. Yoga) against ``category``, ``exercise_name``, and
    ``description``. Optional ``category`` query narrows when matches exist; otherwise all rows are
    returned with interest matches first.
    """
    try:
        user_id = current_user["id"]

        resolved = _resolve_phase_day_id(user_id, phase_day_id)
        if not resolved:
            return {"exercises": []}

        interests = _normalize_interests_list(current_user.get("interests"))
        category_query = str(category).strip() if category is not None and str(category).strip() else None
        favorite_exercise = current_user.get("favorite_exercise")
        favorite_exercise = str(favorite_exercise).strip() if favorite_exercise else None

        table_name = f"exercises_{language}"
        response = supabase.table(table_name).select("*").eq("hormone_id", resolved).execute()
        rows: List[Dict[str, Any]] = list(response.data or [])

        if category_query:
            narrowed = [
                r
                for r in rows
                if _text_matches_interest(r.get("category"), category_query)
                or _text_matches_interest(r.get("exercise_name"), category_query)
            ]
            if narrowed:
                rows = narrowed

        category_boost = favorite_exercise if category_query is None else None
        ranked = _rank_rows_by_score(
            rows,
            lambda r: _exercise_interest_score(r, interests, category_boost),
        )

        return {
            "exercises": ranked,
        }

    except Exception as e:
        logger.exception("get_exercises failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch exercise data: {str(e)}") from e
