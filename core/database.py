from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings
from datetime import datetime

client: AsyncIOMotorClient = None
database = None


async def connect_to_mongo():
    global client, database
    
    # MongoDB Atlas connection with optimized settings
    client = AsyncIOMotorClient(
        settings.mongodb_url,
        maxPoolSize=10,
        minPoolSize=1,
        maxIdleTimeMS=45000,
        connectTimeoutMS=30000,
        socketTimeoutMS=30000,
        serverSelectionTimeoutMS=30000
    )
    database = client[settings.mongodb_db_name]
    
    # Test connection
    try:
        await client.admin.command('ping')
        print(f"Success: Connected to MongoDB Atlas: {settings.mongodb_db_name}")
    except Exception as e:
        print(f"Failed to connect to MongoDB Atlas: {e}")
        raise
    
    # Create indexes
    try:
        await database.users.create_index("email", unique=True)
        await database.quotes.create_index("quote_hash", unique=True)
        await database.delivery_history.create_index([("user_id", 1), ("sent_at", -1)])
        await database.otp_records.create_index([("email", 1), ("created_at", -1)])
        await database.feedback.create_index([("user_id", 1), ("created_at", -1)])
        print("Success: Database indexes created/verified")
    except Exception as e:
        print(f"Note: Index creation: {e}")


async def close_mongo_connection():
    global client
    if client:
        client.close()


def get_database():
    return database
