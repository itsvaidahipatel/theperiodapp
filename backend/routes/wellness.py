"""
Wellness routes (hormones, nutrition, exercises): all handlers depend on ``get_current_user``.
The account scope is always ``authenticated_subject_id(current_user)`` (JWT ``sub`` / ``users.id``).
Query parameters such as ``phase_day_id`` refer to cycle *template* ids (e.g. p1, f5), not user UUIDs.
All API ``phase_day_id`` (and hormone ``id``) values are normalized to lowercase. Nutrition and exercise
rows load by resolved ``hormone_id`` alone; ``hormones_data_v2`` is not required for those endpoints.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from cycle_utils import (
    calculate_today_phase_day_id,
    get_previous_phase_day_ids,
    get_user_phase_day,
    get_user_today,
)
from database import supabase
from routes.auth import authenticated_subject_id, get_current_user

router = APIRouter()
logger = logging.getLogger("periodcycle_ai.wellness")

# hormones_data_v2 — keep selects aligned with database/schema.sql
HORMONES_DATA_V2_SELECT = (
    "id, phase_id, day_number, estrogen, estrogen_trend, progesterone, progesterone_trend, "
    "fsh, fsh_trend, lh, lh_trend, mood, energy, best_work_type, created_at, updated_at"
)

# nutrition_* — explicit columns only (must match nutrition_en / hi / gu).
NUTRITION_TABLE_SELECT = (
    "id, hormone_id, phase_id, day_number, cuisine, recipe_name, serves, "
    "ingredients, steps, photo_url, nutrients"
)

# exercises_* — subset of wellness columns that exist on exercise tables (see nutrition for cuisine fields).
EXERCISES_TABLE_SELECT = (
    "id, hormone_id, category, exercise_name, steps, photo_url, energy_level"
)

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
    steps = row.get("steps")
    for interest in interests:
        if (
            _text_matches_interest(cat, interest)
            or _text_matches_interest(name, interest)
            or _text_matches_interest(desc, interest)
            or _text_matches_interest(steps, interest)
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


def _v2_id_lowercase(row: Optional[Dict[str, Any]]) -> Optional[str]:
    """``hormones_data_v2.id`` normalized to lowercase for API responses and FK filters."""
    if not row:
        return None
    rid = row.get("id")
    if rid is None:
        return None
    s = str(rid).strip().lower()
    return s if s else None


def _response_phase_day_id(row: Optional[Dict[str, Any]], resolved_lower: str) -> str:
    """Resolved phase template id (always lowercase); prefer v2 row id when present."""
    cid = _v2_id_lowercase(row)
    return cid if cid else resolved_lower


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


def _optional_int(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _energy_to_text(raw: Any) -> Optional[str]:
    """``hormones_data_v2.energy`` is TEXT; coerce legacy JSON-shaped values if present."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _to_optional_text(raw.get("level"))
    return _to_optional_text(raw)


def _hormone_row_to_today_payload(hormone_data: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize one ``hormones_data_v2`` row: hormone levels, trends, mood, energy, ``best_work_type``."""
    cid = _v2_id_lowercase(hormone_data)
    return {
        "id": cid,
        "phase_day_id": cid,
        "phase_id": _optional_int(hormone_data.get("phase_id")),
        "day_number": _optional_int(hormone_data.get("day_number")),
        "estrogen": _to_optional_text(hormone_data.get("estrogen")),
        "estrogen_trend": _to_optional_text(hormone_data.get("estrogen_trend")),
        "progesterone": _to_optional_text(hormone_data.get("progesterone")),
        "progesterone_trend": _to_optional_text(hormone_data.get("progesterone_trend")),
        "fsh": _to_optional_text(hormone_data.get("fsh")),
        "fsh_trend": _to_optional_text(hormone_data.get("fsh_trend")),
        "lh": _to_optional_text(hormone_data.get("lh")),
        "lh_trend": _to_optional_text(hormone_data.get("lh_trend")),
        "mood": _coerce_json_object(hormone_data.get("mood")),
        "energy": _energy_to_text(hormone_data.get("energy")),
        "best_work_type": _coerce_json_object(hormone_data.get("best_work_type")),
        "created_at": hormone_data.get("created_at"),
        "updated_at": hormone_data.get("updated_at"),
    }


def _empty_hormone_response(
    language: str,
    phase_day_id: Optional[str],
    message: str,
    include_history: bool = False,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "today": {},
        "language": language,
        "phase_day_id": phase_day_id.strip().lower() if isinstance(phase_day_id, str) and phase_day_id.strip() else phase_day_id,
        "message": message,
        "disclaimer": HORMONE_DISCLAIMER,
    }
    if include_history:
        out["history"] = []
    return out


@router.get("/hormones")
async def get_hormones(
    phase_day_id: Optional[str] = Query(
        None,
        description="Cycle template phase-day id (e.g. p1, f5)—not a user UUID. Omitted: derived from the authenticated user's logs.",
    ),
    days: int = Query(5, description="Number of days to fetch (default 5: last 4 days + today)"),
    client_today: Optional[str] = Query(
        None,
        description="Device calendar date YYYY-MM-DD; preferred over server/IST for 'today'",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Get hormone data for a specific phase day. Defaults to today's phase-day ID. Can fetch multiple days for graphs."""
    try:
        user_id = authenticated_subject_id(current_user)
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
                    .select(HORMONES_DATA_V2_SELECT)
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
                    hormone_history.append(_hormone_row_to_today_payload(hormone_data))

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
                "phase_day_id": _response_phase_day_id(today_row, today_phase_day_id),
                "disclaimer": HORMONE_DISCLAIMER,
            }
            if msg:
                out["message"] = msg
            return out

        try:
            response = (
                supabase.table("hormones_data_v2")
                .select(HORMONES_DATA_V2_SELECT)
                .eq("id", today_phase_day_id)
                .execute()
            )
        except Exception:
            logger.exception("hormones_data_v2 single lookup failed")
            raise

        if response.data:
            row0 = response.data[0]
            payload = _hormone_row_to_today_payload(row0)
            return {
                **payload,
                "language": language,
                "disclaimer": HORMONE_DISCLAIMER,
                "phase_day_id": _response_phase_day_id(row0, today_phase_day_id),
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


def _sort_nutrition_by_recipe_name(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: str(r.get("recipe_name") or "").lower())


@router.get("/nutrition")
async def get_nutrition(
    phase_day_id: Optional[str] = Query(
        None,
        description="Cycle template phase-day id—not a user UUID. Omitted: derived for the authenticated user.",
    ),
    language: str = Query("en", description="Language code"),
    cuisine: Optional[str] = Query(
        None,
        description="Optional cuisine filter: try hormone_id+cuisine first; if no rows, return all recipes for the phase.",
    ),
    client_today: Optional[str] = Query(
        None,
        description="Device calendar date YYYY-MM-DD; preferred over server/IST for 'today'",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Nutrition for the resolved phase (``hormone_id`` = resolved template id, lowercase).

    Optional ``cuisine``: query with cuisine ILIKE first; if no rows, fetch all recipes for that ``hormone_id``.

    Results are ordered by ``recipe_name``. Rows may be re-ranked by profile interests when present.
    """
    try:
        user_id = authenticated_subject_id(current_user)

        if phase_day_id is not None:
            pid = str(phase_day_id).strip().lower()
            phase_day_id = pid if pid else None

        resolved = _resolve_phase_day_id(user_id, phase_day_id, client_today)
        if not resolved:
            return {"recipes": [], "phase_day_id": None}

        hormone_key = resolved.lower().strip()

        interests = _normalize_interests_list(current_user.get("interests"))
        favorite_cuisine = current_user.get("favorite_cuisine")
        favorite_cuisine = str(favorite_cuisine).strip() if favorite_cuisine else None
        cuisine_query = str(cuisine).strip().lower() if cuisine is not None and str(cuisine).strip() else None

        lang = str(language or "en").strip().lower()
        table_name = f"nutrition_{lang}"
        tbl = supabase.table(table_name)

        def _fetch_by_hormone_only() -> List[Dict[str, Any]]:
            """All recipes for this phase; case-insensitive ``hormone_id`` (DB may store ``P3`` vs ``p3``)."""
            r = (
                tbl.select(NUTRITION_TABLE_SELECT)
                .ilike("hormone_id", hormone_key)
                .order("recipe_name")
                .execute()
            )
            return list(r.data or [])

        rows: List[Dict[str, Any]]
        if cuisine_query:
            r_narrow = (
                tbl.select(NUTRITION_TABLE_SELECT)
                .ilike("hormone_id", hormone_key)
                .ilike("cuisine", f"%{cuisine_query}%")
                .order("recipe_name")
                .execute()
            )
            rows = list(r_narrow.data or [])
            if not rows:
                rows = _fetch_by_hormone_only()
        else:
            rows = _fetch_by_hormone_only()

        rows = _sort_nutrition_by_recipe_name(rows)

        if not interests and not favorite_cuisine:
            return {"recipes": rows, "phase_day_id": hormone_key}

        cuisine_boost = favorite_cuisine if cuisine_query is None else None
        ranked = _rank_rows_by_score(
            rows,
            lambda r: _nutrition_interest_score(r, interests, cuisine_boost),
        )

        return {"recipes": ranked, "phase_day_id": hormone_key}

    except Exception as e:
        logger.exception("get_nutrition failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch nutrition data: {str(e)}") from e


@router.get("/exercises")
async def get_exercises(
    phase_day_id: Optional[str] = Query(
        None,
        description="Cycle template phase-day id—not a user UUID. Omitted: derived for the authenticated user.",
    ),
    language: str = Query("en", description="Language code"),
    category: Optional[str] = Query(None, description="Optional category filter; falls back to all rows if no match"),
    client_today: Optional[str] = Query(
        None,
        description="Device calendar date YYYY-MM-DD; preferred over server/IST for 'today'",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Exercises for the resolved phase (``hormone_id`` = resolved template id, lowercase).

    Rows are ranked by ``users.interests`` against ``category``, ``exercise_name``, and ``steps``
    (and legacy ``description`` when present). Optional ``category`` query narrows when matches exist;
    otherwise all rows are returned with interest matches first.
    """
    try:
        user_id = authenticated_subject_id(current_user)

        if phase_day_id is not None:
            pid = str(phase_day_id).strip().lower()
            phase_day_id = pid if pid else None

        resolved = _resolve_phase_day_id(user_id, phase_day_id, client_today)
        if not resolved:
            return {"exercises": []}

        hormone_key = resolved.lower().strip()

        interests = _normalize_interests_list(current_user.get("interests"))
        category_query = str(category).strip() if category is not None and str(category).strip() else None
        favorite_exercise = current_user.get("favorite_exercise")
        favorite_exercise = str(favorite_exercise).strip() if favorite_exercise else None

        table_name = f"exercises_{language}"
        response = (
            supabase.table(table_name)
            .select(EXERCISES_TABLE_SELECT)
            .eq("hormone_id", hormone_key)
            .execute()
        )
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

        # Neutral sort when user has no preference signals.
        if not interests and not favorite_exercise:
            return {
                "exercises": rows,
            }

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
