import os

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env for local development (Railway uses actual env vars)
load_dotenv()


class Settings(BaseSettings):
    """
    JWT_SECRET_KEY must be the Supabase project's JWT secret (Dashboard → Project Settings → API
    → JWT Settings → JWT Secret). Supabase signs Auth access tokens with HS256 and that secret;
    this backend verifies the same tokens via verify_token() and uses the ``sub`` claim as user id.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    GEMINI_API_KEY: str = ""
    # Accept either name in .env / Railway for the same value
    JWT_SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SUPABASE_JWT_SECRET"),
        description="Supabase JWT secret (HS256). Required for verifying Supabase Auth access tokens.",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Must match Supabase (HS256 for symmetric JWT secret).",
    )
    JWT_EXPIRATION_DAYS: int = 7

# Create settings instance
settings = Settings()

# Support SUPABASE_ANON_KEY as fallback for SUPABASE_KEY (for backward compatibility)
if not settings.SUPABASE_KEY:
    settings.SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_KEY", "")

# Normalize algorithm name for jose (Supabase uses HS256)
if settings.JWT_ALGORITHM:
    settings.JWT_ALGORITHM = str(settings.JWT_ALGORITHM).strip().upper() or "HS256"