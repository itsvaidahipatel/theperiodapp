import logging
import os
import re
import time
from functools import wraps
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import supabase
from routes.auth import get_current_user
from routes.wellness import get_hormone_trends_summary_for_llm

router = APIRouter()
logger = logging.getLogger("periodcycle_ai.ai_chat")

# Primary / fallback models (override via env if needed)
GEMINI_MODEL_PRIMARY = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
GEMINI_MODEL_FALLBACK = os.getenv("GEMINI_MODEL_FALLBACK", "gemini-3.1-flash-preview")
GEMINI_MODEL_COMPLEX = os.getenv("GEMINI_MODEL_COMPLEX", "gemini-3.1-flash-preview")

RESPONSE_DISCLAIMER = (
    "\n\n---\n"
    "This information is for educational purposes and not a substitute for professional medical advice."
)
BUSY_MESSAGE = "The AI is a bit busy, please wait a moment before your next message."
SAFETY_PLACEHOLDER = "This content has been removed to comply with health information regulations."

_GENAI_CONFIGURED = False
_GENAI_CLIENT: Optional[Any] = None


class GeminiResourceExhaustedError(RuntimeError):
    """Raised when Gemini quota/rate budget is exhausted (HTTP 429)."""


def configure_genai_on_startup() -> None:
    """Call once from app startup (and lazily before first chat). Idempotent."""
    global _GENAI_CONFIGURED, _GENAI_CLIENT
    if _GENAI_CONFIGURED:
        return
    try:
        from google import genai
    except ImportError:
        logger.warning("google-genai SDK not installed")
        _GENAI_CONFIGURED = True
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        _GENAI_CLIENT = genai.Client(api_key=api_key)
        logger.info("Gemini client configured (google.genai.Client)")
    else:
        logger.warning("GEMINI_API_KEY not set; chat will fail until configured")
    _GENAI_CONFIGURED = True


def _ensure_genai_configured() -> None:
    if not _GENAI_CONFIGURED:
        configure_genai_on_startup()


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
    """Convert DB rows into normalized role/message history."""
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


def _build_generate_contents(gemini_history: List[Dict[str, Any]], user_message: str) -> str:
    """Build compact conversation transcript for generate_content API."""
    lines: List[str] = []
    for h in gemini_history:
        role = h.get("role")
        parts = h.get("parts") or []
        text = str(parts[0]).strip() if parts else ""
        if not text:
            continue
        if role == "user":
            lines.append(f"User: {text}")
        elif role == "model":
            lines.append(f"Assistant: {text}")
    lines.append(f"User: {user_message.strip()}")
    return "\n".join(lines)


def _append_disclaimer(text: str) -> str:
    base = (text or "").rstrip()
    if "not a substitute for professional medical advice" in base.lower():
        return base
    return base + RESPONSE_DISCLAIMER


def _fetch_blocked_phrases() -> List[str]:
    """Fetch all blocked phrases from ai_safety_blocks."""
    resp = supabase.table("ai_safety_blocks").select("blocked_phrase").execute()
    rows = resp.data or []
    phrases: List[str] = []
    for row in rows:
        phrase = str((row or {}).get("blocked_phrase") or "").strip()
        if phrase:
            phrases.append(phrase)
    return phrases


def _contains_blocked_phrase(text: str, blocked_phrases: List[str]) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(phrase.lower() in lowered for phrase in blocked_phrases)


def check_safety_blocks(response_text: str) -> str:
    """
    Replace output with a regulatory placeholder when blocked phrases are present.
    Blocked phrases are loaded from Supabase table: ai_safety_blocks.blocked_phrase.
    """
    text = (response_text or "").strip()
    if not text:
        return text

    try:
        blocked_phrases = _fetch_blocked_phrases()
    except Exception:
        logger.exception("Failed to query ai_safety_blocks; returning original response")
        return text

    if _contains_blocked_phrase(text, blocked_phrases):
        logger.warning("AI response blocked by safety phrase match")
        return SAFETY_PLACEHOLDER

    return text


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


def _is_rls_insert_error(err: Exception) -> bool:
    raw = str(err)
    lowered = raw.lower()
    return "42501" in raw or "row-level security policy" in lowered


class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None
    complex: bool = Field(
        False,
        description="If true, use higher-capability fallback model for complex prompts.",
    )
    client_today: Optional[str] = Field(
        None,
        description="Device calendar date YYYY-MM-DD for cycle context (preferred over server clock)",
    )
    stream: bool = Field(
        True,
        description="Streaming enabled by default for immediate UI rendering.",
    )


def _classify_query_intent(user_message: str) -> str:
    text = (user_message or "").strip().lower()
    if not text:
        return "general"
    personal_markers = [
        r"\b(i|me|my|mine)\b",
        r"\bmy cycle\b",
        r"\bwhy am i\b",
        r"\bmy period\b",
        r"\bmy symptoms?\b",
        r"\bmy hormones?\b",
        r"\bcycle\b",
        r"\bphase\b",
    ]
    for pat in personal_markers:
        if re.search(pat, text):
            return "personal"
    if text.startswith(("what is", "explain", "define", "tell me about", "how does")):
        return "general"
    return "general"


def _build_master_system_instruction(
    user_context: Dict[str, Any], language: str, hormone_context: str, intent: str
) -> str:
    user_name = user_context.get("name", "User")
    phase_info = ""
    if user_context.get("current_phase"):
        phase_info = f"\n- Current cycle phase: {user_context['current_phase']}"
        if user_context.get("phase_day"):
            phase_info += f" (phase day id: {user_context['phase_day']})"

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

    base = f"""You are an expert women's-health medical education assistant.

CRITICAL RULES:
1. Give medically sound, evidence-aware educational information only.
2. Do not diagnose, prescribe, or provide medication dosages.
3. If uncertain, say so and recommend consulting a qualified clinician.
4. Never fabricate facts.
5. Always address the user by name: {user_name}.
6. RESPOND IN THE USER'S SELECTED LANGUAGE: {language.upper()}{language_instruction}

Safety behavior:
- Provide self-care and symptom education.
- For urgent red flags, advise urgent care/ER.
- Keep answers concise and practical.
"""

    if intent == "general":
        return (
            base
            + f"\nGeneral query mode:\n- Name: {user_name}\n- Language: {language}\n"
            + "- Do not rely on user hormone/persona details unless user explicitly asks.\n"
        )

    return (
        base
        + "\nPersonal query mode:\n"
        + f"- Name: {user_name}\n"
        + f"- Typical cycle length: {user_context.get('cycle_length', 28)} days{phase_info}\n"
        + f"- Interests: {interests_text}\n\n"
        + "Hormone mapping context for today (educational reference, NOT lab values):\n"
        + f"{hormone_context}\n"
    )


def _is_resource_exhausted_error(err: Exception) -> bool:
    raw = str(err).lower()
    if "resource_exhausted" in raw or "quota" in raw or "429" in raw:
        return True
    status_code = getattr(err, "status_code", None)
    code = getattr(err, "code", None)
    return status_code == 429 or code == 429


def _retry_on_429(max_retries: int = 3, base_delay_seconds: int = 2):
    """Retry decorator for transient Gemini 429/quota sync windows."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not _is_resource_exhausted_error(e):
                        raise
                    if attempt >= max_retries:
                        raise GeminiResourceExhaustedError(BUSY_MESSAGE) from e
                    wait_seconds = base_delay_seconds * (2**attempt)
                    logger.warning(
                        "Gemini 429 RESOURCE_EXHAUSTED; retry %s/%s in %ss",
                        attempt + 1,
                        max_retries,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)

        return wrapper

    return decorator


def get_gemini_response(
    user_message: str,
    user_context: Dict[str, Any],
    language: str,
    hormone_context: str,
    gemini_history: List[Dict[str, Any]],
    complex_query: bool = False,
) -> str:
    """Generate AI reply using Gemini with explicit retry/backoff on 429."""
    global _GENAI_CLIENT
    _ensure_genai_configured()

    if not os.getenv("GEMINI_API_KEY") or _GENAI_CLIENT is None:
        raise ValueError("GEMINI_API_KEY is not configured")

    intent = _classify_query_intent(user_message)
    system_instruction = _build_master_system_instruction(
        user_context, language, hormone_context, intent
    )

    last_error: Optional[Exception] = None

    models_to_try = [GEMINI_MODEL_PRIMARY]
    if complex_query and GEMINI_MODEL_COMPLEX:
        models_to_try.append(GEMINI_MODEL_COMPLEX)
    if GEMINI_MODEL_FALLBACK and GEMINI_MODEL_FALLBACK != GEMINI_MODEL_PRIMARY:
        models_to_try.append(GEMINI_MODEL_FALLBACK)
    # Deduplicate while preserving order.
    models_to_try = list(dict.fromkeys(models_to_try))

    retry_delays = [2, 4, 8]
    for model_name in models_to_try:
        try:
            model_kwargs: Dict[str, Any] = {
                "model": model_name,
                "system_instruction": system_instruction,
            }
            contents = _build_generate_contents(gemini_history, user_message)
            for idx in range(len(retry_delays) + 1):
                try:
                    response = _GENAI_CLIENT.models.generate_content(
                        model=model_kwargs["model"],
                        contents=contents,
                        config={"system_instruction": model_kwargs["system_instruction"]},
                    )
                    text = _extract_response_text(response)
                    return _append_disclaimer(text)
                except Exception as e:
                    if not _is_resource_exhausted_error(e):
                        raise
                    if idx >= len(retry_delays):
                        raise GeminiResourceExhaustedError(BUSY_MESSAGE) from e
                    wait_seconds = retry_delays[idx]
                    logger.warning(
                        "Gemini 429 RESOURCE_EXHAUSTED on model %s; retry in %ss",
                        model_name,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
        except Exception as e:
            if _is_resource_exhausted_error(e):
                raise GeminiResourceExhaustedError(str(e)) from e
            last_error = e
            logger.warning("Gemini model %s failed: %s", model_name, e)

    logger.error("All Gemini models failed; last error: %s", last_error)
    raise RuntimeError(f"Failed to generate AI response: {last_error}")


def get_gemini_response_stream(
    user_message: str,
    user_context: Dict[str, Any],
    language: str,
    hormone_context: str,
    gemini_history: List[Dict[str, Any]],
    complex_query: bool = False,
) -> Iterator[str]:
    """Yield streaming response chunks for low TTFT Flutter rendering."""
    global _GENAI_CLIENT
    _ensure_genai_configured()
    if not os.getenv("GEMINI_API_KEY") or _GENAI_CLIENT is None:
        raise ValueError("GEMINI_API_KEY is not configured")

    intent = _classify_query_intent(user_message)
    system_instruction = _build_master_system_instruction(
        user_context, language, hormone_context, intent
    )
    models_to_try = [GEMINI_MODEL_PRIMARY]
    if complex_query and GEMINI_MODEL_COMPLEX:
        models_to_try.append(GEMINI_MODEL_COMPLEX)
    if GEMINI_MODEL_FALLBACK and GEMINI_MODEL_FALLBACK != GEMINI_MODEL_PRIMARY:
        models_to_try.append(GEMINI_MODEL_FALLBACK)
    models_to_try = list(dict.fromkeys(models_to_try))

    contents = _build_generate_contents(gemini_history, user_message)
    last_error: Optional[Exception] = None
    for model_name in models_to_try:
        try:
            attempts = 0
            while True:
                emitted_any = False
                try:
                    stream = _GENAI_CLIENT.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config={"system_instruction": system_instruction},
                    )
                    for chunk in stream:
                        ctext = _extract_response_text(chunk)
                        if ctext:
                            emitted_any = True
                            yield ctext
                    return
                except Exception as e:
                    if _is_resource_exhausted_error(e) and not emitted_any and attempts < 3:
                        wait_seconds = 2 * (2**attempts)
                        logger.warning(
                            "Gemini stream 429 on model %s; retry %s/3 in %ss",
                            model_name,
                            attempts + 1,
                            wait_seconds,
                        )
                        time.sleep(wait_seconds)
                        attempts += 1
                        continue
                    if _is_resource_exhausted_error(e):
                        raise GeminiResourceExhaustedError(BUSY_MESSAGE) from e
                    raise
        except Exception as e:
            last_error = e
            logger.warning("Gemini streaming model %s failed: %s", model_name, e)
    raise RuntimeError(f"Failed to generate streaming AI response: {last_error}")


@router.post("/chat")
async def chat(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """Chat with AI assistant (last 5 turns/10 messages retained as Gemini history)."""
    try:
        user_id = current_user["id"]
        language = chat_request.language or current_user.get("language", "en")
        user_message = (chat_request.message or "").strip()

        # Block unsafe user inputs before calling AI.
        blocked_phrases: List[str] = []
        try:
            blocked_phrases = _fetch_blocked_phrases()
        except Exception:
            logger.exception("Failed to load safety blocks for user-input scan")
        if blocked_phrases and _contains_blocked_phrase(user_message, blocked_phrases):
            placeholder = SAFETY_PLACEHOLDER
            try:
                supabase.table("chat_history").insert(
                    {"user_id": user_id, "message": user_message, "role": "user"}
                ).execute()
                supabase.table("chat_history").insert(
                    {"user_id": user_id, "message": placeholder, "role": "assistant"}
                ).execute()
            except Exception:
                logger.exception("Database error saving blocked-input chat history")
            return StreamingResponse(iter([placeholder]), media_type="text/plain; charset=utf-8")

        history_rows = _fetch_recent_chat_rows(user_id, limit=10)
        gemini_history = _rows_to_gemini_history(history_rows)

        intent = _classify_query_intent(chat_request.message)
        current_phase = None
        phase_day = None
        hormone_context = "Hormone reference: omitted for general query."
        if intent == "personal":
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
            "interests": current_user.get("interests", []),
            "current_phase": current_phase,
            "phase_day": phase_day,
        }

        try:
            def _event_stream() -> Iterator[str]:
                collected: List[str] = []
                try:
                    for chunk in get_gemini_response_stream(
                        user_message,
                        user_context,
                        language,
                        hormone_context,
                        gemini_history,
                        complex_query=chat_request.complex,
                    ):
                        collected.append(chunk)
                finally:
                    # Save full exchange after stream completes.
                    raw_text = _append_disclaimer("".join(collected).strip()) if collected else ""
                    full_text = check_safety_blocks(raw_text) if raw_text else ""
                    try:
                        supabase.table("chat_history").insert(
                            {"user_id": user_id, "message": user_message, "role": "user"}
                        ).execute()
                        if full_text:
                            supabase.table("chat_history").insert(
                                {"user_id": user_id, "message": full_text, "role": "assistant"}
                            ).execute()
                    except Exception as e:
                        if _is_rls_insert_error(e):
                            logger.warning(
                                "Skipping chat_history save due to RLS policy (code 42501)."
                            )
                        else:
                            logger.exception("Database error saving streaming chat history")
                if full_text:
                    yield full_text

            return StreamingResponse(_event_stream(), media_type="text/plain; charset=utf-8")
        except ValueError as e:
            logger.error("Gemini configuration error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service is not configured. Please set GEMINI_API_KEY.",
            ) from e
        except GeminiResourceExhaustedError as e:
            logger.warning("Gemini quota/rate exhausted: %s", e)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"status": "busy", "message": BUSY_MESSAGE},
            ) from e
        except Exception as e:
            logger.exception("Gemini error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI service error: {str(e)}",
            ) from e

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
