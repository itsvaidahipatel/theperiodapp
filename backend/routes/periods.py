import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from auto_close_periods import auto_close_open_periods
from cycle_stats import get_cycle_stats, update_user_cycle_stats
from cycle_utils import estimate_period_length, get_user_phase_day
from database import supabase
from luteal_learning import learn_luteal_from_new_period
from period_service import (
    MAX_CYCLE_DAYS,
    MIN_CYCLE_DAYS,
    can_log_period,
    check_anomaly,
    get_predictions,
    calculate_rolling_average,
    calculate_rolling_period_length,
)
from prediction_cache import hard_invalidate_predictions_from_date, schedule_regenerate_predictions
from period_start_logs import get_period_start_logs, sync_period_start_logs_from_period_logs
from routes.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

IDEMPOTENCY_WINDOW_SEC = 5


def parse_period_date(value: Union[str, date, datetime, None]) -> date:
    """Normalize API / DB date values to a date (accepts ISO str or date/datetime)."""
    if value is None:
        raise ValueError("date is required")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    raise TypeError(f"Unsupported date type: {type(value)}")


def _parse_db_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _within_idempotency_window(row: Dict[str, Any], seconds: int = IDEMPOTENCY_WINDOW_SEC) -> bool:
    ts = _parse_db_timestamp(row.get("updated_at")) or _parse_db_timestamp(row.get("created_at"))
    if not ts:
        return False
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return 0 <= age <= seconds


def _next_predicted_period_start(user_id: str) -> Optional[date]:
    """Next simple calendar predicted start after last confirmed period (pre-write snapshot)."""
    try:
        starts = get_period_start_logs(user_id, confirmed_only=True)
        if not starts:
            return None
        last_raw = starts[-1].get("start_date")
        if not last_raw:
            return None
        last_d = parse_period_date(last_raw)
        avg = calculate_rolling_average(user_id)
        cycle_int = int(round(avg))
        cycle_int = max(MIN_CYCLE_DAYS, min(cycle_int, MAX_CYCLE_DAYS))
        return last_d + timedelta(days=cycle_int)
    except Exception:
        logger.exception("Failed to compute next predicted period start")
        return None


def _medical_overlap_exception(existing_start: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "MEDICAL_OVERLAP",
            "message": (
                "This date falls within an existing logged period. "
                "You can merge logs or edit the existing period if needed."
            ),
            "existingPeriodStart": existing_start,
        },
    )


def _assemble_period_log_response(
    saved_row: Dict[str, Any],
    logs: List[Dict[str, Any]],
    predictions: Any,
    rolling_average: float,
    rolling_period_average: float,
    is_anomaly: bool,
    estimated_end_date: date,
    cache_invalidation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build POST /log JSON (no user_id / internal FKs in payloads)."""
    ci = cache_invalidation or {
        "cache_invalidated": False,
        "invalidation_date": str(saved_row.get("date") or ""),
        "deleted_count": 0,
    }
    return {
        "log": {
            "id": saved_row.get("id"),
            "date": saved_row.get("date"),
            "endDate": saved_row.get("end_date"),
            "isManualEnd": saved_row.get("is_manual_end", False),
            "flow": saved_row.get("flow"),
            "notes": saved_row.get("notes"),
            "isAnomaly": is_anomaly,
            "estimatedEnd": estimated_end_date.strftime("%Y-%m-%d"),
        },
        "logs": [
            {
                "id": log.get("id"),
                "date": log.get("date"),
                "endDate": log.get("end_date"),
                "isManualEnd": log.get("is_manual_end", False),
                "flow": log.get("flow"),
                "notes": log.get("notes"),
            }
            for log in logs
        ],
        "predictions": predictions,
        "rollingAverage": rolling_average,
        "rollingPeriodAverage": rolling_period_average,
        "cacheInvalidated": bool(ci.get("cache_invalidated", False)),
        "cacheInvalidation": ci,
    }


async def _parallel_fetch_post_log_bundle(
    user_id: str,
    saved_row: Dict[str, Any],
    is_anomaly: bool,
    estimated_end_date: date,
    cache_invalidation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    def fetch_logs():
        return (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .execute()
        )

    logs_res, predictions, rolling_average, rolling_period_average = await asyncio.gather(
        asyncio.to_thread(fetch_logs),
        asyncio.to_thread(get_predictions, user_id, 6),
        asyncio.to_thread(calculate_rolling_average, user_id),
        asyncio.to_thread(calculate_rolling_period_length, user_id),
    )
    logs = logs_res.data or []
    return _assemble_period_log_response(
        saved_row,
        logs,
        predictions,
        rolling_average,
        rolling_period_average,
        is_anomaly,
        estimated_end_date,
        cache_invalidation=cache_invalidation,
    )


class PeriodLogRequest(BaseModel):
    date: str
    end_date: Optional[str] = None
    bleeding_days: Optional[int] = None
    flow: Optional[str] = None
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class PeriodEndRequest(BaseModel):
    date: str


class PeriodLogUpdate(BaseModel):
    date: Optional[str] = None
    end_date: Optional[str] = None
    flow: Optional[str] = None
    notes: Optional[str] = None


class CycleStatsAPIResponse(BaseModel):
    """Public cycle stats shape; ignores unknown keys and never exposes raw user / FK fields."""

    model_config = ConfigDict(extra="ignore")

    totalCycles: int = 0
    averageCycleLength: float = 28.0
    averagePeriodLength: float = 5.0
    averagePeriodLengthRaw: Optional[float] = None
    averagePeriodLengthNormalized: Optional[float] = None
    isPeriodLengthOutsideRange: Optional[bool] = None
    periodLengthHealthAlert: Optional[bool] = None
    healthAlerts: Optional[Dict[str, Any]] = None
    cycleRegularity: str = "unknown"
    longestCycle: Optional[int] = None
    shortestCycle: Optional[int] = None
    longestPeriod: Optional[float] = None
    shortestPeriod: Optional[float] = None
    lastPeriodDate: Optional[str] = None
    daysSinceLastPeriod: Optional[int] = None
    anomalies: int = 0
    confidence: Dict[str, Any] = Field(default_factory=dict)
    insights: List[Any] = Field(default_factory=list)
    insightsKeys: List[Any] = Field(default_factory=list)
    insightsParams: List[Any] = Field(default_factory=list)
    cycleLengths: List[Any] = Field(default_factory=list)
    allCycles: List[Any] = Field(default_factory=list)
    bleedingEpisodes: List[Any] = Field(default_factory=list)


@router.post("/log")
async def log_period(
    log_data: PeriodLogRequest,
    client_today: Optional[str] = Query(None, description="Client local today (YYYY-MM-DD) to avoid UTC drift"),
    current_user: dict = Depends(get_current_user),
):
    """
    Log a period entry.

    Idempotency: same start date replay within a few seconds returns the same success payload
    without duplicating writes. Overlap inside an existing bleed window returns 409 MEDICAL_OVERLAP.
    """
    try:
        user_id = current_user["id"]
        date_obj = parse_period_date(log_data.date)

        from cycle_utils import get_user_today

        today = get_user_today(client_today)
        if date_obj > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot log period for future dates. Please log periods that have already occurred.",
            )

        existing_same_start = (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .eq("date", log_data.date)
            .limit(1)
            .execute()
        )
        existing_row = existing_same_start.data[0] if existing_same_start.data else None

        if existing_row and _within_idempotency_window(existing_row):
            is_anomaly = check_anomaly(user_id, date_obj)
            rolling_period_avg = await asyncio.to_thread(calculate_rolling_period_length, user_id)
            estimated_days = int(round(max(3.0, min(8.0, rolling_period_avg))))
            estimated_end_date = date_obj + timedelta(days=estimated_days - 1)
            logger.info("Returning idempotent /log response (recent duplicate submit)")
            return await _parallel_fetch_post_log_bundle(
                user_id, existing_row, is_anomaly, estimated_end_date
            )

        if not existing_row:
            validation = can_log_period(user_id, date_obj)
            if not validation.get("canLog", False):
                reason = validation.get("reason") or "Cannot log period for this date."
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

        auto_closed = auto_close_open_periods(user_id, client_today_str=client_today)
        if auto_closed:
            logger.info("Auto-closed %s open period(s) before new log", len(auto_closed))

        is_anomaly = check_anomaly(user_id, date_obj)

        period_length_days_for_check = max(2, min(8, int(current_user.get("avg_bleeding_days") or 5)))
        logs_check = supabase.table("period_logs").select("date", "end_date").eq("user_id", user_id).execute()
        for row in logs_check.data or []:
            start_date_str = row.get("date")
            if not start_date_str:
                continue
            if str(start_date_str) == str(log_data.date):
                continue
            start_date = parse_period_date(start_date_str)
            end_date_str = row.get("end_date")
            if end_date_str:
                end_date = parse_period_date(end_date_str)
            else:
                end_date = start_date + timedelta(days=period_length_days_for_check - 1)
            if start_date <= date_obj <= end_date:
                raise _medical_overlap_exception(str(start_date_str))

        if log_data.bleeding_days is not None:
            bleeding_days = max(2, min(8, int(log_data.bleeding_days)))
        else:
            bleeding_days = max(2, min(8, int(current_user.get("avg_bleeding_days") or 5)))
        estimated_end_date = date_obj + timedelta(days=bleeding_days - 1)
        end_date_value = estimated_end_date.strftime("%Y-%m-%d")
        is_manual_end_value = log_data.bleeding_days is not None
        logger.debug("Computed end_date=%s bleeding_days=%s", end_date_value, bleeding_days)

        prev_logs = (
            supabase.table("period_logs")
            .select("id", "date", "end_date", "is_manual_end")
            .eq("user_id", user_id)
            .lt("date", log_data.date)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if prev_logs.data:
            prev = prev_logs.data[0]
            prev_end = prev.get("end_date")
            prev_manual = prev.get("is_manual_end", True)
            if not prev_manual and prev_end:
                prev_end_dt = parse_period_date(prev_end)
                if prev_end_dt >= date_obj:
                    trim_end = date_obj - timedelta(days=1)
                    trim_end_str = trim_end.strftime("%Y-%m-%d")
                    supabase.table("period_logs").update({"end_date": trim_end_str}).eq("id", prev["id"]).execute()
                    logger.info("Trimmed previous period end to %s (overlap protection)", trim_end_str)

        log_entry = {
            "user_id": user_id,
            "date": log_data.date,
            "end_date": end_date_value,
            "is_manual_end": is_manual_end_value,
            "flow": log_data.flow,
            "notes": log_data.notes,
        }

        existing = (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .eq("date", log_data.date)
            .execute()
        )

        next_predicted_start: Optional[date] = None
        if not existing.data:
            next_predicted_start = _next_predicted_period_start(user_id)

        if existing.data:
            response = supabase.table("period_logs").update(log_entry).eq("user_id", user_id).eq("date", log_data.date).execute()
        else:
            response = supabase.table("period_logs").insert(log_entry).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create/update period log",
            )

        saved = response.data[0]
        logger.info("Period log saved start=%s end=%s manual_end=%s", log_data.date, end_date_value, is_manual_end_value)

        period_starts = sync_period_start_logs_from_period_logs(user_id, client_today_str=client_today)
        update_user_cycle_stats(user_id, period_starts=period_starts)

        logged_date = parse_period_date(log_data.date)
        predicted_phase_data = get_user_phase_day(user_id, log_data.date, prefer_actual=False)
        if predicted_phase_data and predicted_phase_data.get("phase") == "Period" and period_starts:
            for start_log in period_starts:
                if not start_log.get("is_confirmed", True):
                    start_date_str = start_log.get("start_date")
                    if start_date_str:
                        predicted_start = parse_period_date(start_date_str)
                        delta_days = abs((logged_date - predicted_start).days)
                        logger.debug(
                            "Period delta: %s days (predicted=%s actual=%s)",
                            delta_days,
                            predicted_start.isoformat(),
                            log_data.date,
                        )
                        if delta_days > 3:
                            logger.info("Large period delta (%s days); downstream may full recalc", delta_days)
                        break

        try:
            learn_luteal_from_new_period(user_id, log_data.date)
        except Exception:
            logger.exception("Luteal learning failed (non-blocking)")

        supabase.table("users").update({"last_period_date": log_data.date}).eq("id", user_id).execute()

        hard_inv: Dict[str, Any] = {
            "cache_invalidated": False,
            "invalidation_date": log_data.date,
            "deleted_count": 0,
        }
        if (
            not existing.data
            and next_predicted_start is not None
            and date_obj < next_predicted_start
        ):
            try:
                hard_inv = await hard_invalidate_predictions_from_date(user_id, log_data.date)
            except Exception:
                logger.warning(
                    "hard_invalidate_predictions_from_date failed after early period log",
                    exc_info=True,
                )
            if hard_inv.get("cache_invalidated"):
                schedule_regenerate_predictions(user_id, days_ahead=180)

        rolling_period_avg = calculate_rolling_period_length(user_id)
        estimated_days = int(round(max(3.0, min(8.0, rolling_period_avg))))
        display_estimated_end = date_obj + timedelta(days=estimated_days - 1)

        return await _parallel_fetch_post_log_bundle(
            user_id, saved, is_anomaly, display_estimated_end, cache_invalidation=hard_inv
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log period: {str(e)}",
        )


@router.get("/logs")
async def get_period_logs(current_user: dict = Depends(get_current_user)):
    """Get all period logs for the current user. Returns camelCase."""
    try:
        user_id = current_user["id"]

        response = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date", desc=False).execute()

        logs = [
            {
                "id": log.get("id"),
                "startDate": log.get("date"),
                "endDate": log.get("end_date"),
                "isManualEnd": log.get("is_manual_end", False),
                "flow": log.get("flow"),
                "notes": log.get("notes"),
                "isAnomaly": False,
            }
            for log in (response.data or [])
        ]

        return logs

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch period logs: {str(e)}",
        )


@router.get("/predictions")
async def get_predictions_endpoint(
    count: int = 6,
    client_today: Optional[str] = Query(None, description="Client local today (YYYY-MM-DD) to avoid UTC drift"),
    current_user: dict = Depends(get_current_user),
):
    """Get predictions with confidence levels. Returns camelCase."""
    try:
        user_id = current_user["id"]
        language = current_user.get("language", "en")

        pred_bundle = get_predictions(user_id, count=count, language=language, client_today_str=client_today)
        predictions = pred_bundle.get("predictions", [])
        is_late = bool(pred_bundle.get("is_late", False))
        rolling_average = calculate_rolling_average(user_id)
        rolling_period_average = calculate_rolling_period_length(user_id)
        confidence = get_cycle_stats(user_id, language=language).get("confidence", {})

        return {
            "predictions": predictions,
            "isLate": is_late,
            "rollingAverage": rolling_average,
            "rollingPeriodAverage": rolling_period_average,
            "confidence": confidence,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch predictions: {str(e)}",
        )


@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)) -> CycleStatsAPIResponse:
    """Get comprehensive cycle statistics (sanitized public model)."""
    try:
        user_id = current_user["id"]
        language = current_user.get("language", "en")
        stats = get_cycle_stats(user_id, language=language)
        return CycleStatsAPIResponse.model_validate(stats)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}",
        )


@router.get("/episodes")
async def get_period_episodes(current_user: dict = Depends(get_current_user)):
    """
    Get period episodes (start dates + predicted end dates) for calendar rendering.
    """
    try:
        user_id = current_user["id"]

        period_starts = get_period_start_logs(user_id, confirmed_only=False)

        predicted_length = 5

        episodes = []
        for start_log in period_starts:
            start_date_str = start_log["start_date"]
            start_date = parse_period_date(start_date_str)

            predicted_end_date = start_date + timedelta(days=predicted_length - 1)

            episodes.append(
                {
                    "start_date": start_date_str,
                    "predicted_end_date": predicted_end_date.strftime("%Y-%m-%d"),
                    "predicted_length": predicted_length,
                    "is_confirmed": start_log.get("is_confirmed", False),
                }
            )

        return episodes

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch period episodes: {str(e)}",
        )


@router.put("/log/{log_id}")
async def update_period_log(
    log_id: str,
    log_data: PeriodLogUpdate,
    client_today: Optional[str] = Query(None, description="Client local today (YYYY-MM-DD) to avoid UTC drift"),
    current_user: dict = Depends(get_current_user),
):
    """
    Update a period log entry with SMART RECALCULATION.
    """
    try:
        user_id = current_user["id"]

        check = supabase.table("period_logs").select("*").eq("id", log_id).eq("user_id", user_id).execute()

        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found",
            )

        old_log = check.data[0]
        old_date = old_log.get("date")
        new_date = log_data.date

        if new_date and new_date != old_date:
            logger.info("Editing period log start date from %s to %s", old_date, new_date)

            new_date_obj = parse_period_date(new_date)

            from cycle_utils import get_user_today

            today = get_user_today(client_today)
            if new_date_obj > today:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set period start to a future date",
                )

            validation = can_log_period(user_id, new_date_obj)
            if not validation.get("canLog", False):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation.get("reason", "Cannot update period to this date"),
                )

            old_date_obj = parse_period_date(old_date)

            old_period_end = None
            if old_log.get("end_date"):
                old_end_date_str = old_log["end_date"]
                old_period_end = parse_period_date(old_end_date_str)
                logger.debug("Using actual end_date for old period: %s", old_period_end.isoformat())
            else:
                period_length = estimate_period_length(user_id)
                period_length_days = int(round(max(3.0, min(8.0, period_length))))
                old_period_end = old_date_obj + timedelta(days=period_length_days - 1)
                logger.debug(
                    "Using estimated end_date for old period: %s (%s days)",
                    old_period_end.isoformat(),
                    period_length_days,
                )

            if old_period_end:
                current_date = old_date_obj
                deleted_count = 0
                while current_date <= old_period_end:
                    date_str = current_date.strftime("%Y-%m-%d")
                    try:
                        supabase.table("user_cycle_days").delete().eq("user_id", user_id).eq("date", date_str).eq("phase", "Period").execute()
                        deleted_count += 1
                    except Exception:
                        logger.warning("Could not delete old predictions for %s", date_str, exc_info=True)
                    current_date += timedelta(days=1)

                logger.info(
                    "Deleted %s old period range predictions (%s to %s)",
                    deleted_count,
                    old_date,
                    old_period_end.strftime("%Y-%m-%d"),
                )
            else:
                logger.warning("Could not determine old_period_end; skipping old predictions deletion")

            update_data = log_data.model_dump(exclude_unset=True)

            if "end_date" in update_data and update_data["end_date"]:
                if new_date:
                    new_date_obj_for_validation = parse_period_date(new_date)
                else:
                    new_date_obj_for_validation = old_date_obj

                end_date_obj_update = parse_period_date(update_data["end_date"])

                if end_date_obj_update < new_date_obj_for_validation:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"End date ({update_data['end_date']}) cannot be before start date ({new_date or old_date})",
                    )

                update_data["is_manual_end"] = True
                logger.info("Updating end_date to %s (manual)", update_data["end_date"])
            elif "end_date" in update_data and update_data["end_date"] is None:
                update_data["is_manual_end"] = False
                logger.info("Clearing end_date (estimated length)")

            response = supabase.table("period_logs").update(update_data).eq("id", log_id).execute()

            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update period log",
                )

            period_starts = sync_period_start_logs_from_period_logs(user_id, client_today_str=client_today)
            update_user_cycle_stats(user_id, period_starts=period_starts)

            if new_date == old_date or new_date > old_date:
                logs_response = (
                    supabase.table("period_logs")
                    .select("date")
                    .eq("user_id", user_id)
                    .order("date", desc=True)
                    .limit(1)
                    .execute()
                )
                if logs_response.data and logs_response.data[0].get("date") == new_date:
                    supabase.table("users").update({"last_period_date": new_date}).eq("id", user_id).execute()
                    logger.info("Updated last_period_date to %s", new_date)

            return {
                "log": response.data[0],
                "message": f"Period start date updated from {old_date} to {new_date}. Calendar has been recalculated.",
            }
        else:
            update_data = log_data.model_dump(exclude_unset=True)
            response = supabase.table("period_logs").update(update_data).eq("id", log_id).execute()

            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update period log",
                )

            return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update period log: {str(e)}",
        )


@router.delete("/log/{log_id}")
async def delete_period_log(
    log_id: str,
    client_today: Optional[str] = Query(None, description="Client local today (YYYY-MM-DD) for snapshot sync"),
    current_user: dict = Depends(get_current_user),
):
    """Delete a period log entry. Recalculates predictions."""
    try:
        user_id = current_user["id"]

        check = supabase.table("period_logs").select("id").eq("id", log_id).eq("user_id", user_id).execute()

        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found",
            )

        supabase.table("period_logs").delete().eq("id", log_id).execute()

        period_starts = sync_period_start_logs_from_period_logs(user_id, client_today_str=client_today)
        update_user_cycle_stats(user_id, period_starts=period_starts)

        return {"message": "Period log deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete period log: {str(e)}",
        )


@router.post("/log-end")
async def log_period_end(
    end_data: PeriodEndRequest,
    client_today: Optional[str] = Query(None, description="Client local today (YYYY-MM-DD) to avoid UTC drift"),
    current_user: dict = Depends(get_current_user),
):
    """Log a period end date."""
    try:
        user_id = current_user["id"]

        end_date_obj = parse_period_date(end_data.date)

        from cycle_utils import get_user_today

        today = get_user_today(client_today)
        if end_date_obj > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot log period end for future dates.",
            )

        logs_response = (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .is_("end_date", "null")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )

        if not logs_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No open period found. Please log a period start first.",
            )

        last_log = logs_response.data[0]
        start_date_str = last_log["date"]
        start_date_obj = parse_period_date(start_date_str)

        if end_date_obj < start_date_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Period end date must be after start date.",
            )

        duration = (end_date_obj - start_date_obj).days + 1
        if duration < 3 or duration > 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Period duration must be between 3 and 15 days. Calculated duration: {duration} days.",
            )

        update_response = (
            supabase.table("period_logs")
            .update(
                {
                    "end_date": end_data.date,
                    "is_manual_end": True,
                }
            )
            .eq("id", last_log["id"])
            .execute()
        )

        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update period log with end date.",
            )

        period_starts = sync_period_start_logs_from_period_logs(user_id, client_today_str=client_today)
        update_user_cycle_stats(user_id, period_starts=period_starts)

        return {
            "message": f"Period end logged successfully. Duration: {duration} days.",
            "start_date": start_date_str,
            "end_date": end_data.date,
            "duration": duration,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log period end: {str(e)}",
        )


@router.patch("/log/{log_id}/anomaly")
async def toggle_anomaly(
    log_id: str,
    client_today: Optional[str] = Query(None, description="Client local today (YYYY-MM-DD) for snapshot sync"),
    current_user: dict = Depends(get_current_user),
):
    """
    Toggle user-marked anomaly for this period start. Persists to period_start_logs.is_outlier
    so Bayesian / rolling stats exclude this cycle.
    """
    try:
        user_id = current_user["id"]

        check = supabase.table("period_logs").select("id, date").eq("id", log_id).eq("user_id", user_id).execute()

        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Period log not found",
            )

        start_str = check.data[0]["date"]
        sync_period_start_logs_from_period_logs(user_id, client_today_str=client_today)

        ps = (
            supabase.table("period_start_logs")
            .select("is_outlier")
            .eq("user_id", user_id)
            .eq("start_date", start_str)
            .limit(1)
            .execute()
        )
        current_flag = bool(ps.data[0].get("is_outlier")) if ps.data else False
        new_flag = not current_flag

        supabase.table("period_start_logs").update({"is_outlier": new_flag}).eq("user_id", user_id).eq("start_date", start_str).execute()

        logger.info("Toggled is_outlier for cycle start (user anomaly)")

        return {"isOutlier": new_flag, "startDate": start_str}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle anomaly: {str(e)}",
        )
