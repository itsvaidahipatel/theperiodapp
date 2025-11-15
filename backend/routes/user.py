from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

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

