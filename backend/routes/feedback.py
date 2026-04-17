import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database import supabase
from routes.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Generic client-facing message (no internal details leaked)
_CLIENT_ERROR = "Unable to process feedback at this time"


class FeedbackRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=100)
    message: str = Field(..., min_length=10, max_length=5000)
    type: Literal["general", "question", "suggestion", "bug", "other"] = "general"


def _persist_feedback(user_id: str, subject: str, message: str, feedback_type: str) -> None:
    """
    Persist feedback after the HTTP response is sent. Logs errors internally; never logs PII.
    """
    try:
        feedback_entry = {
            "user_id": user_id,
            "subject": subject,
            "message": message,
            "type": feedback_type,
        }
        response = supabase.table("feedback").insert(feedback_entry).execute()
        if response.data:
            logger.info("Feedback record persisted successfully")
        else:
            logger.error("Feedback insert returned no data")
    except Exception:
        logger.exception("Failed to persist feedback to database")


@router.post("/submit")
async def submit_feedback(
    feedback: FeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Submit user feedback, questions, or suggestions. User details are linked via user_id only."""
    try:
        user_id = current_user["id"]
        background_tasks.add_task(
            _persist_feedback,
            user_id,
            feedback.subject,
            feedback.message,
            feedback.type,
        )
        logger.info("Feedback submission accepted for processing")
        return {
            "message": "Thank you for your feedback! We'll get back to you soon.",
            "success": True,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to queue feedback submission")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_CLIENT_ERROR,
        )
