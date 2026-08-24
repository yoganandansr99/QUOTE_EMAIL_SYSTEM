import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.quote_service import QuoteService
from datetime import datetime


@pytest.mark.asyncio
class TestQuoteService:
    """Tests for quote service."""

    async def test_store_quote(self, db: AsyncIOMotorDatabase, test_quote):
        """Test storing a quote."""
        quote_service = QuoteService(db)

        quote_id = await quote_service.store_quote(test_quote)
        assert quote_id is not None

        # Verify quote was stored by ObjectId or quote text
        stored_quote = await db.quotes.find_one({"_id": ObjectId(quote_id)})
        assert stored_quote is not None
        assert stored_quote["quote"] == test_quote["quote"]

    async def test_store_duplicate_quote(self, db: AsyncIOMotorDatabase, test_quote):
        """Test that duplicate quotes are not stored."""
        quote_service = QuoteService(db)

        # Store first time
        quote_id1 = await quote_service.store_quote(test_quote)
        assert quote_id1 is not None

        # Try to store duplicate
        quote_id2 = await quote_service.store_quote(test_quote)
        assert quote_id2 is None

        # Verify only one quote exists
        count = await db.quotes.count_documents({"quote": test_quote["quote"]})
        assert count == 1

    async def test_get_quote_count(self, db: AsyncIOMotorDatabase, test_quote):
        """Test getting quote count."""
        quote_service = QuoteService(db)

        initial_count = await quote_service.get_quote_count()
        await quote_service.store_quote(test_quote)
        new_count = await quote_service.get_quote_count()
        assert new_count == initial_count + 1

    async def test_get_eligible_quote_for_user(
        self,
        db: AsyncIOMotorDatabase,
        test_quote,
        test_email
    ):
        """Test getting eligible quote for user."""
        quote_service = QuoteService(db)

        # Store a test quote
        quote_id = await quote_service.store_quote(test_quote)

        # Create test user
        user_result = await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["success"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        user_id = str(user_result.inserted_id)

        # Get eligible quote
        quote = await quote_service.get_eligible_quote_for_user(
            user_id=user_id,
            interests=["success"]
        )

        assert quote is not None
        assert "quote" in quote
        assert "author" in quote

    async def test_quote_hash_generation(self, db: AsyncIOMotorDatabase, test_quote):
        """Test that quote hashes are correctly generated."""
        quote_service = QuoteService(db)

        await quote_service.store_quote(test_quote)

        # Check hash was created
        stored_quote = await db.quotes.find_one({"quote": test_quote["quote"]})
        assert stored_quote is not None
        assert stored_quote["quote_hash"] is not None
        assert len(stored_quote["quote_hash"]) == 64  # SHA-256 hash length
