#!/usr/bin/env python
"""
Standalone CLI script to import quotes from data/quotes.json into MongoDB.

Usage:
    python scripts/import_quotes.py
    python scripts/import_quotes.py --file path/to/custom_quotes.json
"""
import sys
import os
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import connect_to_mongo, close_mongo_connection, get_database
from services.quote_service import QuoteService


async def main():
    parser = argparse.ArgumentParser(description="Import quote dataset into MongoDB.")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to custom JSON quotes dataset file."
    )
    args = parser.parse_args()

    print("Connecting to MongoDB...")
    await connect_to_mongo()
    db = get_database()

    quote_service = QuoteService(db)
    print(f"Starting import (file: {args.file or 'data/quotes.json'})...")

    result = await quote_service.import_quotes_from_dataset(dataset_path=args.file)
    print("\n--- Import Summary ---")
    print(f"Total in dataset:     {result.get('total_in_dataset', 0)}")
    print(f"Newly Imported:       {result.get('imported', 0)}")
    print(f"Duplicates / Skipped: {result.get('duplicates_skipped', 0)}")
    print(f"Total Quotes in DB:   {result.get('total_in_db', 0)}")
    print("----------------------\n")

    await close_mongo_connection()
    print("MongoDB connection closed. Done!")


if __name__ == "__main__":
    asyncio.run(main())
