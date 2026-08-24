from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import Optional
from bson import ObjectId
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_database
from models.feedback import Feedback, FeedbackType, FeedbackSubmitRequest
from services.email_service import email_service
from schemas import FeedbackResponse, MessageResponse

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@router.post("/submit", response_model=MessageResponse)
async def submit_user_feedback(
    request: FeedbackSubmitRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Submit general user feedback, feature suggestions, or issue reports from the web portal.
    Stores the feedback in MongoDB and automatically notifies promotionp270@gmail.com via email.
    """
    email = request.email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    if not request.comment or not request.comment.strip():
        raise HTTPException(status_code=400, detail="Please provide your feedback comment")
    
    # Try to find existing user
    user = await db.users.find_one({"email": email})
    user_id = str(user.get("_id")) if user else None
    
    feedback_record = Feedback(
        user_id=user_id,
        user_email=email,
        feedback_type=request.feedback_type,
        rating=request.rating,
        comment=request.comment.strip()
    )
    
    await db.feedback.insert_one(feedback_record.model_dump())
    
    # Send email notification to admin (promotionp270@gmail.com)
    try:
        await email_service.send_admin_feedback_notification(
            user_email=email,
            feedback_type=request.feedback_type,
            comment=request.comment.strip(),
            rating=request.rating,
            user_id=user_id
        )
    except Exception as e:
        print(f"Warning: Failed to dispatch feedback notification email to admin: {str(e)}")
    
    return MessageResponse(
        message="Thank you! Your feedback has been received and sent to our team.",
        success=True
    )


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    user_id: str,
    quote_id: str,
    feedback_type: str,
    comment: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Submit feedback for a specific quote."""
    # Verify user exists
    user = None
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # Verify quote exists
    try:
        quote = await db.quotes.find_one({"_id": ObjectId(quote_id)})
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid quote ID")
    
    user_email = user.get("email") if user else None
    
    # Store feedback
    feedback_record = Feedback(
        user_id=user_id,
        user_email=user_email,
        quote_id=quote_id,
        feedback_type=feedback_type,
        comment=comment
    )
    
    await db.feedback.insert_one(feedback_record.model_dump())
    
    # Notify admin via email
    if user_email:
        try:
            await email_service.send_admin_feedback_notification(
                user_email=user_email,
                feedback_type=f"Quote Reaction: {feedback_type}",
                comment=comment or f"Reacted {feedback_type} to quote: '{quote.get('quote')}'",
                user_id=user_id
            )
        except Exception as e:
            print(f"Warning: Could not send admin feedback notification: {str(e)}")
    
    return FeedbackResponse(
        message="Thank you for your feedback!",
        success=True,
        feedback_type=feedback_type
    )


@router.get("", response_model=MessageResponse)
@router.get("/email", response_model=MessageResponse)
async def submit_feedback_via_email(
    user_id: str,
    type: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle 1-click feedback from daily emails."""
    valid_types = ["loved", "useful", "not_for_me"]
    if type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid feedback type")
    
    # Find most recent delivery for this user
    delivery = await db.delivery_history.find_one(
        {"user_id": user_id},
        sort=[("sent_at", -1)]
    )
    
    if not delivery:
        raise HTTPException(status_code=404, detail="No recent delivery found")
    
    # Lookup user email
    user = None
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        pass
    
    user_email = user.get("email") if user else "Unknown Subscriber"
    
    # Store feedback
    feedback_record = Feedback(
        user_id=user_id,
        user_email=user_email,
        quote_id=delivery.get("quote_id"),
        feedback_type=type
    )
    
    await db.feedback.insert_one(feedback_record.model_dump())
    
    # Notify admin via email
    try:
        await email_service.send_admin_feedback_notification(
            user_email=user_email,
            feedback_type=f"Daily Email Reaction: {type.upper()}",
            comment=f"User clicked '{type}' reaction button in daily morning email.",
            user_id=user_id
        )
    except Exception as e:
        print(f"Warning: Failed to notify admin: {str(e)}")
    
    response_messages = {
        "loved": "❤️ We're thrilled you loved today's inspiration! Your feedback has been sent to our team.",
        "useful": "👍 Thank you! We're glad this morning's quote was useful for you.",
        "not_for_me": "Thanks for letting us know. Your feedback helps us curate even better inspiration."
    }
    
    return MessageResponse(
        message=response_messages.get(type, "Thank you for your feedback!"),
        success=True
    )


@router.get("/history")
async def get_feedback_history(
    email: str,
    limit: int = 20,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all past feedback submitted by a user."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    user_id = str(user.get("_id")) if user else None
    
    query = {"$or": [{"user_email": email}]}
    if user_id:
        query["$or"].append({"user_id": user_id})
    
    feedback_records = await db.feedback.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    # Format for JSON response
    formatted = []
    for f in feedback_records:
        formatted.append({
            "id": str(f.get("_id")),
            "feedback_type": f.get("feedback_type"),
            "comment": f.get("comment"),
            "rating": f.get("rating"),
            "created_at": f.get("created_at").isoformat() if isinstance(f.get("created_at"), datetime) else str(f.get("created_at"))
        })
    
    return {
        "email": email,
        "feedback_count": len(formatted),
        "feedback": formatted
    }
