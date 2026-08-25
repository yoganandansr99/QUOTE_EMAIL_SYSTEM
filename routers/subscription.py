from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import re
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_database
from core.config import settings
from models.user import UserStatus
from models.otp import OTPRequest, OTPVerify
from services.otp_service import OTPService
from services.email_service import email_service
from schemas import (
    MessageResponse,
    OTPRequestResponse,
    SubscriptionStatusResponse,
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleClientIdResponse
)
import httpx

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


async def send_welcome_email(db: AsyncIOMotorDatabase, email: str):
    """Send welcome email with first inspirational quote to new/verified user."""
    try:
        from services.quote_service import QuoteService
        from services.image_service import ImageService
        
        user = await db.users.find_one({"email": email})
        if not user:
            return
        
        quote_service = QuoteService(db)
        image_service = ImageService()
        
        # Get a welcome quote
        quote = await quote_service.get_eligible_quote_for_user(
            user_id=str(user["_id"]),
            interests=[]
        )
        
        if quote:
            # Get image for quote
            if not quote.get("image_url"):
                image_data = await image_service.get_image_for_quote(
                    quote=quote.get("quote"),
                    category=quote.get("category"),
                    tags=quote.get("tags")
                )
                quote["image_url"] = image_data.get("url")
                quote["image_source"] = image_data.get("source")
                quote["image_photographer"] = image_data.get("photographer")
            
            # Send welcome email
            person_story = quote.get("person_story") or f"{quote.get('author')} has inspired countless individuals through their wisdom and achievements."
            daily_action = quote.get("daily_action") or "Take one small step today toward a goal you've been postponing."
            
            await email_service.send_daily_inspiration_email(
                to_email=email,
                quote=quote.get("quote"),
                author=quote.get("author"),
                image_url=quote.get("image_url"),
                person_story=person_story,
                daily_action=daily_action,
                user_id=str(user["_id"])
            )
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
        # Don't fail the verification/auth if welcome email fails


async def verify_google_token(credential: str) -> dict:
    """Verify Google ID token via Google's tokeninfo endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid Google authentication token.")
            
            payload = resp.json()
            
            # Check audience if client_id configured
            if settings.google_client_id:
                aud = payload.get("aud")
                if aud != settings.google_client_id:
                    raise HTTPException(status_code=400, detail="Google Client ID mismatch.")
            
            email = payload.get("email", "").lower().strip()
            email_verified = payload.get("email_verified") in [True, "true", "True", 1]
            
            if not email or not email_verified:
                raise HTTPException(status_code=400, detail="Google account email is not verified.")
            
            return payload
    except HTTPException:
        raise
    except Exception as e:
        print(f"Google token verification error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to verify Google token.")


@router.get("/google-client-id", response_model=GoogleClientIdResponse)
async def get_google_client_id():
    """Return configured Google Client ID for frontend initialization."""
    client_id = settings.google_client_id.strip()
    return GoogleClientIdResponse(
        client_id=client_id,
        is_configured=bool(client_id)
    )


@router.post("/google-auth", response_model=GoogleAuthResponse)
async def google_auth(
    request: GoogleAuthRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Authenticate or subscribe a user with Google OAuth (Google Identity Services)."""
    email = None
    name = request.name
    picture = request.picture

    # Require verified Google credential token (JWT)
    if not request.credential:
        raise HTTPException(
            status_code=400,
            detail="Google authentication token (credential) is required. Please sign in via the Google OAuth popup."
        )

    payload = await verify_google_token(request.credential)
    email = payload.get("email", "").lower().strip()
    name = payload.get("name") or request.name
    picture = payload.get("picture") or request.picture

    if not email or not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address returned from Google.")

    existing_user = await db.users.find_one({"email": email})
    is_new = False
    should_send_welcome = False

    if not existing_user:
        # Create new verified subscriber
        is_new = True
        should_send_welcome = True
        new_user = {
            "email": email,
            "status": UserStatus.VERIFIED.value,
            "interests": [],
            "auth_provider": "google",
            "name": name,
            "picture": picture,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "unsubscribed_at": None
        }
        await db.users.insert_one(new_user)
    else:
        # Update existing user to verified status
        if existing_user.get("status") != UserStatus.VERIFIED.value:
            should_send_welcome = True

        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "status": UserStatus.VERIFIED.value,
                    "auth_provider": "google",
                    "name": name or existing_user.get("name"),
                    "picture": picture or existing_user.get("picture"),
                    "unsubscribed_at": None,
                    "updated_at": datetime.utcnow()
                }
            }
        )

    # Dispatch welcome email with quote immediately for newly verified subscriber
    if should_send_welcome:
        await send_welcome_email(db, email)

    message = (
        "Welcome to Daily Inspiration! You are now subscribed with Google."
        if is_new
        else "Welcome back! Signed in with Google."
    )

    return GoogleAuthResponse(
        message=message,
        success=True,
        email=email,
        is_new=is_new,
        is_verified=True,
        name=name,
        picture=picture
    )


@router.post("/request-otp", response_model=OTPRequestResponse)
async def request_otp(
    request: OTPRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Request an OTP for email verification."""
    email = request.email.lower().strip()
    
    # Validate email format
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Check if user is already active verified subscriber
    existing_user = await db.users.find_one({"email": email})
    if existing_user and existing_user.get("status") == UserStatus.VERIFIED.value:
        raise HTTPException(
            status_code=400,
            detail="This email is already subscribed to Daily Inspiration. You are already receiving daily emails!"
        )

    otp_service = OTPService(db)
    
    # Request OTP
    success, message, otp_plain = await otp_service.request_otp(email)
    
    if not success:
        status_code = 400 if "already subscribed" in message.lower() else 429
        raise HTTPException(status_code=status_code, detail=message)
    
    # Send OTP email
    email_sent = await email_service.send_otp_email(email, otp_plain)
    
    if not email_sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP email. Please try again later."
        )
    
    return OTPRequestResponse(
        message=message,
        success=True,
        expires_in_minutes=5
    )


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(
    request: OTPVerify,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Verify OTP and activate subscription."""
    email = request.email.lower().strip()
    otp = request.otp.strip()
    
    # Validate inputs
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    if not otp or len(otp) != 6 or not otp.isdigit():
        raise HTTPException(status_code=400, detail="Invalid OTP format. Please enter a 6-digit code.")
    
    otp_service = OTPService(db)
    
    # Verify OTP
    success, message = await otp_service.verify_otp(email, otp)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Send welcome email with first quote immediately
    await send_welcome_email(db, email)
    
    return MessageResponse(message=message, success=True)


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    email: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get subscription status for an email."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        return SubscriptionStatusResponse(
            email=email,
            is_subscribed=False,
            is_verified=False,
            interests=[],
            created_at=None
        )
    
    status = user.get("status")
    is_verified = status == UserStatus.VERIFIED.value
    is_subscribed = is_verified
    
    return SubscriptionStatusResponse(
        email=email,
        is_subscribed=is_subscribed,
        is_verified=is_verified,
        interests=user.get("interests", []),
        created_at=user.get("created_at")
    )


@router.post("/unsubscribe", response_model=MessageResponse)
async def unsubscribe(
    email: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Unsubscribe a user from daily emails."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=404, detail="Email not found in our system")
    
    # Update user status to unsubscribed
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "status": UserStatus.UNSUBSCRIBED.value,
                "unsubscribed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return MessageResponse(
        message="You have been successfully unsubscribed from Daily Inspiration emails.",
        success=True
    )


@router.post("/resubscribe", response_model=MessageResponse)
async def resubscribe(
    email: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Resubscribe a previously unsubscribed user."""
    email = email.lower().strip()
    
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=404, detail="Email not found in our system")
    
    # Check if user was previously verified
    if user.get("status") == UserStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Please verify your email first")
    
    # Update user status back to verified
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "status": UserStatus.VERIFIED.value,
                "unsubscribed_at": None,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return MessageResponse(
        message="Welcome back! You have been resubscribed to Daily Inspiration.",
        success=True
    )
