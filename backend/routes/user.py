import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, ConfigDict, model_validator

from auth_utils import get_password_hash, verify_password
from cycle_stats import update_user_cycle_stats
from cycle_utils import estimate_period_length
from database import supabase
from period_start_logs import sync_period_start_logs_from_period_logs
from prediction_cache import (
    hard_invalidate_predictions_from_date,
    invalidate_predictions_after_period,
    schedule_regenerate_predictions,
)
from routes.auth import get_current_user

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("periodcycle_ai.user")


def _strip_auth_secrets(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Never return password material to clients."""
    if not row:
        return {}
    out = dict(row)
    out.pop("password", None)
    out.pop("password_hash", None)
    return out


def _validate_new_password_strength(new_password: str) -> None:
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long.",
        )
    has_digit = bool(re.search(r"\d", new_password))
    has_special = bool(re.search(r"[^A-Za-z0-9]", new_password))
    if not has_digit and not has_special:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must include at least one number or one special character.",
        )


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_user_update_payload(base: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attach users.updated_at when the column exists (see database/schema.sql).
    If your deployment lacks this column, remove the line or add a DB trigger — see TODO below.
    """
    # TODO: Alternatively rely on a Postgres trigger: BEFORE UPDATE ON users SET NEW.updated_at = NOW()
    merged = {**base, "updated_at": _now_iso_utc()}
    return merged


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    avg_bleeding_days: Optional[int] = None
    allergies: Optional[list] = None
    language: Optional[str] = None
    favorite_cuisine: Optional[str] = None
    favorite_exercise: Optional[str] = None
    interests: Optional[list] = None


class NotificationPreferencesPayload(BaseModel):
    """Validated shape for users.notification_preferences (JSONB)."""

    model_config = ConfigDict(extra="ignore")

    upcoming_reminders: bool = True
    logging_reminders: bool = True
    health_alerts: bool = True
    pause_emails_until: Optional[str] = None
    snooze_this_cycle: bool = False

    @model_validator(mode="before")
    @classmethod
    def parse_jsonb(cls, data: Any) -> Any:
        if data is None:
            return {}
        if isinstance(data, str):
            stripped = data.strip()
            if not stripped:
                return {}
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                return {}
        if not isinstance(data, dict):
            return {}
        out = dict(data)
        if "upcoming_reminders" not in out and "period_reminders" in out:
            out["upcoming_reminders"] = out.get("period_reminders", True)
        if "logging_reminders" not in out and "period_reminders" in out:
            out["logging_reminders"] = out.get("period_reminders", True)
        if "health_alerts" not in out:
            out["health_alerts"] = True
        if "pause_emails_until" not in out:
            out["pause_emails_until"] = None
        if "snooze_this_cycle" not in out:
            out["snooze_this_cycle"] = False
        return out


class NotificationPreferencesUpdate(BaseModel):
    email_notifications_enabled: Optional[bool] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    upcoming_reminders: Optional[bool] = None
    logging_reminders: Optional[bool] = None
    health_alerts: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class RemoveItemRequest(BaseModel):
    type: str
    item: dict


@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile."""
    return _strip_auth_secrets(current_user)


@router.post("/profile")
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update user profile."""
    try:
        user_id = current_user["id"]
        update_data = profile_data.model_dump(exclude_unset=True)
        if "avg_bleeding_days" in update_data and update_data["avg_bleeding_days"] is not None:
            update_data["avg_bleeding_days"] = max(2, min(8, int(update_data["avg_bleeding_days"])))

        payload = _merge_user_update_payload(update_data)
        response = supabase.table("users").update(payload).eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile",
            )

        logger.info("Profile updated for user")
        return _strip_auth_secrets(response.data[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile update failed: {str(e)}",
        )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """Change user password."""
    try:
        user_id = current_user["id"]

        if not verify_password(password_data.current_password, current_user.get("password_hash", "")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        _validate_new_password_strength(password_data.new_password)

        new_password_hash = get_password_hash(password_data.new_password)
        payload = _merge_user_update_payload({"password_hash": new_password_hash})
        response = supabase.table("users").update(payload).eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password",
            )

        logger.info("Password changed for user")
        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}",
        )


@router.post("/remove-item")
async def remove_item(
    request: RemoveItemRequest,
    current_user: dict = Depends(get_current_user),
):
    """Remove item from user's saved items."""
    try:
        user_id = current_user["id"]

        if "saved_items" not in current_user:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Saved items feature is not available. The saved_items column does not exist in the database.",
            )

        saved_items = current_user.get("saved_items", {})
        item_type = request.type

        if item_type not in saved_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No saved {item_type} items found",
            )

        items_list = saved_items[item_type]
        items_list = [item for item in items_list if item != request.item]
        saved_items[item_type] = items_list

        payload = _merge_user_update_payload({"saved_items": saved_items})
        supabase.table("users").update(payload).eq("id", user_id).execute()

        logger.info("Saved item removed for user")
        return {
            "message": f"{item_type} item removed successfully",
            "removed": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove item: {str(e)}",
        )


def _coerce_notification_preferences(raw: Any) -> NotificationPreferencesPayload:
    """Normalize DB JSONB (dict or legacy JSON string) via Pydantic."""
    return NotificationPreferencesPayload.model_validate(raw)


@router.get("/notification-preferences")
async def get_notification_preferences(current_user: dict = Depends(get_current_user)):
    """Get user's notification preferences."""
    try:
        email_enabled = current_user.get("email_notifications_enabled", True)
        raw_prefs = current_user.get("notification_preferences")
        prefs = _coerce_notification_preferences(raw_prefs if raw_prefs is not None else {})

        return {
            "email_notifications_enabled": email_enabled,
            "notification_preferences": prefs.model_dump(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification preferences: {str(e)}",
        )


@router.post("/notification-preferences")
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update user's notification preferences."""
    try:
        user_id = current_user["id"]
        update_data: Dict[str, Any] = {}

        if preferences.email_notifications_enabled is not None:
            update_data["email_notifications_enabled"] = preferences.email_notifications_enabled

        current_prefs = _coerce_notification_preferences(
            current_user.get("notification_preferences")
        ).model_dump()

        if preferences.upcoming_reminders is not None:
            current_prefs["upcoming_reminders"] = preferences.upcoming_reminders
        if preferences.logging_reminders is not None:
            current_prefs["logging_reminders"] = preferences.logging_reminders
        if preferences.health_alerts is not None:
            current_prefs["health_alerts"] = preferences.health_alerts

        if preferences.notification_preferences is not None:
            merged = {**current_prefs, **preferences.notification_preferences}
            current_prefs = _coerce_notification_preferences(merged).model_dump()

        update_data["notification_preferences"] = current_prefs

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No preferences provided to update",
            )

        payload = _merge_user_update_payload(update_data)
        response = supabase.table("users").update(payload).eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update notification preferences",
            )

        updated_user = response.data[0]
        final_prefs = _coerce_notification_preferences(updated_user.get("notification_preferences"))

        logger.info("Notification preferences updated for user")
        return {
            "message": "Notification preferences updated successfully",
            "email_notifications_enabled": updated_user.get("email_notifications_enabled", True),
            "notification_preferences": final_prefs.model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification preferences: {str(e)}",
        )


@router.post("/reset-cycle-data")
async def reset_cycle_data(current_user: dict = Depends(get_current_user)):
    """
    Reset all cycle data for the user.

    Clears period logs, period_start_logs, and prediction cache (user_cycle_days) so
    stateless phase logic (e.g. calculate_phase_for_date_range) sees no stale cycles.
    """
    try:
        user_id = current_user["id"]

        supabase.table("period_logs").delete().eq("user_id", user_id).execute()
        logger.info("Deleted all period_logs for user reset")

        try:
            supabase.table("period_start_logs").delete().eq("user_id", user_id).execute()
            logger.info("Deleted all period_start_logs for user reset")
        except Exception:
            logger.warning("Error deleting period_start_logs (table may not exist)", exc_info=True)

        supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()
        logger.info("Deleted all user_cycle_days for user reset")

        # Ensure prediction cache is fully cleared if any rows survived RLS/edge cases
        try:
            await invalidate_predictions_after_period(user_id)
        except Exception:
            logger.warning("Prediction cache invalidation helper failed (non-fatal)", exc_info=True)

        update_data = _merge_user_update_payload(
            {
                "last_period_date": None,
                "cycle_length": 28,
            }
        )

        response = supabase.table("users").update(update_data).eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset user profile cycle fields",
            )

        logger.info("Cycle data reset completed for user")
        return {
            "message": "All cycle data has been reset successfully",
            "user": _strip_auth_secrets(response.data[0]),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset cycle data: {str(e)}",
        )


@router.post("/reset-last-period")
async def reset_last_period(current_user: dict = Depends(get_current_user)):
    """
    Reset only the most recently logged period start.

    Hard-invalidates phase cache from that date forward, rebuilds period_start_logs,
    refreshes stats, and regenerates predictions from the new last confirmed period.
    """
    try:
        user_id = current_user["id"]

        logs_response = (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )

        if not logs_response.data or len(logs_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No period logs found to reset",
            )

        last_period_log = logs_response.data[0]
        last_period_date_str = last_period_log["date"]

        if isinstance(last_period_date_str, str):
            last_period_date = datetime.strptime(last_period_date_str, "%Y-%m-%d").date()
        else:
            last_period_date = last_period_date_str

        if last_period_log.get("end_date"):
            end_date_str = last_period_log["end_date"]
            if isinstance(end_date_str, str):
                period_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            else:
                period_end_date = end_date_str
            logger.info("Resetting last period using stored end_date")
        else:
            period_length = estimate_period_length(user_id)
            period_length_days = int(round(max(3.0, min(8.0, period_length))))
            period_end_date = last_period_date + timedelta(days=period_length_days - 1)
            logger.info("Resetting last period using estimated bleed length")

        supabase.table("period_logs").delete().eq("id", last_period_log["id"]).execute()
        logger.info("Deleted most recent period log")

        # Hard invalidation: all cached phases on/after removed period start (stateless recompute baseline)
        hard_inv: Dict[str, Any] = {"cache_invalidated": False}
        try:
            hard_inv = await hard_invalidate_predictions_from_date(user_id, str(last_period_date_str))
        except Exception:
            logger.warning("hard_invalidate_predictions_from_date failed; narrowing cleanup", exc_info=True)
            if period_end_date:
                current_date = last_period_date
                while current_date <= period_end_date:
                    date_str = current_date.strftime("%Y-%m-%d")
                    try:
                        supabase.table("user_cycle_days").delete().eq("user_id", user_id).eq("date", date_str).execute()
                    except Exception:
                        logger.warning("Could not delete user_cycle_days for %s", date_str, exc_info=True)
                    current_date += timedelta(days=1)

        remaining_logs = (
            supabase.table("period_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )

        new_last_period_date = None
        if remaining_logs.data and len(remaining_logs.data) > 0:
            new_last_period_date = remaining_logs.data[0]["date"]

        user_update = supabase.table("users").update(
            _merge_user_update_payload({"last_period_date": new_last_period_date})
        ).eq("id", user_id).execute()

        if not user_update.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user's last_period_date",
            )

        updated_user = user_update.data[0]
        logger.info("Updated last_period_date after last-period reset")

        period_starts = sync_period_start_logs_from_period_logs(user_id)
        update_user_cycle_stats(user_id, period_starts=period_starts)
        logger.info("Synced period_start_logs and cycle stats after last-period reset")

        try:
            await invalidate_predictions_after_period(user_id)
        except Exception:
            logger.warning("invalidate_predictions_after_period after reset failed (non-fatal)", exc_info=True)

        schedule_regenerate_predictions(user_id, days_ahead=180)
        logger.info("Scheduled prediction cache regeneration after last-period reset")

        return {
            "message": "Last period has been reset successfully",
            "user": _strip_auth_secrets(updated_user),
            "deleted_period_date": last_period_date_str,
            "cacheInvalidated": bool(hard_inv.get("cache_invalidated", False)),
            "cacheInvalidation": hard_inv,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset last period: {str(e)}",
        )
