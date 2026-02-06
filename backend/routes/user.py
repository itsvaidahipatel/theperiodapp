from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
import json

from database import supabase
from auth_utils import get_password_hash, verify_password
from routes.auth import get_current_user

router = APIRouter()
security = HTTPBearer()

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    # cycle_length and last_period_date are NOT updatable via profile (managed automatically)
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