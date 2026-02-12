from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
import json

from database import supabase
from auth_utils import get_password_hash, verify_password
from routes.auth import get_current_user
from datetime import timedelta
from cycle_utils import estimate_period_length
from period_start_logs import sync_period_start_logs_from_period_logs
from prediction_cache import regenerate_predictions_from_last_confirmed_period
from cycle_stats import update_user_cycle_stats

router = APIRouter()
security = HTTPBearer()

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    # cycle_length and last_period_date are NOT updatable via profile (managed automatically)
    avg_bleeding_days: Optional[int] = None  # Typical bleeding length (2-8), used for auto end_date
    allergies: Optional[list] = None
    language: Optional[str] = None
    favorite_cuisine: Optional[str] = None
    favorite_exercise: Optional[str] = None
    interests: Optional[list] = None

class NotificationPreferencesUpdate(BaseModel):
    email_notifications_enabled: Optional[bool] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    # New fields for clean email system
    upcoming_reminders: Optional[bool] = None
    logging_reminders: Optional[bool] = None
    health_alerts: Optional[bool] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class RemoveItemRequest(BaseModel):
    type: str  # "recipe" | "wholeFood" | "dessert"
    item: dict

@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile."""
    current_user.pop("password_hash", None)
    return current_user

@router.post("/profile")
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile."""
    try:
        user_id = current_user["id"]
        update_data = profile_data.dict(exclude_unset=True)
        # Clamp avg_bleeding_days to 2-8 if present
        if "avg_bleeding_days" in update_data and update_data["avg_bleeding_days"] is not None:
            update_data["avg_bleeding_days"] = max(2, min(8, int(update_data["avg_bleeding_days"])))
        # Note: updated_at column doesn't exist in database, so we skip it

        response = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )
        
        updated_user = response.data[0]
        updated_user.pop("password", None)
        
        return updated_user
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile update failed: {str(e)}"
        )

@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """Change user password."""
    try:
        user_id = current_user["id"]
        
        # Verify current password
        if not verify_password(password_data.current_password, current_user.get("password_hash", "")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        new_password_hash = get_password_hash(password_data.new_password)
        
        # Update password
        response = supabase.table("users").update({
            "password_hash": new_password_hash
        }).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password"
            )
        
        return {"message": "Password changed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )

@router.post("/remove-item")
async def remove_item(
    request: RemoveItemRequest,
    current_user: dict = Depends(get_current_user)
):
    """Remove item from user's saved items."""
    try:
        user_id = current_user["id"]
        
        # Check if saved_items column exists in database
        # If not, return a message that this feature is not available
        if "saved_items" not in current_user:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Saved items feature is not available. The saved_items column does not exist in the database."
            )
        
        # Get current saved items
        saved_items = current_user.get("saved_items", {})
        item_type = request.type
        
        if item_type not in saved_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No saved {item_type} items found"
            )
        
        # Remove item from list
        items_list = saved_items[item_type]
        items_list = [item for item in items_list if item != request.item]
        
        # Update saved items
        saved_items[item_type] = items_list
        
        response = supabase.table("users").update({
            "saved_items": saved_items
        }).eq("id", user_id).execute()
        
        return {
            "message": f"{item_type} item removed successfully",
            "removed": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove item: {str(e)}"
        )

@router.get("/notification-preferences")
async def get_notification_preferences(current_user: dict = Depends(get_current_user)):
    """Get user's notification preferences."""
    try:
        user_id = current_user["id"]
        
        # Get notification preferences
        email_enabled = current_user.get("email_notifications_enabled", True)
        notification_prefs = current_user.get("notification_preferences", {})
        
        # Parse JSONB if it's a string
        if isinstance(notification_prefs, str):
            try:
                notification_prefs = json.loads(notification_prefs) if notification_prefs else {}
            except json.JSONDecodeError:
                notification_prefs = {}
        
        # Default preferences if not set
        if not notification_prefs:
            notification_prefs = {
                "upcoming_reminders": True,
                "logging_reminders": True,
                "health_alerts": True,
                "pause_emails_until": None,
                "snooze_this_cycle": False
            }
        else:
            # Ensure new fields exist (backward compatibility)
            if "upcoming_reminders" not in notification_prefs:
                notification_prefs["upcoming_reminders"] = notification_prefs.get("period_reminders", True)
            if "logging_reminders" not in notification_prefs:
                notification_prefs["logging_reminders"] = notification_prefs.get("period_reminders", True)
            if "health_alerts" not in notification_prefs:
                notification_prefs["health_alerts"] = True
            if "pause_emails_until" not in notification_prefs:
                notification_prefs["pause_emails_until"] = None
            if "snooze_this_cycle" not in notification_prefs:
                notification_prefs["snooze_this_cycle"] = False
        
        return {
            "email_notifications_enabled": email_enabled,
            "notification_preferences": notification_prefs
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification preferences: {str(e)}"
        )

@router.post("/notification-preferences")
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user's notification preferences."""
    try:
        user_id = current_user["id"]
        update_data = {}
        
        # Update email notifications enabled
        if preferences.email_notifications_enabled is not None:
            update_data["email_notifications_enabled"] = preferences.email_notifications_enabled
        
        # Update notification preferences
        # Support both old format (notification_preferences dict) and new individual fields
        current_prefs = current_user.get("notification_preferences", {})
        if isinstance(current_prefs, str):
            try:
                current_prefs = json.loads(current_prefs) if current_prefs else {}
            except json.JSONDecodeError:
                current_prefs = {}
        
        # Update from individual fields if provided
        if preferences.upcoming_reminders is not None:
            current_prefs["upcoming_reminders"] = preferences.upcoming_reminders
        if preferences.logging_reminders is not None:
            current_prefs["logging_reminders"] = preferences.logging_reminders
        if preferences.health_alerts is not None:
            current_prefs["health_alerts"] = preferences.health_alerts
        
        # Also support updating via notification_preferences dict (backward compatibility)
        if preferences.notification_preferences is not None:
            # Merge with new preferences
            current_prefs = {**current_prefs, **preferences.notification_preferences}
        
        update_data["notification_preferences"] = current_prefs
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No preferences provided to update"
            )
        
        # Update in database
        response = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update notification preferences"
            )
        
        updated_user = response.data[0]
        updated_prefs = updated_user.get("notification_preferences", {})
        if isinstance(updated_prefs, str):
            try:
                updated_prefs = json.loads(updated_prefs) if updated_prefs else {}
            except json.JSONDecodeError:
                updated_prefs = {}
        
        return {
            "message": "Notification preferences updated successfully",
            "email_notifications_enabled": updated_user.get("email_notifications_enabled", True),
            "notification_preferences": updated_prefs
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification preferences: {str(e)}"
        )

@router.post("/reset-cycle-data")
async def reset_cycle_data(current_user: dict = Depends(get_current_user)):
    """
    Reset all cycle data for the user.
    
    This will permanently delete:
    - All period logs (past, current, and future)
    - All period start logs
    - All phase predictions (user_cycle_days)
    - Reset user profile cycle fields (last_period_date, cycle_length)
    
    WARNING: This action cannot be undone!
    """
    try:
        user_id = current_user["id"]
        
        # Delete all period logs
        supabase.table("period_logs").delete().eq("user_id", user_id).execute()
        print(f"✅ Deleted all period_logs for user {user_id}")
        
        # Delete all period start logs
        try:
            supabase.table("period_start_logs").delete().eq("user_id", user_id).execute()
            print(f"✅ Deleted all period_start_logs for user {user_id}")
        except Exception as e:
            print(f"⚠️ Error deleting period_start_logs (table may not exist): {str(e)}")
        
        # Delete all phase predictions (user_cycle_days)
        supabase.table("user_cycle_days").delete().eq("user_id", user_id).execute()
        print(f"✅ Deleted all user_cycle_days for user {user_id}")
        
        # Delete period events if table exists
        try:
            supabase.table("period_events").delete().eq("user_id", user_id).execute()
            print(f"✅ Deleted all period_events for user {user_id}")
        except Exception as e:
            print(f"⚠️ Error deleting period_events (table may not exist): {str(e)}")
        
        # Reset user profile cycle fields to defaults
        update_data = {
            "last_period_date": None,
            "cycle_length": 28,  # Default cycle length
        }
        
        response = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset user profile cycle fields"
            )
        
        updated_user = response.data[0]
        updated_user.pop("password", None)
        updated_user.pop("password_hash", None)
        
        print(f"✅ Reset cycle data for user {user_id}")
        
        return {
            "message": "All cycle data has been reset successfully",
            "user": updated_user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset cycle data: {str(e)}"
        )

@router.post("/reset-last-period")
async def reset_last_period(current_user: dict = Depends(get_current_user)):
    """
    Reset only the most recently logged period start.
    
    This will:
    - Delete the most recent period log
    - Delete all user_cycle_days entries for that period range
    - Update last_period_date to the previous period's date (if any)
    - Sync period_start_logs
    - Regenerate predictions from the new last period
    
    Useful if a user accidentally logged a period and wants to undo just that entry.
    """
    try:
        user_id = current_user["id"]
        
        # Get the most recent period log (ordered by date desc)
        logs_response = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date", desc=True).limit(1).execute()
        
        if not logs_response.data or len(logs_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No period logs found to reset"
            )
        
        last_period_log = logs_response.data[0]
        last_period_date_str = last_period_log["date"]
        
        # Parse the date
        if isinstance(last_period_date_str, str):
            last_period_date = datetime.strptime(last_period_date_str, "%Y-%m-%d").date()
        else:
            last_period_date = last_period_date_str
        
        # SAFETY: Handle period end date - use actual end_date if available, else estimate
        # This ensures we delete the correct period range regardless of whether end_date exists
        period_end_date = None
        if last_period_log.get("end_date"):
            # Use actual end_date if available
            end_date_str = last_period_log["end_date"]
            if isinstance(end_date_str, str):
                period_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            else:
                period_end_date = end_date_str
            print(f"🔄 Resetting last period: {last_period_date_str} to {period_end_date.strftime('%Y-%m-%d')} (using actual end_date)")
        else:
            # No end_date - use estimated period length (fallback)
            period_length = estimate_period_length(user_id)
            period_length_days = int(round(max(3.0, min(8.0, period_length))))
            period_end_date = last_period_date + timedelta(days=period_length_days - 1)
            print(f"🔄 Resetting last period: {last_period_date_str} to {period_end_date.strftime('%Y-%m-%d')} (estimated {period_length_days} days, end_date was NULL)")
        
        # Step 1: Delete the period log (handles both start_date only and start_date + end_date)
        delete_response = supabase.table("period_logs").delete().eq("id", last_period_log["id"]).execute()
        print(f"✅ Deleted period log: {last_period_date_str} (end_date was {'provided' if last_period_log.get('end_date') else 'NULL'})")
        
        # Step 2: Delete all user_cycle_days entries for this period range
        # SAFETY: Only delete if we have a valid period_end_date
        if period_end_date:
            current_date = last_period_date
            deleted_count = 0
            while current_date <= period_end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                try:
                    supabase.table("user_cycle_days").delete().eq("user_id", user_id).eq("date", date_str).eq("phase", "Period").execute()
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️ Warning: Could not delete user_cycle_days for {date_str}: {str(e)}")
                current_date += timedelta(days=1)
            
            print(f"✅ Deleted {deleted_count} user_cycle_days entries for period range")
        else:
            print(f"⚠️ Warning: Could not determine period_end_date, skipping user_cycle_days deletion")
        
        # Step 3: Update last_period_date to the previous period's date (if any)
        remaining_logs = supabase.table("period_logs").select("*").eq("user_id", user_id).order("date", desc=True).limit(1).execute()
        
        new_last_period_date = None
        if remaining_logs.data and len(remaining_logs.data) > 0:
            new_last_period_date = remaining_logs.data[0]["date"]
        
        update_data = {
            "last_period_date": new_last_period_date
        }
        
        user_update = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        if not user_update.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user's last_period_date"
            )
        
        updated_user = user_update.data[0]
        updated_user.pop("password", None)
        updated_user.pop("password_hash", None)
        
        print(f"✅ Updated last_period_date to: {new_last_period_date}")
        
        # Step 4: Sync period_start_logs (rebuild from remaining period_logs)
        period_starts = sync_period_start_logs_from_period_logs(user_id)
        print(f"✅ Synced period_start_logs")
        
        # Step 5: Update cycle stats (use returned data to avoid DB read)
        update_user_cycle_stats(user_id, period_starts=period_starts)
        print(f"✅ Updated cycle stats")
        
        # Step 6: Regenerate predictions from the new last confirmed period
        regenerate_predictions_from_last_confirmed_period(user_id, days_ahead=730)
        print(f"✅ Regenerated predictions")
        
        return {
            "message": "Last period has been reset successfully",
            "user": updated_user,
            "deleted_period_date": last_period_date_str
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset last period: {str(e)}"
        )