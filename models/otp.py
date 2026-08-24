from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class OTPRecord(BaseModel):
    email: EmailStr
    otp_hash: str
    attempts: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_used: bool = False


class OTPRecordInDB(OTPRecord):
    id: str


class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str
