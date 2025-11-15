from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid

from database import supabase
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

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    # Fetch user from database
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return response.data[0]

@router.post("/register")
async def register(request: RegisterRequest):
    """Register a new user."""
    try:
        # Check if user already exists
        existing = supabase.table("users").select("id").eq("email", request.email).execute()
        
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
        
        response = supabase.table("users").insert(user_data).execute()
        
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
                from cycle_utils import generate_cycle_phase_map
                from datetime import datetime, timedelta
                
                # Generate synthetic past cycle data based on last_period_date and cycle_length
                last_period_dt = datetime.strptime(request.last_period_date, "%Y-%m-%d")
                cycle_length = request.cycle_length or 28
                past_cycle_data = []
                
                # Generate 5 cycles going backwards from last period
                for i in range(5):
                    cycle_date = last_period_dt - timedelta(days=cycle_length * i)
                    past_cycle_data.append({
                        "cycle_start_date": cycle_date.strftime("%Y-%m-%d"),
                        "period_length": 5  # Default period length
                    })
                
                # Generate cycle predictions
                current_date = datetime.now().strftime("%Y-%m-%d")
                print(f"Auto-generating cycle predictions for new user {user['id']}")
                generate_cycle_phase_map(
                    user_id=user["id"],
                    past_cycle_data=past_cycle_data,
                    current_date=current_date
                )
                print(f"Cycle predictions generated successfully for user {user['id']}")
            except Exception as pred_error:
                # Don't fail registration if prediction fails, but log it
                import traceback
                print(f"Warning: Failed to generate cycle predictions during registration: {str(pred_error)}")
                print(traceback.format_exc())
        
        # Create access token
        access_token = create_access_token(data={"sub": user["id"]})
        
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
        response = supabase.table("users").select("*").eq("email", request.email).execute()
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
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

