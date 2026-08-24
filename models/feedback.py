from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class FeedbackType(str, Enum):
    LOVED = "loved"
    USEFUL = "useful"
    NOT_FOR_ME = "not_for_me"
    SUGGESTION = "suggestion"
    GENERAL = "general"
    ISSUE = "issue"


class Feedback(BaseModel):
    user_id: Optional[str] = None
    user_email: Optional[EmailStr] = None
    quote_id: Optional[str] = None
    feedback_type: str = "general"
    rating: Optional[int] = None
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackInDB(Feedback):
    id: str


class FeedbackCreate(BaseModel):
    feedback_type: str = "general"
    comment: Optional[str] = None
    rating: Optional[int] = None


class FeedbackSubmitRequest(BaseModel):
    email: EmailStr
    feedback_type: str = "general"
    comment: str
    rating: Optional[int] = None
