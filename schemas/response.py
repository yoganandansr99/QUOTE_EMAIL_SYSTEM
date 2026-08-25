from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class OTPRequestResponse(BaseModel):
    message: str
    success: bool = True
    expires_in_minutes: int


class SubscriptionStatusResponse(BaseModel):
    email: EmailStr
    is_subscribed: bool
    is_verified: bool
    interests: List[str] = []
    created_at: Optional[datetime] = None


class PreferencesResponse(BaseModel):
    email: EmailStr
    interests: List[str]
    available_interests: List[str]


class FeedbackResponse(BaseModel):
    message: str
    success: bool = True
    feedback_type: str


class ErrorResponse(BaseModel):
    detail: str
    success: bool = False


class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None  # Google ID token (JWT) from GIS
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    picture: Optional[str] = None


class GoogleAuthResponse(BaseModel):
    message: str
    success: bool = True
    email: str
    is_new: bool = False
    is_verified: bool = True
    name: Optional[str] = None
    picture: Optional[str] = None


class GoogleClientIdResponse(BaseModel):
    client_id: str
    is_configured: bool = False
