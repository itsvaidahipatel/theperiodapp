import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from config import settings
from database import supabase
from routes.auth import get_current_user
from routes.wellness import get_hormone_trends_summary_for_llm

router = APIRouter()
logger = logging.getLogger("periodcycle_ai.ai_chat")

# Primary / fallback models (override via env if needed)
GEMINI_MODEL_PRIMARY = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_MODEL_FALLBACK = os.getenv("GEMINI_MODEL_FALLBACK", "gemini-2.0-flash")

RESPONSE_DISCLAIMER = (
    "\n\n---\n"
    "This information is for educational purposes and not a substitute for professional medical advice."
)

_GENAI_CONFIGURED = False


def configure_genai_on_startup() -> None:
    """Call once from app startup (and lazily before first chat). Idempotent."""
    global _GENAI_CONFIGURED
    if _GENAI_CONFIGURED:
        return
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google.generativeai not installed")
        _GENAI_CONFIGURED = True
        return

    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        logger.info("Gemini client configured (genai.configure)")
    else:
        logger.warning("GEMINI_API_KEY not set; chat will fail until configured")
    _GENAI_CONFIGURED = True


def _ensure_genai_configured() -> None:
    if not _GENAI_CONFIGURED:
        configure_genai_on_startup()


def _build_safety_settings() -> Optional[List[Dict[str, Any]]]:
    try:
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
    except ImportError:
        return None

    settings_list: List[Dict[str, Any]] = [
        {
            "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
            "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        },
    ]
    for attr in ("HARM_CATEGORY_MEDICAL_ADVICE", "HARM_CATEGORY_MEDICAL"):
        med = getattr(HarmCategory, attr, None)
        if med is not None:
            settings_list.append(
                {"category": med, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH}
            )
            break
    return settings_list


def _fetch_recent_chat_rows(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Most recent `limit` messages in chronological order (oldest first)."""
    try:
        resp = (
            supabase.table("chat_history")
            .select("role, message, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(reversed(resp.data or []))
        return rows
    except Exception:
        logger.exception("Failed to fetch chat history for Gemini context")
        return []


def _rows_to_gemini_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert DB rows to Gemini start_chat history (user/model turns)."""
    history: List[Dict[str, Any]] = []
    for row in rows:
        role = row.get("role")
        msg = (row.get("message") or "").strip()
        if not msg:
            continue
        if role == "user":
            history.append({"role": "user", "parts": [msg]})
        elif role == "assistant":
            history.append({"role": "model", "parts": [msg]})

    while history and history[0]["role"] != "user":
        history.pop(0)
    # Trailing user without a model reply cannot be in history when using send_message for the new turn
    while history and history[-1]["role"] == "user":
        history.pop()
    return history


def _append_disclaimer(text: str) -> str:
    base = (text or "").rstrip()
    if "not a substitute for professional medical advice" in base.lower():
        return base
    return base + RESPONSE_DISCLAIMER


def _extract_response_text(response: Any) -> str:
    if hasattr(response, "text") and response.text:
        return str(response.text)
    if hasattr(response, "candidates") and response.candidates:
        c0 = response.candidates[0]
        if hasattr(c0, "content") and c0.content and hasattr(c0.content, "parts"):
            parts = c0.content.parts
            if parts and hasattr(parts[0], "text"):
                return str(parts[0].text)
        return str(c0)
    return str(response)


class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None
    client_today: Optional[str] = Field(
        None,
        description="Device calendar date YYYY-MM-DD for cycle context (preferred over server clock)",
    )


def get_gemini_response(
    user_message: str,
    user_context: Dict[str, Any],
    language: str,
    hormone_context: str,
    gemini_history: List[Dict[str, Any]],
) -> str:
    """Generate AI reply using Gemini with conversation history and safety settings."""
    _ensure_genai_configured()
    import google.generativeai as genai

    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured")

    user_name = user_context.get("name", "User")
    phase_info = ""
    if user_context.get("current_phase"):
        phase_info = f"\n- Current cycle phase: {user_context['current_phase']}"
        if user_context.get("phase_day"):
            phase_info += f" (phase day id: {user_context['phase_day']})"

    allergies_text = ", ".join(user_context.get("allergies", []) or []) or "None"
    interests_text = ", ".join(user_context.get("interests", []) or []) or "None"

    if language == "hi":
        language_instruction = (
            "\nIMPORTANT: Respond in Hindi (हिंदी). Use simple, clear Hindi. "
            "If you need to use English medical terms, provide Hindi explanation."
        )
    elif language == "gu":
        language_instruction = (
            "\nIMPORTANT: Respond in Gujarati (ગુજરાતી). Use simple, clear Gujarati. "
            "If you need to use English medical terms, provide Gujarati explanation."
        )
    else:
        language_instruction = "\nIMPORTANT: Respond in simple, clear English."

    system_instruction = f"""You are an expert medical information assistant for women's health. Provide comprehensive, evidence-aware educational information.

CRITICAL RULES:
1. ONLY medically sound, evidence-based educational information; avoid definitive diagnoses or prescriptions.
2. If you cannot give a safe educational answer, say you don't have a reliable answer and suggest consulting a healthcare professional.
3. NEVER guess or fabricate medical facts.
4. ALWAYS address {user_name} by name.
5. RESPOND IN THE USER'S SELECTED LANGUAGE: {language.upper()}{language_instruction}

User profile (context only): {user_name} | Language: {language} | Typical cycle length: {user_context.get('cycle_length', 28)} days{phase_info}
Allergies (for lifestyle tips only): {allergies_text}
Interests (optional context): {interests_text}

Hormone pattern context (educational mapping for today, NOT lab results):
{hormone_context}

Medical safety:
- Give general education: symptoms, self-care ideas that are widely considered safe, when to seek care.
- For diagnosis, treatment decisions, or medications: direct the user to a qualified clinician.
- Do not provide specific dosages, prescription advice, or emergency instructions; urge urgent care/ER when appropriate.

Response format:
- Start: "Hi {user_name}," or "{user_name},"
- Use bullet points with * (not the word "bullet")
- Keep to 2–4 short paragraphs plus bullets where helpful
- Use **bold** for key terms when useful
"""

    safety = _build_safety_settings()
    last_error: Optional[Exception] = None

    models_to_try = [GEMINI_MODEL_PRIMARY]
    if GEMINI_MODEL_FALLBACK and GEMINI_MODEL_FALLBACK != GEMINI_MODEL_PRIMARY:
        models_to_try.append(GEMINI_MODEL_FALLBACK)

    for model_name in models_to_try:
        try:
            model_kwargs: Dict[str, Any] = {
                "model_name": model_name,
                "system_instruction": system_instruction,
            }
            if safety:
                model_kwargs["safety_settings"] = safety

            model = genai.GenerativeModel(**model_kwargs)
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(user_message)
            text = _extract_response_text(response)
            return _append_disclaimer(text)
        except Exception as e:
            last_error = e
            logger.warning("Gemini model %s failed: %s", model_name, e)

    logger.error("All Gemini models failed; last error: %s", last_error)
    raise RuntimeError(f"Failed to generate AI response: {last_error}")


@router.post("/chat")
async def chat(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """Chat with AI assistant (last 5 messages retained as Gemini history)."""
    try:
        user_id = current_user["id"]
        language = chat_request.language or current_user.get("language", "en")

        history_rows = _fetch_recent_chat_rows(user_id, limit=5)
        gemini_history = _rows_to_gemini_history(history_rows)

        current_phase = None
        phase_day = None
        try:
            from cycle_utils import get_user_phase_day, get_user_today

            today = get_user_today(chat_request.client_today).strftime("%Y-%m-%d")
            phase_data = get_user_phase_day(user_id, today)
            if phase_data:
                current_phase = phase_data.get("phase")
                phase_day = phase_data.get("phase_day_id")
        except Exception:
            logger.exception("Error resolving current phase for chat context")

        try:
            hormone_context = get_hormone_trends_summary_for_llm(user_id, chat_request.client_today)
        except Exception:
            logger.exception("Hormone context for LLM failed; continuing without")
            hormone_context = "Hormone reference: unavailable."

        user_context = {
            "name": current_user.get("name"),
            "language": language,
            "cycle_length": current_user.get("cycle_length", 28),
            "allergies": current_user.get("allergies", []),
            "interests": current_user.get("interests", []),
            "current_phase": current_phase,
            "phase_day": phase_day,
        }

        try:
            ai_response = get_gemini_response(
                chat_request.message.strip(),
                user_context,
                language,
                hormone_context,
                gemini_history,
            )
        except ValueError as e:
            logger.error("Gemini configuration error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service is not configured. Please set GEMINI_API_KEY.",
            ) from e
        except Exception as e:
            logger.exception("Gemini error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI service error: {str(e)}",
            ) from e

        try:
            supabase.table("chat_history").insert(
                {"user_id": user_id, "message": chat_request.message, "role": "user"}
            ).execute()
            supabase.table("chat_history").insert(
                {"user_id": user_id, "message": ai_response, "role": "assistant"}
            ).execute()
        except Exception:
            logger.exception("Database error saving chat history")

        return {"response": ai_response}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}",
        ) from e


@router.get("/chat-history")
async def get_chat_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """Get chat history for the current user."""
    try:
        user_id = current_user["id"]

        response = (
            supabase.table("chat_history")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )

        history = []
        for msg in response.data or []:
            history.append(
                {
                    "message": msg["message"],
                    "role": msg["role"],
                    "timestamp": msg["created_at"],
                }
            )

        return {"history": history}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat history: {str(e)}",
        ) from e
