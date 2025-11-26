from supabase import create_client, Client
from config import settings
import time
import asyncio
from typing import Callable, Any, Optional
from functools import wraps

# Create Supabase client with default configuration
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def is_transient_error(error: Exception) -> bool:
    """Check if an error is a transient connection error that should be retried."""
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    
    # Check for specific error types and messages
    transient_indicators = [
        'resource temporarily unavailable',
        'readerror',
        'connection',
        'timeout',
        'errno 35',
        'errno 54',  # Connection reset
        'errno 60',  # Operation timed out
        'broken pipe',
        'connection reset',
        'connection aborted',
    ]
    
    # Check error message
    if any(indicator in error_str for indicator in transient_indicators):
        return True
    
    # Check error type
    if any(indicator in error_type for indicator in ['read', 'connection', 'timeout']):
        return True
    
    return False

def retry_supabase_call(max_retries: int = 3, initial_delay: float = 0.5, backoff_factor: float = 2.0):
    """
    Decorator to retry Supabase calls with exponential backoff.
    Handles transient connection errors like 'Resource temporarily unavailable'.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if is_transient_error(e):
                        last_exception = e
                        if attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= backoff_factor
                            continue
                    # If it's not a transient error, raise immediately
                    raise
            
            # If we exhausted retries, raise the last exception
            if last_exception:
                raise last_exception
            raise Exception("Retry failed")
        
        return wrapper
    return decorator

async def async_supabase_call(func: Callable, *args, **kwargs) -> Any:
    """
    Execute a synchronous Supabase call in an async context with retry logic.
    This prevents blocking the event loop and handles connection errors.
    """
    @retry_supabase_call(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
    def _execute():
        return func(*args, **kwargs)
    
    # Run the synchronous call in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _execute)

