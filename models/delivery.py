from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class DeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"


class DeliveryHistory(BaseModel):
    user_id: str
    quote_id: str
    sent_at: datetime = datetime.utcnow()
    status: DeliveryStatus = DeliveryStatus.SENT
    error_message: Optional[str] = None


class DeliveryHistoryInDB(DeliveryHistory):
    id: str


class EmailLog(BaseModel):
    user_id: str
    email: str
    subject: str
    status: DeliveryStatus
    error_message: Optional[str] = None
    sent_at: datetime = datetime.utcnow()


class EmailLogInDB(EmailLog):
    id: str
