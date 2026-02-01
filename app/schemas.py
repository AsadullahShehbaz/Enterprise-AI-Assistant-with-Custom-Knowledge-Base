from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any

# User Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Thread Schemas
class ThreadCreate(BaseModel):
    title: Optional[str] = None

class ThreadResponse(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Message Schemas
class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    thread_id: int
    role: str
    content: str
    meta_data: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True

# Chat Schemas
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[int] = None

class ChatResponse(BaseModel):
    message: str
    thread_id: int
    sources: Optional[List[str]] = None

# Document Schemas
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_size: Optional[int]
    upload_date: datetime
    processed: int

    class Config:
        from_attributes = True
