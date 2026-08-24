import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from core.database import connect_to_mongo, close_mongo_connection, get_database


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db():
    await connect_to_mongo()
    database = get_database()
    
    # Clean up test data before tests
    await database.users.delete_many({"email": {"$regex": "test.*@test\\.com"}})
    await database.otp_records.delete_many({"email": {"$regex": "test.*@test\\.com"}})
    await database.quotes.delete_many({"quote": {"$regex": "^Test Quote"}})
    await database.delivery_history.delete_many({"user_id": {"$regex": "test_.*"}})
    await database.email_logs.delete_many({"email": {"$regex": "test.*@test\\.com"}})
    
    yield database
    
    # Clean up test data after tests
    await database.users.delete_many({"email": {"$regex": "test.*@test\\.com"}})
    await database.otp_records.delete_many({"email": {"$regex": "test.*@test\\.com"}})
    await database.quotes.delete_many({"quote": {"$regex": "^Test Quote"}})
    await database.delivery_history.delete_many({"user_id": {"$regex": "test_.*"}})
    await database.email_logs.delete_many({"email": {"$regex": "test.*@test\\.com"}})
    
    await close_mongo_connection()


@pytest.fixture
def test_email():
    return "test_user@test.com"


@pytest.fixture
def test_quote():
    return {
        "quote": "Test Quote for Testing",
        "author": "Test Author",
        "category": "success",
        "tags": ["test", "success"]
    }
