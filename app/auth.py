# Import required modules
from datetime import datetime, timedelta   # Used for handling time (e.g., token expiration)
from typing import Optional                # Allows optional type hints
from jose import JWTError, jwt             # Library for creating and decoding JWT tokens
from passlib.context import CryptContext   # Library for hashing and verifying passwords
from fastapi import Depends, HTTPException, status   # FastAPI tools for dependencies and error handling
from fastapi.security import OAuth2PasswordBearer    # Handles token-based authentication
from sqlalchemy.orm import Session         # Database session for interacting with SQLAlchemy
from argon2 import PasswordHasher 
# Import project-specific modules
from app.config import get_settings        # Load app settings (like secret key, algorithm)
from app.database import get_db            # Function to get a database session
from app.models import User                # User model (represents users in the database)
from app.schemas import TokenData          # Schema for token payload (username inside JWT)

# Load application settings (contains SECRET_KEY, ALGORITHM, etc.)
settings = get_settings()

# Password hashing configuration
pwd_context = PasswordHasher()

# Define OAuth2 scheme (this tells FastAPI where users will send their login credentials)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# ---------------- PASSWORD FUNCTIONS ----------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if the plain password matches the hashed password"""
    return pwd_context.verify(hashed_password,plain_password)

def get_password_hash(password: str) -> str:
    """Hash a plain password before storing it in the database"""
    return pwd_context.hash(password)

# ---------------- TOKEN CREATION ----------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a JWT access token.
    - data: information to encode inside the token (e.g., username)
    - expires_delta: how long the token should be valid
    """
    to_encode = data.copy()
    
    # Set expiration time (default: 15 minutes if not provided)
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    
    # Add expiration info to token payload
    to_encode.update({"exp": expire})
    
    # Encode the token using secret key and algorithm
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# ---------------- USER AUTHENTICATION ----------------
def authenticate_user(db: Session, username: str, password: str):
    """
    Authenticate a user:
    - Look up user by username
    - Verify password against stored hash
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# ---------------- GET CURRENT USER ----------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),  # Extract token from request
    db: Session = Depends(get_db)         # Get database session
):
    """
    Get the currently logged-in user based on the JWT token.
    - Decodes the token
    - Validates the username inside
    - Fetches user from database
    """
    # Exception to raise if credentials are invalid
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token using secret key and algorithm
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Extract username from token payload ("sub" means subject)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # Wrap username in TokenData schema
        token_data = TokenData(username=username)
    except JWTError:
        # If token is invalid or expired, raise error
        raise credentials_exception
    
    # Look up user in database
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    
    return user  # Return the authenticated user object
