import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from routes import ai_chat, auth, cycles, debug, feedback, meta, periods, user, wellness

logger = logging.getLogger("periodcycle_ai.main")

# Optional notification service (graceful degradation if apscheduler not installed)
try:
    from notification_service import notification_service

    NOTIFICATION_SERVICE_AVAILABLE = True
except ImportError:
    logger.warning(
        "Notification service not available (apscheduler not installed). Run: pip install apscheduler"
    )
    NOTIFICATION_SERVICE_AVAILABLE = False
    notification_service = None

# Default: Vite + common Flutter/web dev hosts. Set CORS_ORIGINS (comma-separated) on Railway.
_DEFAULT_CORS = (
    "http://localhost:5173,http://localhost:3000,"
    "http://127.0.0.1:5173,http://127.0.0.1:3000,http://127.0.0.1:8000"
)
_RAW_CORS = os.getenv("CORS_ORIGINS", _DEFAULT_CORS)
_EXTRA_ORIGIN = os.getenv("CORS_EXTRA_ORIGIN", "").strip()
origins = [o.strip() for o in _RAW_CORS.split(",") if o.strip()]
if _EXTRA_ORIGIN and _EXTRA_ORIGIN not in origins:
    origins.append(_EXTRA_ORIGIN)
if not origins:
    origins = ["http://localhost:5173"]

# Browser clients on Vercel previews, Railway-hosted web, and typical Railway app hostnames
_CORS_ORIGIN_REGEX = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https://.*\.vercel\.app|https://.*\.up\.railway\.app|https://.*\.railway\.app",
)


def _cors_allows_any_origin() -> bool:
    return any(o == "*" for o in origins)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("ENV", "").lower() == "production" and _cors_allows_any_origin():
        logger.critical(
            "SECURITY: CORS_ORIGINS is set to allow any origin (*) in production. "
            "This is unsafe for credentialed cross-origin requests. Restrict to explicit origins."
        )

    try:
        ai_chat.configure_genai_on_startup()
    except Exception as e:
        logger.warning("Gemini startup configure skipped: %s", e)

    if NOTIFICATION_SERVICE_AVAILABLE and notification_service:
        try:
            notification_service.start()
            logger.info("Smart Notification Agent started")
        except Exception as e:
            logger.warning("Failed to start notification scheduler: %s", e)

    yield

    if NOTIFICATION_SERVICE_AVAILABLE and notification_service:
        try:
            notification_service.stop()
            logger.info("Smart Notification Agent stopped")
        except Exception as e:
            logger.warning("Error stopping notification scheduler: %s", e)


app = FastAPI(
    title="PeriodCycle.AI API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/user", tags=["User"])
app.include_router(periods.router, prefix="/periods", tags=["Periods"])
app.include_router(ai_chat.router, prefix="/ai", tags=["AI"])
app.include_router(cycles.router, prefix="/cycles", tags=["Cycles"])
app.include_router(wellness.router, prefix="/wellness", tags=["Wellness"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(debug.router, prefix="/debug", tags=["Debug"])
app.include_router(meta.router, prefix="/app-info", tags=["App Info"])


@app.get("/")
async def root():
    return {"message": "PeriodCycle.AI API", "status": "running"}


@app.get("/health")
async def health_check():
    """Liveness plus a lightweight Supabase connectivity check."""
    from database import async_supabase_call, supabase

    def _ping_supabase():
        supabase.table("users").select("id").limit(1).execute()

    try:
        await async_supabase_call(_ping_supabase)
    except Exception as e:
        logger.warning("Health check: Supabase ping failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": "unreachable",
                "message": "Supabase request failed",
            },
        )

    return {
        "status": "healthy",
        "database": "connected",
    }


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
