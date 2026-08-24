from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import List
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_database
from models.user import InterestCategory, UserStatus
from schemas import PreferencesResponse, MessageResponse

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    email: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user preferences."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return PreferencesResponse(
        email=email,
        interests=user.get("interests", []),
        available_interests=[cat.value for cat in InterestCategory]
    )


@router.put("", response_model=MessageResponse)
async def update_preferences(
    email: str,
    interests: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user preferences."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("status") != UserStatus.VERIFIED.value:
        raise HTTPException(status_code=400, detail="Please verify your email first")
    
    # Parse comma-separated interests
    interests_list = [i.strip() for i in interests.split(",") if i.strip()]
    
    # Validate interests
    valid_interests = [cat.value for cat in InterestCategory]
    invalid_interests = [i for i in interests_list if i not in valid_interests]
    
    if invalid_interests:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interest categories: {', '.join(invalid_interests)}"
        )
    
    # Update preferences
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "interests": interests_list,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return MessageResponse(
        message="Preferences updated successfully!",
        success=True
    )


@router.post("/add", response_model=MessageResponse)
async def add_interest(
    email: str,
    interest: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add a single interest to user preferences."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("status") != UserStatus.VERIFIED.value:
        raise HTTPException(status_code=400, detail="Please verify your email first")
    
    # Validate interest
    valid_interests = [cat.value for cat in InterestCategory]
    if interest not in valid_interests:
        raise HTTPException(status_code=400, detail=f"Invalid interest category: {interest}")
    
    # Check if already has this interest
    current_interests = user.get("interests", [])
    if interest in current_interests:
        raise HTTPException(status_code=400, detail="Interest already added")
    
    # Add interest
    await db.users.update_one(
        {"email": email},
        {
            "$addToSet": {"interests": interest},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return MessageResponse(
        message=f"Interest '{interest}' added successfully!",
        success=True
    )


@router.post("/remove", response_model=MessageResponse)
async def remove_interest(
    email: str,
    interest: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Remove a single interest from user preferences."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove interest
    result = await db.users.update_one(
        {"email": email},
        {
            "$pull": {"interests": interest},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Interest not found in preferences")
    
    return MessageResponse(
        message=f"Interest '{interest}' removed successfully!",
        success=True
    )
