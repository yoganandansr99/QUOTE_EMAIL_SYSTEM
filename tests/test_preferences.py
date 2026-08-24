import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime


@pytest.mark.asyncio
class TestPreferences:
    """Tests for preferences endpoints."""
    
    async def test_get_preferences_user_not_found(self, client: AsyncClient):
        """Test getting preferences for non-existent user."""
        response = await client.get(
            "/api/preferences",
            params={"email": "nonexistent@test.com"}
        )
        
        assert response.status_code == 404
    
    async def test_get_preferences_success(
        self, 
        client: AsyncClient, 
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test getting preferences for existing user."""
        # Create test user
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["success", "career"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        response = await client.get(
            "/api/preferences",
            params={"email": test_email}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_email
        assert "success" in data["interests"]
        assert "career" in data["interests"]
    
    async def test_update_preferences_success(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test updating preferences."""
        # Create test user
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        response = await client.put(
            "/api/preferences",
            params={
                "email": test_email,
                "interests": "success,career,happiness"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify in database
        user = await db.users.find_one({"email": test_email})
        assert "success" in user["interests"]
        assert "career" in user["interests"]
        assert "happiness" in user["interests"]
    
    async def test_update_preferences_invalid_category(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test updating preferences with invalid category."""
        # Create test user
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        response = await client.put(
            "/api/preferences",
            params={
                "email": test_email,
                "interests": "invalid_category"
            }
        )
        
        assert response.status_code == 400
    
    async def test_add_interest_success(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test adding a single interest."""
        # Create test user
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["success"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        response = await client.post(
            "/api/preferences/add",
            params={
                "email": test_email,
                "interest": "career"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    async def test_remove_interest_success(
        self,
        client: AsyncClient,
        db: AsyncIOMotorDatabase,
        test_email
    ):
        """Test removing a single interest."""
        # Create test user
        await db.users.insert_one({
            "email": test_email,
            "status": "verified",
            "interests": ["success", "career"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        response = await client.post(
            "/api/preferences/remove",
            params={
                "email": test_email,
                "interest": "career"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
