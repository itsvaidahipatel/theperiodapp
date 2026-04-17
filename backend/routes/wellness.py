import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

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
            .select("id, estrogen_trend, progesterone_trend, fsh_trend, lh_trend")
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
    for key, label in (
        ("estrogen_trend", "Estrogen"),
        ("progesterone_trend", "Progesterone"),
        ("fsh_trend", "FSH"),
        ("lh_trend", "LH"),
    ):
        v = h.get(key)
        if v is not None and str(v).strip():
            parts.append(f"{label}: {v}")

    if not parts:
        return f"Hormone reference for phase day {resolved}: trend fields empty in reference data."

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


def _hormone_row_to_today_payload(hormone_data: Dict[str, Any]) -> Dict[str, Any]:
    phase_day_id_from_db = hormone_data.get("id")
    return {
        "id": phase_day_id_from_db,
        "phase_day_id": phase_day_id_from_db,
        "phase_id": hormone_data.get("phase_id"),
        "day_number": hormone_data.get("day_number"),
        "estrogen": hormone_data.get("estrogen"),
        "estrogen_trend": hormone_data.get("estrogen_trend"),
        "progesterone": hormone_data.get("progesterone"),
        "progesterone_trend": hormone_data.get("progesterone_trend"),
        "fsh": hormone_data.get("fsh"),
        "fsh_trend": hormone_data.get("fsh_trend"),
        "lh": hormone_data.get("lh"),
        "lh_trend": hormone_data.get("lh_trend"),
        "mood": hormone_data.get("mood"),
        "energy": hormone_data.get("energy"),
        "best_work_type": hormone_data.get("best_work_type"),
        "brain_note": hormone_data.get("brain_note"),
        "energy_level": hormone_data.get("energy", {}).get("level")
        if isinstance(hormone_data.get("energy"), dict)
        else None,
        "emotional_summary": hormone_data.get("mood", {}).get("summary")
        if isinstance(hormone_data.get("mood"), dict)
        else None,
        "physical_summary": hormone_data.get("brain_note", {}).get("summary")
        if isinstance(hormone_data.get("brain_note"), dict)
        else None,
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
                    supabase.table("hormones_data").select("*").in_("id", unique_ids).execute()
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
                    hormone_history.append(
                        {
                            "phase_day_id": pid,
                            "estrogen": parse_hormone_value(hormone_data.get("estrogen")),
                            "progesterone": parse_hormone_value(hormone_data.get("progesterone")),
                            "fsh": parse_hormone_value(hormone_data.get("fsh")),
                            "lh": parse_hormone_value(hormone_data.get("lh")),
                        }
                    )

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
            response = supabase.table("hormones_data").select("*").eq("id", today_phase_day_id).execute()
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
    cuisine: Optional[str] = Query(None, description="Cuisine filter"),
    current_user: dict = Depends(get_current_user),
):
    """Get nutrition data for a specific phase day. Defaults to today's phase-day ID."""
    try:
        user_id = current_user["id"]

        resolved = _resolve_phase_day_id(user_id, phase_day_id)
        if not resolved:
            return {"recipes": [], "wholefoods": []}

        effective_cuisine = cuisine if cuisine is not None else current_user.get("favorite_cuisine")
        if effective_cuisine is not None:
            effective_cuisine = str(effective_cuisine).strip() or None

        table_name = f"nutrition_{language}"
        query = supabase.table(table_name).select("*").eq("hormone_id", resolved)

        if effective_cuisine:
            query = query.eq("cuisine", effective_cuisine)

        recipes_response = query.execute()

        return {
            "recipes": recipes_response.data or [],
            "wholefoods": [],
        }

    except Exception as e:
        logger.exception("get_nutrition failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch nutrition data: {str(e)}") from e


@router.get("/exercises")
async def get_exercises(
    phase_day_id: Optional[str] = Query(None, description="Phase day ID. If not provided, uses today's phase-day ID"),
    language: str = Query("en", description="Language code"),
    category: Optional[str] = Query(None, description="Exercise category"),
    current_user: dict = Depends(get_current_user),
):
    """Get exercise data for a specific phase day. Defaults to today's phase-day ID."""
    try:
        user_id = current_user["id"]

        resolved = _resolve_phase_day_id(user_id, phase_day_id)
        if not resolved:
            return {"exercises": []}

        table_name = f"exercises_{language}"
        query = supabase.table(table_name).select("*").eq("hormone_id", resolved)
        if category:
            logger.debug("Exercise category filter requested but not applied (schema may vary): %s", category)

        response = query.execute()

        return {
            "exercises": response.data or [],
        }

    except Exception as e:
        logger.exception("get_exercises failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch exercise data: {str(e)}") from e
