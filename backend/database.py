import asyncio
import logging
import ssl
import time
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from supabase import Client, create_client

from config import settings

logger = logging.getLogger("periodcycle_ai.database")

P = ParamSpec("P")
R = TypeVar("R")


def _require_supabase_credentials() -> None:
    url = (settings.SUPABASE_URL or "").strip()
    key = (settings.SUPABASE_KEY or "").strip()
    if not url or not key:
        raise SystemExit(
            "Environment Variables Missing: SUPABASE_URL and SUPABASE_KEY "
            "(or SUPABASE_ANON_KEY) must be set."
        )


_require_supabase_credentials()

# Create Supabase client with default configuration (anon key - respects RLS)
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Create service role client for operations that need to bypass RLS
# Only use this for server-side operations that require elevated permissions
supabase_admin: Client | None = None
if settings.SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase_admin = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    except Exception as e:
        logger.warning(
            "Could not create Supabase service role client: %s. "
            "Some operations may fail if RLS policies are too restrictive.",
            e,
        )


def is_transient_error(error: Exception) -> bool:
    """Check if an error is a transient connection error that should be retried."""
    if isinstance(error, (ssl.SSLError, ssl.SSLZeroReturnError)):
        return True

    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    transient_indicators = [
        "resource temporarily unavailable",
        "readerror",
        "connection",
        "timeout",
        "errno 35",
        "errno 54",  # Connection reset
        "errno 60",  # Operation timed out
        "broken pipe",
        "connection reset",
        "connection aborted",
        "ssl",
        "tls",
    ]

    if any(indicator in error_str for indicator in transient_indicators):
        return True

    if any(indicator in error_type for indicator in ["read", "connection", "timeout", "ssl"]):
        return True

    return False


def retry_supabase_call(
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Retry Supabase client operations (sync ``Client`` or ``supabase_admin`` calls)
    with exponential backoff on transient errors.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = initial_delay
            last_exception: Exception | None = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if is_transient_error(e):
                        last_exception = e
                        if attempt < max_retries - 1:
                            logger.info(
                                "Supabase call failed (Attempt %s). Retrying in %ss...",
                                attempt + 1,
                                delay,
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                            continue
                    raise

            if last_exception:
                raise last_exception
            raise RuntimeError("Retry failed")

        return wrapper

    return decorator


async def async_supabase_call(func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """
    Execute a synchronous Supabase call in an async context with retry logic.
    Runs the blocking client in a thread pool so the event loop is not blocked.
    """

    @retry_supabase_call(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
    def _execute() -> R:
        return func(*args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _execute)
