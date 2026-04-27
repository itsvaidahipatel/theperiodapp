from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, SecretStr
from typing import Optional
from datetime import datetime, timedelta, timezone

from database import supabase, async_supabase_call, retry_supabase_call
from auth_utils import get_password_hash, verify_password, create_access_token, verify_token

router = APIRouter()
security = HTTPBearer()
# Optional Supabase session on /register: links public.users.id to auth.users (JWT ``sub``)
optional_supabase_bearer = HTTPBearer(auto_error=False)
PRIVACY_POLICY_VERSION = "2026.04.v1"

def _post_registration_sync(user_id: str) -> None:
    """
    Sync period anchors + stats after registration.
    This runs inline so login cannot proceed before anchors exist.
    """
    try:
        from period_start_logs import sync_period_start_logs_from_period_logs
        from cycle_stats import update_user_cycle_stats

        period_starts = sync_period_start_logs_from_period_logs(user_id)
        update_user_cycle_stats(user_id, period_starts=period_starts)
        print(f"✅ Post-registration sync completed for user {user_id}")
    except Exception as e:
        import traceback
        print(f"⚠️ Post-registration sync failed for user {user_id}: {str(e)}")
        print(traceback.format_exc())
        raise


class RegisterRequest(BaseModel):
    model_config = {"hide_input_in_errors": True}

    name: str
    email: EmailStr
    password: SecretStr
    last_period_date: str  # Required - period start date (source of truth)
    avg_bleeding_days: int = 5  # Typical bleeding length (2-8+), default 5
    cycle_length: int = 28  # Required, default 28
    allergies: Optional[list] = None
    language: Optional[str] = "en"
    language_choice: str
    favorite_cuisine: Optional[str] = None
    favorite_exercise: Optional[str] = None
    interests: Optional[list] = None
    consent_accepted: bool

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateFcmTokenRequest(BaseModel):
    fcm_token: str

@retry_supabase_call(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
def _fetch_user_from_db(user_id: str):
    """Helper function to fetch user from database with retry logic."""
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    return response

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    try:
        # Fetch user from database with retry logic and async handling
        response = await async_supabase_call(_fetch_user_from_db, user_id)
    
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
    
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"Error fetching user from database: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection error. Please try again."
        )

@router.post("/register")
async def register(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    supabase_session: Optional[HTTPAuthorizationCredentials] = Depends(optional_supabase_bearer),
):
    """
    Register a new user. ``RegisterRequest`` is unchanged.

    For Supabase Auth as primary IdP: send ``Authorization: Bearer <supabase_access_token>`` from the
    client after sign-up. The token is verified with the Supabase JWT secret; ``sub`` becomes
    ``users.id`` so RLS and ``get_current_user`` align with ``auth.users``. The registration email must
    match the token's ``email`` claim. Email remains the unique business key for duplicate detection.

    Without a Bearer token, a database-generated UUID is used for ``users.id`` (legacy self-contained auth).
    """
    try:
        if request.consent_accepted is not True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consent is required to register.",
            )

        # Check if user already exists (email links app profile to the Supabase account)
        @retry_supabase_call(max_retries=3)
        def _check_existing():
            return supabase.table("users").select("id").eq("email", request.email).execute()
        
        existing = await async_supabase_call(_check_existing)
        
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = get_password_hash(request.password.get_secret_value())

        # Clamp cycle_length to 21-45; default 28 if missing or out of range
        raw_cycle = request.cycle_length or 28
        try:
            cycle_length = max(21, min(45, int(raw_cycle)))
        except (TypeError, ValueError):
            cycle_length = 28

        # Clamp avg_bleeding_days to 2-8+ (store 8 for "8+")
        raw_bleeding = getattr(request, "avg_bleeding_days", 5) or 5
        try:
            avg_bleeding_days = max(2, min(9, int(raw_bleeding)))  # 2-8, or 9 for "8+"
            if avg_bleeding_days == 9:
                avg_bleeding_days = 8  # 8+ stored as 8
        except (TypeError, ValueError):
            avg_bleeding_days = 5

        # Create user - schema includes avg_bleeding_days (Integer, default 5)
        user_data: dict = {
            "name": request.name,
            "email": request.email,
            "password_hash": hashed_password,
            "last_period_date": request.last_period_date,
            "cycle_length": cycle_length,
            "avg_bleeding_days": avg_bleeding_days,
            "allergies": request.allergies or [],
            "language": request.language_choice or request.language or "en",
            "favorite_cuisine": request.favorite_cuisine,
            "favorite_exercise": request.favorite_exercise,
            "interests": request.interests or [],
            "consent_accepted": request.consent_accepted,
            "consent_timestamp": datetime.now(timezone.utc),
            "privacy_policy_version": PRIVACY_POLICY_VERSION,
            "consent_language": request.language_choice,
        }

        if supabase_session and supabase_session.credentials:
            try:
                auth_payload = verify_token(supabase_session.credentials)
            except HTTPException:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired Supabase session token. Sign in again.",
                ) from None
            raw_sub = auth_payload.get("sub")
            supabase_sub = str(raw_sub).strip() if raw_sub else None
            if not supabase_sub:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Supabase token is missing sub (user id).",
                )
            claim_email = auth_payload.get("email")
            if claim_email is not None and str(claim_email).strip():
                if str(claim_email).strip().lower() != str(request.email).strip().lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Registration email must match the Supabase signed-in account email.",
                    )
            user_data["id"] = supabase_sub
        
        @retry_supabase_call(max_retries=3)
        def _insert_user():
            return supabase.table("users").insert(user_data).execute()
        
        response = await async_supabase_call(_insert_user)
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        user = response.data[0]
        user.pop("password_hash", None)  # Remove password from response
        
        # Create first period_logs entry using avg_bleeding_days (end_date = start + (avg_bleeding_days - 1))
        if request.last_period_date:
            try:
                last_period_dt = datetime.strptime(request.last_period_date, "%Y-%m-%d").date()
                bleeding_days = max(2, min(8, avg_bleeding_days))
                estimated_end_date = last_period_dt + timedelta(days=bleeding_days - 1)
                end_date_value = estimated_end_date.strftime("%Y-%m-%d")
                # Auto-calculated from typical bleeding length; is_manual_end=False
                is_manual_end_value = False
                print(f"📊 Registration: end_date={end_date_value} (avg_bleeding_days={bleeding_days})")

                # Create period_logs entry (Initial Log Injection)
                # flow='Medium' so the engine recognizes it as a valid period start
                period_log_entry = {
                    "user_id": user["id"],
                    "date": request.last_period_date,
                    "end_date": end_date_value,
                    "is_manual_end": is_manual_end_value,
                    "flow": "Medium",
                    "notes": None
                }
                
                period_log_insert = supabase.table("period_logs").insert(period_log_entry).execute()
                if not period_log_insert.data:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to insert initial period log during registration",
                    )
                print(f"✅ Created period_logs entry for registration: start={request.last_period_date}, end={end_date_value}")

                # Run sync inline: user should not proceed/login until anchors are fully synced.
                _post_registration_sync(user["id"])
            except Exception as period_log_error:
                # Registration must fail when initial period log/sync cannot be completed.
                import traceback
                print(f"⚠️ Warning: Failed to create period_logs entry during registration: {str(period_log_error)}")
                print(traceback.format_exc())
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Registration failed during initial period setup: {str(period_log_error)}",
                )
        
        # Create access token
        access_token = create_access_token(data={"sub": user["id"]})
        
        # OPTION B: Send welcome email in background (external calls can be slow/hang)
        try:
            from email_service import email_service
            background_tasks.add_task(
                email_service.send_welcome_email,
                to_email=request.email,
                user_name=request.name,
                language=request.language_choice or request.language or "en"
            )
        except Exception as email_error:
            # Don't fail registration if email fails, but log it
            print(f"⚠️ Failed to schedule welcome email: {str(email_error)}")
        
        return {
            "msg": "User registered successfully",
            "access_token": access_token,
            "user": user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login")
async def login(request: LoginRequest):
    """Login user and return JWT token."""
    try:
        # Find user by email - use password_hash column name
        # Select only columns that exist in the database
        @retry_supabase_call(max_retries=3)
        def _find_user():
            return supabase.table("users").select("*").eq("email", request.email).execute()
        
        response = await async_supabase_call(_find_user)
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user = response.data[0]
        
        # Check if password_hash field exists
        if "password_hash" not in user or not user.get("password_hash"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User account error: password_hash field not accessible."
            )
        
        # Verify password
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user.pop("password_hash", None)  # Remove password from response
        
        # Create access token
        access_token = create_access_token(data={"sub": user["id"]})
        
        return {
            "msg": "Login successful",
            "access_token": access_token,
            "user": user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Login error: {error_details}")  # Log to console for debugging
        
        # Provide more specific error messages
        error_message = str(e)
        if "JWT_SECRET_KEY" in error_message or "secret" in error_message.lower():
            error_message = "Server configuration error: JWT_SECRET_KEY not properly configured"
        elif "connection" in error_message.lower() or "database" in error_message.lower():
            error_message = "Database connection error. Please try again."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {error_message}"
        )

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    current_user.pop("password_hash", None)
    return current_user


@router.post("/update-fcm-token")
async def update_fcm_token(
    request: UpdateFcmTokenRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update authenticated user's FCM token for push notifications."""
    token = (request.fcm_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fcm_token is required",
        )

    try:
        user_id = current_user["id"]
        response = (
            supabase.table("users")
            .update({"fcm_token": token, "updated_at": datetime.utcnow().isoformat()})
            .eq("id", user_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update FCM token",
            )
        return {"msg": "FCM token updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update FCM token: {str(e)}",
        )

@router.post("/logout")
async def logout():
    """Logout user (client-side token removal)."""
    return {"msg": "logged out"}

