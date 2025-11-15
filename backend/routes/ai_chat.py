from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import os

from database import supabase
from routes.auth import get_current_user
from config import settings

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None

def get_gemini_response(user_message: str, user_context: dict, language: str = "en") -> str:
    """Generate AI response using Google Gemini."""
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Build context prompt
        phase_info = ""
        if user_context.get("current_phase"):
            phase_info = f"Current cycle phase: {user_context['current_phase']}, Day: {user_context.get('phase_day', 'N/A')}"
        
        prompt = f"""You are a helpful and empathetic health assistant specializing in women's health and menstrual cycle support.

User Context:
- Name: {user_context.get('name', 'User')}
- Language: {language}
- Cycle Length: {user_context.get('cycle_length', 28)} days
- Allergies: {', '.join(user_context.get('allergies', []) or [])}
- Interests: {', '.join(user_context.get('interests', []) or [])}
{phase_info}

User Question: {user_message}

Please provide a helpful, accurate, and empathetic response in {language}. 
If the question is about medical symptoms or concerns, always recommend consulting with a healthcare professional.
Keep responses concise but informative. Use a warm and supportive tone.

Response:"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        # Fallback response
        return f"I apologize, but I'm having trouble processing your request right now. Please try again later. If you have urgent health concerns, please consult with a healthcare professional."

@router.post("/chat")
async def chat(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Chat with AI assistant."""
    try:
        user_id = current_user["id"]
        language = chat_request.language or current_user.get("language", "en")
        
        # Get user's current cycle phase (if available)
        # This would be calculated from cycle predictions
        user_context = {
            "name": current_user.get("name"),
            "language": language,
            "cycle_length": current_user.get("cycle_length", 28),
            "allergies": current_user.get("allergies", []),
            "interests": current_user.get("interests", []),
            "current_phase": None,  # Would be calculated from cycle data
            "phase_day": None
        }
        
        # Generate AI response
        ai_response = get_gemini_response(chat_request.message, user_context, language)
        
        # Save chat history - schema has: id, created_at, user_id, message, role
        # Save user message
        user_chat_entry = {
            "user_id": user_id,
            "message": chat_request.message,
            "role": "user"
        }
        supabase.table("chat_history").insert(user_chat_entry).execute()
        
        # Save AI response
        ai_chat_entry = {
            "user_id": user_id,
            "message": ai_response,
            "role": "assistant"
        }
        supabase.table("chat_history").insert(ai_chat_entry).execute()
        
        return {"response": ai_response}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}"
        )

@router.get("/chat-history")
async def get_chat_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get chat history for the current user."""
    try:
        user_id = current_user["id"]
        
        # Schema: id, created_at, user_id, message, role
        response = supabase.table("chat_history").select("*").eq("user_id", user_id).order("created_at", desc=False).limit(limit).execute()
        
        # Format for frontend - convert role-based to message pairs
        history = []
        messages = response.data or []
        for msg in messages:
            history.append({
                "message": msg["message"],
                "role": msg["role"],
                "timestamp": msg["created_at"]
            })
        
        return {"history": history}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat history: {str(e)}"
        )

