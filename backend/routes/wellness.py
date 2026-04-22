import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from cycle_utils import (
    calculate_today_phase_day_id,
    get_previous_phase_day_ids,
    get_user_phase_day,
    get_user_today,
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

class HormoneHistoryPoint(BaseModel):
    """One day in /wellness/hormones?days>1 history."""

    model_config = ConfigDict(extra="ignore")

    phase_day_id: str
    id: Optional[str] = None
    estrogen: Optional[str] = None
    estrogen_trend: Optional[str] = None
    progesterone: Optional[str] = None
    progesterone_trend: Optional[str] = None
    fsh: Optional[str] = None
    fsh_trend: Optional[str] = None
    lh: Optional[str] = None
    lh_trend: Optional[str] = None
    mood: Dict[str, Any] = Field(default_factory=dict)
    energy: Optional[Any] = None
    best_work_type: Dict[str, Any] = Field(default_factory=dict)


def get_hormone_trends_summary_for_llm(user_id: str, client_today_str: Optional[str] = None) -> str:
    """
    Short hormone trend summary for AI system prompts (same source as /wellness/hormones reference data).
    Safe to import from other modules; does not require a FastAPI request context.
    """
    resolved = _resolve_phase_day_id(user_id, None, client_today_str)
    if not resolved:
        return (
            "Hormone reference: no phase-day ID available for this user yet "
            "(they may need to log a period)."
        )
    try:
        r = (
            supabase.table("hormones_data_v2")
            .select(
                "id, estrogen, estrogen_trend, progesterone, progesterone_trend, "
                "fsh, fsh_trend, lh, lh_trend"
            )
            .eq("id", resolved)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("hormones_data_v2 lookup for LLM context failed")
        return f"Hormone reference: could not load trend data for phase day {resolved}."

    if not r.data:
        return f"Hormone reference: no trend row in database for phase day {resolved}."

    h = r.data[0]
    parts: List[str] = []
    for val_key, trend_key, label in (
        ("estrogen", "estrogen_trend", "Estrogen"),
        ("progesterone", "progesterone_trend", "Progesterone"),
        ("fsh", "fsh_trend", "FSH"),
        ("lh", "lh_trend", "LH"),
    ):
        ttxt = h.get(val_key)
        lab = str(ttxt).strip() if ttxt is not None and str(ttxt).strip() else None
        tr = h.get(trend_key)
        trend_s = str(tr).strip() if tr is not None and str(tr).strip() else None
        if lab and trend_s:
            parts.append(f"{label}: {lab} (trend {trend_s})")
        elif trend_s:
            parts.append(f"{label}: trend {trend_s}")
        elif lab:
            parts.append(f"{label}: {lab}")

    if not parts:
        return f"Hormone reference for phase day {resolved}: trend/label fields empty in reference data."

    return (
        "Typical mapped hormone trends for today (phase day "
        f"{resolved}): "
        + "; ".join(parts)
        + ". These are educational reference patterns only, not lab measurements."
    )


def _resolve_phase_day_id(
    user_id: str,
    phase_day_id: Optional[str],
    client_today_str: Optional[str] = None,
) -> Optional[str]:
    if phase_day_id:
        return phase_day_id.strip().lower()
    today_str = get_user_today(client_today_str).strftime("%Y-%m-%d")
    today_phase = get_user_phase_day(user_id, today_str, prefer_actual=True)
    if today_phase and today_phase.get("phase_day_id"):
        return str(today_phase["phase_day_id"]).strip().lower()
    calculated = calculate_today_phase_day_id(user_id, client_today_str)
    return str(calculated).strip().lower() if calculated else None


def _to_optional_text(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def _coerce_json_object(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _hormone_row_to_today_payload(hormone_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build API dict for hormones_data_v2 (TEXT hormone fields + JSONB objects)."""
    phase_day_id_from_db = hormone_data.get("id")
    mood_obj = _coerce_json_object(hormone_data.get("mood"))
    best_work_type_obj = _coerce_json_object(hormone_data.get("best_work_type"))
    return {
        "id": phase_day_id_from_db,
        "estrogen": _to_optional_text(hormone_data.get("estrogen")),
        "estrogen_trend": _to_optional_text(hormone_data.get("estrogen_trend")),
        "progesterone": _to_optional_text(hormone_data.get("progesterone")),
        "progesterone_trend": _to_optional_text(hormone_data.get("progesterone_trend")),
        "fsh": _to_optional_text(hormone_data.get("fsh")),
        "fsh_trend": _to_optional_text(hormone_data.get("fsh_trend")),
        "lh": _to_optional_text(hormone_data.get("lh")),
        "lh_trend": _to_optional_text(hormone_data.get("lh_trend")),
        "mood": mood_obj,
        "energy": hormone_data.get("energy"),
        "best_work_type": best_work_type_obj,
        # Compatibility extras
        "phase_day_id": phase_day_id_from_db,
        "energy_level": hormone_data.get("energy", {}).get("level")
        if isinstance(hormone_data.get("energy"), dict)
        else hormone_data.get("energy_level"),
        "emotional_summary": mood_obj.get("summary") if isinstance(mood_obj, dict) else None,
    }


def _history_point_from_row(hormone_data: Dict[str, Any], phase_day_id: str) -> Dict[str, Any]:
    row = HormoneHistoryPoint(
        phase_day_id=phase_day_id,
        id=_to_optional_text(hormone_data.get("id")),
        estrogen=_to_optional_text(hormone_data.get("estrogen")),
        estrogen_trend=_to_optional_text(hormone_data.get("estrogen_trend")),
        progesterone=_to_optional_text(hormone_data.get("progesterone")),
        progesterone_trend=_to_optional_text(hormone_data.get("progesterone_trend")),
        fsh=_to_optional_text(hormone_data.get("fsh")),
        fsh_trend=_to_optional_text(hormone_data.get("fsh_trend")),
        lh=_to_optional_text(hormone_data.get("lh")),
        lh_trend=_to_optional_text(hormone_data.get("lh_trend")),
        mood=_coerce_json_object(hormone_data.get("mood")),
        energy=hormone_data.get("energy"),
        best_work_type=_coerce_json_object(hormone_data.get("best_work_type")),
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
    client_today: Optional[str] = Query(
        None,
        description="Device calendar date YYYY-MM-DD; preferred over server/IST for 'today'",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Get hormone data for a specific phase day. Defaults to today's phase-day ID. Can fetch multiple days for graphs."""
    try:
        user_id = current_user["id"]
        language = current_user.get("language", "en")

        today_phase_day_id = _resolve_phase_day_id(user_id, phase_day_id, client_today)

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
                    supabase.table("hormones_data_v2")
                    .select(
                        "id, estrogen, estrogen_trend, progesterone, progesterone_trend, "
                        "fsh, fsh_trend, lh, lh_trend, mood, energy, best_work_type"
                    )
                    .in_("id", unique_ids)
                    .execute()
                )
            except Exception:
                logger.exception("hormones_data_v2 batch query failed")
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
                logger.info("No hormones_data_v2 row for phase_day_id=%s (multi-day response)", today_phase_day_id)

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
                supabase.table("hormones_data_v2")
                .select(
                    "id, estrogen, estrogen_trend, progesterone, progesterone_trend, "
                    "fsh, fsh_trend, lh, lh_trend, mood, energy, best_work_type"
                )
                .eq("id", today_phase_day_id)
                .execute()
            )
        except Exception:
            logger.exception("hormones_data_v2 single lookup failed")
            raise

        if response.data:
            return {
                **_hormone_row_to_today_payload(response.data[0]),
                "language": language,
                "disclaimer": HORMONE_DISCLAIMER,
                "phase_day_id": today_phase_day_id,
            }

        logger.info("No hormones_data_v2 row for phase_day_id=%s", today_phase_day_id)
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
    client_today: Optional[str] = Query(
        None,
        description="Device calendar date YYYY-MM-DD; preferred over server/IST for 'today'",
    ),
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

        resolved = _resolve_phase_day_id(user_id, phase_day_id, client_today)
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
    client_today: Optional[str] = Query(
        None,
        description="Device calendar date YYYY-MM-DD; preferred over server/IST for 'today'",
    ),
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

        resolved = _resolve_phase_day_id(user_id, phase_day_id, client_today)
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
