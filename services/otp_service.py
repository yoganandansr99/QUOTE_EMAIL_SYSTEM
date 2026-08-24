import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from models.otp import OTPRecord, OTPRecordInDB, OTPRequest, OTPVerify
from models.user import User, UserStatus

import hmac

class OTPService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.otp_collection = db.otp_records
        self.users_collection = db.users
    
    def generate_otp(self) -> str:
        """Generate a secure 6-digit OTP."""
        return str(secrets.randbelow(900000) + 100000)
    
    def hash_otp(self, otp: str) -> str:
        """Hash the OTP for secure storage."""
        secret = settings.secret_key or "daily-inspiration-otp-secret"
        return hashlib.sha256(f"{otp}:{secret}".encode()).hexdigest()
    
    def verify_otp_hash(self, otp: str, otp_hash: str) -> bool:
        """Verify an OTP against its hash."""
        secret = settings.secret_key or "daily-inspiration-otp-secret"
        expected = hashlib.sha256(f"{otp}:{secret}".encode()).hexdigest()
        return hmac.compare_digest(expected, otp_hash)
    
    async def request_otp(self, email: str) -> Tuple[bool, str, Optional[str]]:
        """
        Request a new OTP for email verification.
        Returns: (success, message, otp_plain)
        """
        # Check if user is already actively subscribed
        existing_user = await self.users_collection.find_one({"email": email.lower()})
        if existing_user and existing_user.get("status") == UserStatus.VERIFIED.value:
            return False, "This email is already subscribed to Daily Inspiration. You are already receiving daily emails!", None

        # Check rate limit
        recent_otp = await self.otp_collection.find_one(
            {"email": email.lower()},
            sort=[("created_at", -1)]
        )
        
        if recent_otp:
            created_at = recent_otp.get("created_at")
            rate_limit_delta = timedelta(minutes=settings.otp_rate_limit_minutes)
            
            if datetime.utcnow() - created_at < rate_limit_delta:
                wait_seconds = int((rate_limit_delta - (datetime.utcnow() - created_at)).total_seconds())
                return False, f"Please wait {wait_seconds} seconds before requesting a new OTP.", None
        
        # Generate and store OTP
        otp_plain = self.generate_otp()
        otp_hash = self.hash_otp(otp_plain)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.otp_expiry_minutes)
        
        otp_record = OTPRecord(
            email=email.lower(),
            otp_hash=otp_hash,
            expires_at=expires_at
        )
        
        await self.otp_collection.insert_one(otp_record.model_dump())
        
        return True, "OTP sent successfully. Please check your email.", otp_plain
    
    async def verify_otp(self, email: str, otp: str) -> Tuple[bool, str]:
        """
        Verify an OTP.
        Returns: (success, message)
        """
        # Find the most recent valid OTP for this email
        otp_record = await self.otp_collection.find_one(
            {"email": email.lower(), "is_used": False},
            sort=[("created_at", -1)]
        )
        
        if not otp_record:
            return False, "No valid OTP found. Please request a new one."
        
        # Check if OTP has expired
        if datetime.utcnow() > otp_record.get("expires_at"):
            return False, "OTP has expired. Please request a new one."
        
        # Check attempts
        attempts = otp_record.get("attempts", 0)
        if attempts >= settings.otp_max_attempts:
            return False, "Maximum attempts exceeded. Please request a new OTP."
        
        # Verify OTP
        if not self.verify_otp_hash(otp, otp_record.get("otp_hash")):
            # Increment attempts
            await self.otp_collection.update_one(
                {"_id": otp_record.get("_id")},
                {"$inc": {"attempts": 1}}
            )
            remaining = settings.otp_max_attempts - attempts - 1
            return False, f"Invalid OTP. {remaining} attempts remaining."
        
        # Mark OTP as used
        await self.otp_collection.update_one(
            {"_id": otp_record.get("_id")},
            {"$set": {"is_used": True}}
        )
        
        # Update or create user as verified
        existing_user = await self.users_collection.find_one({"email": email.lower()})
        
        if existing_user:
            await self.users_collection.update_one(
                {"email": email.lower()},
                {
                    "$set": {
                        "status": UserStatus.VERIFIED.value,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        else:
            user = User(
                email=email.lower(),
                status=UserStatus.VERIFIED
            )
            await self.users_collection.insert_one(user.model_dump())
        
        return True, "Email verified successfully! You are now subscribed."
    
    async def cleanup_expired_otps(self):
        """Remove expired OTP records from the database."""
        await self.otp_collection.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })
