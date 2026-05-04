from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, SecretStr
from typing import Optional
import uuid
import datetime as dt_module
from datetime import timezone, timedelta

from database import supabase, supabase_admin, async_supabase_call, retry_supabase_call
from auth_utils import get_password_hash, verify_password, create_access_token, verify_token

router = APIRouter()
security = HTTPBearer()
# Optional Supabase session on /register: links public.users.id to auth.users (JWT ``sub``)
optional_supabase_bearer = HTTPBearer(auto_error=False)
PRIVACY_POLICY_VERSION = "2026.04.v1"


def _json_safe_value(value):
    """Recursively convert datetime/date objects to ISO-8601 strings."""
    if isinstance(value, (dt_module.datetime, dt_module.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(v) for v in value]
    return value


def _json_safe_user(user: dict) -> dict:
    """Ensure user payload is JSON-serializable."""
    return _json_safe_value(dict(user))

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
    last_period_date: Optional[str] = None  # Optional onboarding field
    avg_bleeding_days: Optional[int] = None  # Optional; DB default is 5
    cycle_length: Optional[int] = None  # Optional; DB default is 28
    language: Optional[str] = "en"
    language_choice: str
    consent_accepted: bool

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateFcmTokenRequest(BaseModel):
    fcm_token: str


@router.get("/check-email")
async def check_email(email: str):
    email_norm = (email or "").strip().lower()
    if not email_norm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email is required",
        )
    response = supabase.table("users").select("id").eq("email", email_norm).execute()
    return {"available": not bool(response.data)}


@retry_supabase_call(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
def _fetch_user_from_db(user_id: str):
    """Helper function to fetch user from database with retry logic."""
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    return response


def _warm_cycle_state_on_login(user: dict) -> None:
    """
    Prime cycle logic on login so first-run users hit the same path as returning users.
    Safe no-op when user has no cycle inputs yet.
    """
    try:
        from cycle_utils import calculate_phase_for_date_range

        user_id = str(user.get("id") or "").strip()
        if not user_id:
            return

        raw_cycle = user.get("cycle_length")
        try:
            cycle_length = int(raw_cycle or 28)
        except (TypeError, ValueError):
            cycle_length = 28
        try:
            avg_bleeding_days = int(user.get("avg_bleeding_days") or 5)
        except (TypeError, ValueError):
            avg_bleeding_days = 5
        avg_bleeding_days = max(2, min(8, avg_bleeding_days))

        raw_last_period = user.get("last_period_date")
        last_period_date = str(raw_last_period).strip() if raw_last_period else None

        # Stateless compute-on-demand call; ensures cycle_utils pipeline runs at login.
        calculate_phase_for_date_range(
            user_id=user_id,
            last_period_date=last_period_date,
            cycle_length=cycle_length,
            period_logs=[],
        )
    except Exception:
        import traceback
        print("⚠️ Login cycle warm-up failed (non-fatal)")
        print(traceback.format_exc())

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Resolve the authenticated app user from the Bearer JWT.

    Supabase Auth (and our login/register tokens minted with the same secret) place the account UUID
    in the ``sub`` claim. ``public.users.id`` matches that UUID when registration links the profile to
    Supabase; downstream requests must send that same token so RLS owner-only policies
    (``auth.uid()`` / ``sub``) align with lookups by ``users.id``.
    """
    token = credentials.credentials
    payload = verify_token(token)
    raw_sub = payload.get("sub")
    user_id = str(raw_sub).strip() if raw_sub is not None else ""

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    try:
        uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
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


def authenticated_subject_id(current_user: dict) -> str:
    """
    ``public.users.id`` for the Bearer token (same as Supabase JWT ``sub`` after profile link).

    Use this—and never a client-supplied user id—to scope health reads/writes from this API. When the
    backend uses the Supabase service role, row-level security is not applied on these queries; the app
    layer must enforce ownership the same way PostgREST does for end-user tokens.
    """
    raw = current_user.get("id")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    uid = str(raw).strip()
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return uid


@router.post("/register")
async def register(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    supabase_session: Optional[HTTPAuthorizationCredentials] = Depends(optional_supabase_bearer),
):
    """
    Register a new user with optional cycle onboarding fields.

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
        email_norm = str(request.email).lower().strip()

        # Check if user already exists (email links app profile to the Supabase account)
        @retry_supabase_call(max_retries=3)
        def _check_existing():
            return supabase.table("users").select("id").eq("email", email_norm).execute()
        
        existing = await async_supabase_call(_check_existing)
        
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="EMAIL_ALREADY_EXISTS",
            )
        
        # Hash password
        hashed_password = get_password_hash(request.password.get_secret_value())

        # Optional medical onboarding fields: validate only when provided.
        last_period_date = None
        if request.last_period_date is not None:
            last_period_date = str(request.last_period_date).strip()
            if not last_period_date:
                last_period_date = None
            else:
                try:
                    dt_module.datetime.strptime(last_period_date, "%Y-%m-%d")
                except (TypeError, ValueError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="last_period_date must be in YYYY-MM-DD format",
                    ) from None

        cycle_length = 28
        if request.cycle_length is not None:
            try:
                cycle_length = int(request.cycle_length)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="cycle_length must be an integer between 21 and 45",
                ) from None
            if cycle_length < 21 or cycle_length > 45:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="cycle_length must be between 21 and 45",
                )

        # Safety net: re-check uniqueness immediately before insert
        existing = await async_supabase_call(_check_existing)
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="EMAIL_ALREADY_EXISTS",
            )

        avg_bleeding_days = 5
        if request.avg_bleeding_days is not None:
            try:
                avg_bleeding_days = int(request.avg_bleeding_days)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="avg_bleeding_days must be an integer between 2 and 8",
                ) from None
            if avg_bleeding_days < 2 or avg_bleeding_days > 8:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="avg_bleeding_days must be between 2 and 8",
                )

        # Create user; keep optional onboarding fields absent to use DB defaults.
        user_data: dict = {
            "name": request.name,
            "email": email_norm,
            "password_hash": hashed_password,
            "language": request.language_choice or request.language or "en",
            "cycle_length": cycle_length,
            "avg_bleeding_days": avg_bleeding_days,
            "consent_accepted": request.consent_accepted,
            "consent_timestamp": dt_module.datetime.now(timezone.utc).isoformat(),
            "privacy_policy_version": PRIVACY_POLICY_VERSION,
            "consent_language": request.language_choice,
        }
        if last_period_date is not None:
            user_data["last_period_date"] = last_period_date

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
                if str(claim_email).strip().lower() != email_norm:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Registration email must match the Supabase signed-in account email.",
                    )
            user_data["id"] = supabase_sub

        if supabase_admin is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server is missing SUPABASE_SERVICE_ROLE_KEY; registration cannot complete.",
            )

        @retry_supabase_call(max_retries=3)
        def _insert_user():
            return supabase_admin.table("users").insert(user_data).execute()

        response = await async_supabase_call(_insert_user)
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        user = _json_safe_user(response.data[0])
        user.pop("password_hash", None)  # Remove password from response
        
        # Create first period_logs entry using avg_bleeding_days (end_date = start + (avg_bleeding_days - 1))
        if last_period_date:
            try:
                last_period_dt = dt_module.datetime.strptime(last_period_date, "%Y-%m-%d").date()
                bleeding_days = max(2, min(8, int(avg_bleeding_days or 5)))
                estimated_end_date = last_period_dt + timedelta(days=bleeding_days - 1)
                end_date_value = estimated_end_date.strftime("%Y-%m-%d")
                # Auto-calculated from typical bleeding length; is_manual_end=False
                is_manual_end_value = False
                print(f"📊 Registration: end_date={end_date_value} (avg_bleeding_days={bleeding_days})")

                # Create period_logs entry (Initial Log Injection)
                # flow='Medium' so the engine recognizes it as a valid period start
                period_log_entry = {
                    "user_id": user["id"],
                    "date": last_period_date,
                    "end_date": end_date_value,
                    "is_manual_end": is_manual_end_value,
                    "flow": "Medium",
                    "notes": None
                }
                
                period_log_insert = supabase_admin.table("period_logs").insert(period_log_entry).execute()
                if not period_log_insert.data:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to insert initial period log during registration",
                    )
                print(f"✅ Created period_logs entry for registration: start={last_period_date}, end={end_date_value}")

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
        access_token = create_access_token(data={"sub": str(user["id"])})
        
        # OPTION B: Send welcome email in background (external calls can be slow/hang)
        try:
            from email_service import email_service
            background_tasks.add_task(
                email_service.send_welcome_email,
                to_email=email_norm,
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
        import traceback

        print(f"REGISTRATION CRASH: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )

@router.post("/login")
async def login(request: LoginRequest):
    """Login user and return JWT token."""
    try:
        email_norm = str(request.email).lower().strip()
        # Find user by email - use password_hash column name
        # Select only columns that exist in the database
        @retry_supabase_call(max_retries=3)
        def _find_user():
            return supabase.table("users").select("*").eq("email", email_norm).execute()
        
        response = await async_supabase_call(_find_user)
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user = _json_safe_user(response.data[0])
        _warm_cycle_state_on_login(user)
        
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
        access_token = create_access_token(data={"sub": str(user["id"])})
        
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
    safe_user = _json_safe_user(current_user)
    safe_user.pop("password_hash", None)
    return safe_user


@router.delete("/delete-account", status_code=status.HTTP_200_OK)
async def delete_account(current_user: dict = Depends(get_current_user)):
    """
    Delete the authenticated user's row in ``public.users`` by ``current_user['id']`` (JWT ``sub``).

    With ``ON DELETE CASCADE`` on FKs from child tables (e.g. ``period_logs``, ``chat_history``,
    ``user_cycle_days``) to ``users``, this single delete removes the profile and dependent rows so
    the account can be erased for Right to be Forgotten requests; behavior is enforced in the schema,
    not in this endpoint.
    """
    user_id = authenticated_subject_id(current_user)
    print(f"User {user_id} requested permanent deletion. Wiping all health logs.")

    @retry_supabase_call(max_retries=3)
    def _delete_user():
        return supabase.table("users").delete().eq("id", user_id).execute()

    try:
        await async_supabase_call(_delete_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}",
        )

    return {"msg": "All your data has been permanently deleted."}


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
        user_id = authenticated_subject_id(current_user)
        response = (
            supabase.table("users")
            .update({"fcm_token": token, "updated_at": dt_module.datetime.utcnow().isoformat()})
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

