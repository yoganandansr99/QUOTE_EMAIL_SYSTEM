from fastapi import APIRouter, Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_database
from core.config import settings
from services.scheduler_service import DailyJobService
from services.quote_service import QuoteService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def verify_cron_secret(x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret")):
    """
    Authenticate cron trigger requests using X-Cron-Secret header.
    Returns 401 Unauthorized if secret is missing or does not match settings.cron_secret.
    """
    configured_secret = settings.cron_secret.strip() if settings.cron_secret else ""

    if not x_cron_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required authentication header: X-Cron-Secret"
        )

    if x_cron_secret.strip() != configured_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Cron-Secret provided."
        )

    return True


@router.post("/send-daily-inspiration")
async def trigger_daily_inspiration_job(
    authenticated: bool = Depends(verify_cron_secret),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> Dict[str, Any]:
    """
    Protected endpoint to trigger daily inspiration email dispatch across active verified users.
    Requires header: X-Cron-Secret
    """
    job_service = DailyJobService(db)
    result = await job_service.execute_daily_inspiration_job()
    return result


@router.post("/import-quotes")
async def trigger_quote_import(
    authenticated: bool = Depends(verify_cron_secret),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> Dict[str, Any]:
    """
    Protected endpoint to import or sync quotes from data/quotes.json into MongoDB.
    Requires header: X-Cron-Secret
    """
    quote_service = QuoteService(db)
    result = await quote_service.import_quotes_from_dataset()
    return {
        "success": True,
        "message": "Quote dataset import completed.",
        "result": result
    }
