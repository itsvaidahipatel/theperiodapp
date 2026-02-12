from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
from dotenv import load_dotenv

from routes import auth, user, periods, ai_chat, cycles, wellness, feedback, debug

# Optional notification service (graceful degradation if apscheduler not installed)
try:
    from notification_service import notification_service
    NOTIFICATION_SERVICE_AVAILABLE = True
except ImportError:
    print("⚠️ Notification service not available (apscheduler not installed). Run: pip install apscheduler")
    NOTIFICATION_SERVICE_AVAILABLE = False
    notification_service = None

load_dotenv()

app = FastAPI(title="PeriodCycle.AI API", version="1.0.0")

# CORS Configuration
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allows all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/user", tags=["User"])
app.include_router(periods.router, prefix="/periods", tags=["Periods"])
app.include_router(ai_chat.router, prefix="/ai", tags=["AI"])
app.include_router(cycles.router, prefix="/cycles", tags=["Cycles"])
app.include_router(wellness.router, prefix="/wellness", tags=["Wellness"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
app.include_router(debug.router, prefix="/debug", tags=["Debug"])

@app.get("/")
async def root():
    return {"message": "PeriodCycle.AI API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Start notification scheduler on app startup."""
    if NOTIFICATION_SERVICE_AVAILABLE and notification_service:
        try:
            notification_service.start()
            print("✅ Smart Notification Agent started")
        except Exception as e:
            print(f"⚠️ Failed to start notification scheduler: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop notification scheduler on app shutdown."""
    if NOTIFICATION_SERVICE_AVAILABLE and notification_service:
        try:
            notification_service.stop()
            print("🛑 Smart Notification Agent stopped")
        except Exception as e:
            print(f"⚠️ Error stopping notification scheduler: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

