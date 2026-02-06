from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid

from database import supabase, async_supabase_call, retry_supabase_call
from auth_utils import get_password_hash, verify_password, create_access_token, verify_token

router = APIRouter()
security = HTTPBearer()

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    last_period_date: str  # Required
    cycle_length: int = 28  # Required, default 28
    allergies: Optional[list] = None
    language: Optional[str] = "en"
    favorite_cuisine: Optional[str] = None
    favorite_exercise: Optional[str] = None
    interests: Optional[list] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

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
async def register(request: RegisterRequest):
    """Register a new user."""
    try:
        # Check if user already exists
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
        hashed_password = get_password_hash(request.password)
        
        # Create user - schema has: id, name, email, last_period_date, cycle_length, 
        # allergies (ARRAY), language, favorite_cuisine, favorite_exercise, interests (ARRAY), created_at, password_hash
        user_data = {
            "name": request.name,
            "email": request.email,
            "password_hash": hashed_password,
            "last_period_date": request.last_period_date,
            "cycle_length": request.cycle_length or 28,
            "allergies": request.allergies or [],
            "language": request.language or "en",
            "favorite_cuisine": request.favorite_cuisine,
            "favorite_exercise": request.favorite_exercise,
            "interests": request.interests or []
        }
        
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
        
        # Auto-generate cycle predictions if last_period_date is provided
        if request.last_period_date:
            try:
                from cycle_utils import calculate_phase_for_date_range
                from datetime import datetime, timedelta
                
                # Generate cycle predictions using local adaptive algorithms
                last_period_date = request.last_period_date
                cycle_length = request.cycle_length or 28
                
                # Calculate date range: from last period to 60 days ahead
                last_period_dt = datetime.strptime(last_period_date, "%Y-%m-%d")
                today = datetime.now()
                start_date = last_period_date
                end_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")
                
                # Generate predictions using local adaptive algorithms
                print(f"Auto-generating cycle predictions for new user {user['id']}")
                phase_mappings = calculate_phase_for_date_range(
                    user_id=user["id"],
                    last_period_date=last_period_date,
                    cycle_length=int(cycle_length),
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Store predictions in database
                if phase_mappings:
                    from cycle_utils import store_cycle_phase_map
                    store_cycle_phase_map(user["id"], phase_mappings, update_future_only=False)
                    print(f"Cycle predictions generated successfully for user {user['id']} ({len(phase_mappings)} days)")
            except Exception as pred_error:
                # Don't fail registration if prediction fails, but log it
                import traceback
                print(f"Warning: Failed to generate cycle predictions during registration: {str(pred_error)}")
                print(traceback.format_exc())
        
        # Create access token
        access_token = create_access_token(data={"sub": user["id"]})
        
        # Send welcome email to new user
        try:
            from email_service import email_service
            email_service.send_welcome_email(
                to_email=request.email,
                user_name=request.name,
                language=request.language or "en"
            )
            print(f"✅ Welcome email sent to {request.email}")
        except Exception as email_error:
            # Don't fail registration if email fails, but log it
            print(f"⚠️ Failed to send welcome email: {str(email_error)}")
        
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

@router.post("/logout")
async def logout():
    """Logout user (client-side token removal)."""
    return {"msg": "logged out"}

