import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext

from config import settings

logger = logging.getLogger(__name__)

# Argon2 for new hashes; pbkdf2_sha256 retained for verifying existing passwords until migrated on login.
pwd_context = CryptContext(
    schemes=["argon2", "pbkdf2_sha256"],
    deprecated=["pbkdf2_sha256"],
)


def _warn_if_weak_jwt_secret() -> None:
    key = (settings.JWT_SECRET_KEY or "").strip()
    weak_placeholders = {"secret", "your-secret-key-change-in-production"}
    if (
        not key
        or key.lower() == "secret"
        or key in weak_placeholders
        or len(key) < 32
    ):
        logger.warning(
            "SECURITY WARNING: JWT_SECRET_KEY is missing, placeholder, or shorter than 32 characters "
            "(length=%s). Configure a strong random secret in production.",
            len(key),
        )


_warn_if_weak_jwt_secret()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password (argon2 for new hashes)."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token with exp and iat. Requires ``sub`` (user id, same as Supabase Auth subject).

    Signed with ``JWT_SECRET_KEY`` (Supabase JWT secret) using HS256, compatible with Supabase Auth tokens.
    """
    if "sub" not in data:
        raise ValueError("JWT payload must include a 'sub' (subject) claim")

    to_encode: Dict[str, Any] = dict(data)
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.JWT_EXPIRATION_DAYS)

    # NumericDate claims (seconds since epoch) for broad python-jose / client compatibility
    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now.timestamp())})
    alg = (settings.JWT_ALGORITHM or "HS256").upper()
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=alg)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT using the Supabase JWT secret (``JWT_SECRET_KEY`` / ``SUPABASE_JWT_SECRET``).

    Supabase Auth issues HS256 tokens; ``sub`` is the authenticated user's UUID. We do not require
    issuer/audience checks so both Supabase-issued sessions and locally minted tokens (same secret) verify.
    """
    try:
        alg = (settings.JWT_ALGORITHM or "HS256").upper()
        if alg != "HS256":
            logger.warning("JWT_ALGORITHM is %s; Supabase Auth uses HS256. Verification may fail.", alg)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[alg],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": False,
            },
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
