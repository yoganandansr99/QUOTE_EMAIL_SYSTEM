"""
Standalone CLI script to seed MongoDB with 150 curated royalty-free images per category (1,350 total).
Idempotent: safe to run multiple times without duplicating entries.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import connect_to_mongo, close_mongo_connection, get_database
from services.image_service import ImageService


async def main():
    print("Connecting to MongoDB Atlas...")
    await connect_to_mongo()
    db = get_database()
    
    image_service = ImageService(db)
    print("Seeding category images from data/category_images.json...")
    result = await image_service.seed_category_images()
    
    print("\n--- Seeding Summary ---")
    print(f"Total in dataset:      {result.get('total_in_dataset')}")
    print(f"Newly imported:        {result.get('imported')}")
    print(f"Duplicates skipped:    {result.get('duplicates_skipped')}")
    print(f"Total images in DB:    {result.get('total_in_db')}")
    print("-----------------------\n")
    
    await close_mongo_connection()
    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
