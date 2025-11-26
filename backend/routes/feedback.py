from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import supabase
from routes.auth import get_current_user

router = APIRouter()

class FeedbackRequest(BaseModel):
    subject: str
    message: str
    type: Optional[str] = "general"  # general, question, suggestion, bug, other

@router.post("/submit")
async def submit_feedback(
    feedback: FeedbackRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit user feedback, questions, or suggestions."""
    try:
        user_id = current_user["id"]
        user_name = current_user.get("name", "User")
        user_email = current_user.get("email", "")
        
        # Store feedback in database with user profile information
        feedback_entry = {
            "user_id": user_id,  # Links to users table via foreign key
            "user_name": user_name,  # User's name from profile
            "user_email": user_email,  # User's email from profile
            "subject": feedback.subject,
            "message": feedback.message,
            "type": feedback.type
            # created_at will be set automatically by database default
        }
        
        print(f"📝 Submitting feedback for user {user_id} ({user_name}): {feedback.type} - {feedback.subject}")
        
        # Insert into feedback table in Supabase
        try:
            response = supabase.table("feedback").insert(feedback_entry).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to submit feedback - no data returned"
                )
            
            print(f"✅ Feedback saved successfully to Supabase: ID {response.data[0].get('id')}")
            
        except HTTPException:
            raise
        except Exception as db_error:
            print(f"❌ Database error saving feedback to Supabase: {str(db_error)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save feedback to database: {str(db_error)}"
            )
        
        return {
            "message": "Thank you for your feedback! We'll get back to you soon.",
            "success": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )

