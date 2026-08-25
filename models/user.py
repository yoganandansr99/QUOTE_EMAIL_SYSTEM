from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class UserStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    UNSUBSCRIBED = "unsubscribed"


class InterestCategory(str, Enum):
    SUCCESS = "success"
    CAREER = "career"
    STUDY = "study"
    PERSONAL_GROWTH = "personal_growth"
    LEADERSHIP = "leadership"
    DISCIPLINE = "discipline"
    ENTREPRENEURSHIP = "entrepreneurship"
    FAILURE_RESILIENCE = "failure_resilience"
    HAPPINESS = "happiness"


class User(BaseModel):
    email: EmailStr
    status: UserStatus = UserStatus.PENDING
    interests: List[InterestCategory] = []
    auth_provider: Optional[str] = "email"
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    unsubscribed_at: Optional[datetime] = None


class UserInDB(User):
    id: str


class UserCreate(BaseModel):
    email: EmailStr


class UserUpdate(BaseModel):
    interests: Optional[List[InterestCategory]] = None
