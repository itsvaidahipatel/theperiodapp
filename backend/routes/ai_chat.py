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
        
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Try different model names - prioritize Gemini 2.5 Flash
        # Try models in order of preference
        model_names_to_try = [
            'gemini-2.5-flash',
            'gemini-2.5-flash-latest',
            'gemini-2.0-flash-exp',
            'gemini-1.5-flash-latest',
            'gemini-1.5-pro-latest', 
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-pro',
        ]
        
        model = None
        last_error = None
        
        for name in model_names_to_try:
            try:
                model = genai.GenerativeModel(name)
                print(f"Successfully initialized model: {name}")
                break
            except Exception as e:
                last_error = e
                print(f"Failed to use model {name}: {e}")
                continue
        
        if not model:
            # Last attempt: try to list models and use the first available one
            try:
                print("Attempting to list available models...")
                available_models = genai.list_models()
                for model_info in available_models:
                    if 'generateContent' in model_info.supported_generation_methods:
                        # Extract just the model name (remove 'models/' prefix if present)
                        model_name = model_info.name.replace('models/', '')
                        try:
                            model = genai.GenerativeModel(model_name)
                            print(f"Using model from list: {model_name}")
                            break
                        except:
                            continue
            except Exception as list_error:
                print(f"Error listing models: {list_error}")
            
            if not model:
                error_msg = f"Could not initialize any Gemini model. Last error: {last_error}"
                print(error_msg)
                raise ValueError(error_msg)
        
        # Build context prompt
        user_name = user_context.get('name', 'User')
        phase_info = ""
        if user_context.get("current_phase"):
            phase_info = f"\n- Current cycle phase: {user_context['current_phase']}"
            if user_context.get("phase_day"):
                phase_info += f" (Day: {user_context['phase_day']})"
        
        allergies_text = ', '.join(user_context.get('allergies', []) or []) or 'None'
        interests_text = ', '.join(user_context.get('interests', []) or []) or 'None'
        
        # Language instruction based on selected language
        language_instruction = ""
        if language == "hi":
            language_instruction = "\nIMPORTANT: Respond in Hindi (हिंदी). Use simple, clear Hindi. If you need to use English medical terms, provide Hindi explanation."
        elif language == "gu":
            language_instruction = "\nIMPORTANT: Respond in Gujarati (ગુજરાતી). Use simple, clear Gujarati. If you need to use English medical terms, provide Gujarati explanation."
        else:
            language_instruction = "\nIMPORTANT: Respond in simple, clear English."
        
        prompt = f"""You are an expert medical information assistant for women's health. Provide comprehensive, medically-approved information.

CRITICAL RULES:
1. ONLY medically approved, evidence-based information
2. If no medically approved answer exists, say: "I don't have a medically approved answer for this. Please consult a healthcare professional."
3. NEVER guess or provide unverified information
4. ALWAYS address {user_name} by name
5. RESPOND IN THE USER'S SELECTED LANGUAGE: {language.upper()}{language_instruction}

User: {user_name} | Language: {language} | Cycle: {user_context.get('cycle_length', 28)} days{phase_info}

Question: {user_message}

Response Format:
- Start: "Hi {user_name}," or "{user_name},"
- Use BULLET POINTS for lists - format as: * Item text (NOT "bullet Item text")
- NEVER write the word "bullet" in your response
- Format lists like this:
  * First item
  * Second item
  * Third item
- Include when relevant:
  * Common symptoms
  * Relief options (medically approved)
  * Treatment options (general, not prescriptions)
  * Prevention tips
  * When to see a doctor
- Use simple English, short sentences
- Be warm, supportive, concise
- Keep to 2-4 paragraphs + bullet points
- Use **bold** for important terms (e.g., **Iron**, **PCOS**, **hormones**)

Medical Safety:
- Provide medically-approved symptoms, relief methods, and general treatment options
- For diagnosis/treatment: recommend seeing a healthcare professional
- No prescriptions or specific medical advice
- If unsure: decline and suggest consulting a doctor

Response:"""
        
        response = model.generate_content(prompt)
        
        # Handle different response formats
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            if hasattr(response.candidates[0], 'content'):
                if hasattr(response.candidates[0].content, 'parts'):
                    return response.candidates[0].content.parts[0].text
                return str(response.candidates[0].content)
            return str(response.candidates[0])
        else:
            return str(response)
    
    except ValueError as e:
        error_msg = f"Gemini configuration error: {e}"
        print(error_msg)
        raise ValueError("GEMINI_API_KEY is not configured. Please add it to your backend/.env file.")
    except Exception as e:
        error_msg = f"Gemini API error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        # Re-raise to be handled by the endpoint
        raise Exception(f"Failed to generate AI response: {str(e)}")

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
        current_phase = None
        phase_day = None
        try:
            from cycle_utils import get_user_phase_day
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            phase_data = get_user_phase_day(user_id, today)
            if phase_data:
                current_phase = phase_data.get("phase")
                phase_day = phase_data.get("phase_day_id")
        except Exception as e:
            print(f"Error getting current phase: {e}")
        
        user_context = {
            "name": current_user.get("name"),
            "language": language,
            "cycle_length": current_user.get("cycle_length", 28),
            "allergies": current_user.get("allergies", []),
            "interests": current_user.get("interests", []),
            "current_phase": current_phase,
            "phase_day": phase_day
        }
        
        # Generate AI response
        try:
            ai_response = get_gemini_response(chat_request.message, user_context, language)
        except Exception as gemini_error:
            print(f"Gemini error: {gemini_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI service error: {str(gemini_error)}"
            )
        
        # Save chat history - schema has: id, created_at, user_id, message, role
        try:
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
        except Exception as db_error:
            print(f"Database error saving chat history: {db_error}")
            # Continue even if saving fails
        
        return {"response": ai_response}
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
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

