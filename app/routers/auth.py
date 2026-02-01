# Import required modules
from datetime import timedelta  # Used to set token expiration time
from fastapi import APIRouter, Depends, HTTPException, status  # FastAPI tools for routing, dependency injection, and error handling
from fastapi.security import OAuth2PasswordRequestForm  # Handles login form data (username & password)
from sqlalchemy.orm import Session  # Database session for interacting with SQLAlchemy

# Import project-specific modules
from app.database import get_db  # Function to get a database session
from app.models import User  # User model (represents users in the database)
from app.schemas import UserCreate, UserResponse, Token  # Pydantic schemas for request/response validation
from app.auth import (
    get_password_hash,       # Function to hash passwords securely
    authenticate_user,       # Function to check if username & password are correct
    create_access_token,     # Function to generate JWT access tokens
    get_current_user         # Function to get the currently logged-in user from token
)
from app.config import get_settings  # Load app settings (like token expiry time)

# Create a router for authentication-related endpoints
router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()  # Load settings (e.g., token expiry duration)

# ---------------- REGISTER ENDPOINT ----------------
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    
    # Check if username already exists in the database
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists in the database
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password before saving (never store plain text passwords!)
    hashed_password = get_password_hash(user.password)
    
    # Create a new user object
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    
    # Save the new user to the database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)  # Refresh to get the latest data from DB
    
    return db_user  # Return the newly created user (without password)

# ---------------- LOGIN ENDPOINT ----------------
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),  # Automatically extracts username & password from login form
    db: Session = Depends(get_db)  # Get database session
):
    """Login and get access token"""
    
    # Authenticate user (check if username & password are correct)
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # If authentication fails, raise an error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Set token expiration time (from settings)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Create a JWT access token with the username inside
    access_token = create_access_token(
        data={"sub": user.username},  # "sub" means subject (who the token belongs to)
        expires_delta=access_token_expires
    )
    
    # Return the token to the user (they will use it in future requests)
    return {"access_token": access_token, "token_type": "bearer"}

# ---------------- GET CURRENT USER ENDPOINT ----------------
@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    # This endpoint returns the details of the currently logged-in user
    return current_user
