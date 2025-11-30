from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# Load .env for local development (Railway uses actual env vars)
load_dotenv()

class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    GEMINI_API_KEY: str = ""
    RAPIDAPI_KEY: str = ""
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 7
    RAPIDAPI_BASE_URL: str = "https://womens-health-menstrual-cycle-phase-predictions-insights.p.rapidapi.com"
    
    class Config:
        env_file = ".env"  # Safe for local development
        extra = "ignore"

# Create settings instance
settings = Settings()

# Support SUPABASE_ANON_KEY as fallback for SUPABASE_KEY (for backward compatibility)
if not settings.SUPABASE_KEY:
    settings.SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_KEY", "")

