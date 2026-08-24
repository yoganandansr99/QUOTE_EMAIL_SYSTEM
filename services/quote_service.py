import json
import hashlib
import random
import sys
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings


class QuoteService:
    """Service for managing, categorizing, and delivering quotes from local dataset and MongoDB."""

    APP_CATEGORIES = [
        "success",
        "career",
        "study",
        "personal_growth",
        "leadership",
        "discipline",
        "entrepreneurship",
        "failure_resilience",
        "happiness"
    ]

    CATEGORY_ALIASES = {
        "success": "success",
        "achievement": "success",
        "winning": "success",
        "work": "career",
        "career": "career",
        "profession": "career",
        "job": "career",
        "study": "study",
        "learning": "study",
        "education": "study",
        "knowledge": "study",
        "personal_growth": "personal_growth",
        "growth": "personal_growth",
        "motivation": "personal_growth",
        "inspirational": "personal_growth",
        "life": "personal_growth",
        "mindset": "personal_growth",
        "leadership": "leadership",
        "management": "leadership",
        "discipline": "discipline",
        "focus": "discipline",
        "habits": "discipline",
        "habit": "discipline",
        "consistency": "discipline",
        "entrepreneurship": "entrepreneurship",
        "business": "entrepreneurship",
        "money": "entrepreneurship",
        "innovation": "entrepreneurship",
        "failure_resilience": "failure_resilience",
        "resilience": "failure_resilience",
        "failure": "failure_resilience",
        "courage": "failure_resilience",
        "perseverance": "failure_resilience",
        "adversity": "failure_resilience",
        "happiness": "happiness",
        "joy": "happiness",
        "peace": "happiness",
        "gratitude": "happiness",
        "mindfulness": "happiness"
    }

    KEYWORD_RULES = {
        "success": ["success", "achieve", "achievement", "goal", "win", "winning", "accomplish", "excellence", "greatness", "triumph", "victor"],
        "career": ["career", "work", "job", "profession", "craft", "craftsmanship", "vocation", "labor", "colleague", "trade"],
        "study": ["learn", "learning", "study", "education", "knowledge", "book", "wisdom", "intellect", "curiosity", "question", "school", "student"],
        "personal_growth": ["grow", "growth", "become", "change", "potential", "inner", "self", "mindset", "destiny", "transform", "evolve"],
        "leadership": ["lead", "leader", "leadership", "guide", "inspire", "mentor", "example", "service", "delegate", "empower", "team"],
        "discipline": ["discipline", "disciplined", "focus", "consistency", "consistent", "willpower", "routine", "practice", "procrastinat", "steady", "streak", "habit"],
        "entrepreneurship": ["entrepreneur", "startup", "risk", "create", "innovate", "innovation", "opportunity", "venture", "market", "business", "founder"],
        "failure_resilience": ["fail", "failure", "fall", "resilience", "resilient", "courage", "adversity", "hardship", "overcome", "persevere", "perseverance", "strength", "obstacle", "wound"],
        "happiness": ["happy", "happiness", "joy", "peace", "gratitude", "thankful", "smile", "laugh", "laughter", "calm", "serenity", "content"]
    }

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.quotes_collection = db.quotes

    def _generate_quote_hash(self, quote: str, author: str) -> str:
        """Generate a normalized SHA-256 hash for the quote and author."""
        normalized = f"{quote.lower().strip()}-{author.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()

    def categorize_quote(
        self,
        quote: str,
        raw_category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Normalize and map quote category to one of the 9 supported categories.
        Uses alias mapping and keyword-based rules when necessary.
        """
        # 1. Direct alias / exact match
        if raw_category:
            cleaned_cat = raw_category.lower().strip().replace("-", "_").replace(" ", "_")
            if cleaned_cat in self.CATEGORY_ALIASES:
                return self.CATEGORY_ALIASES[cleaned_cat]

        # 2. Check tags
        if tags:
            for tag in tags:
                cleaned_tag = str(tag).lower().strip().replace("-", "_").replace(" ", "_")
                if cleaned_tag in self.CATEGORY_ALIASES:
                    return self.CATEGORY_ALIASES[cleaned_tag]

        # 3. Keyword-based matching in quote text
        text_lower = f"{quote} {' '.join(tags or [])}".lower()
        category_scores: Dict[str, int] = {cat: 0 for cat in self.APP_CATEGORIES}

        for cat, keywords in self.KEYWORD_RULES.items():
            for kw in keywords:
                if kw in text_lower:
                    category_scores[cat] += 2 if kw in quote.lower() else 1

        best_cat = max(category_scores, key=category_scores.get)
        if category_scores[best_cat] > 0:
            return best_cat

        # 4. Default fallback
        return "personal_growth"

    async def store_quote(self, quote_data: Dict[str, Any]) -> Optional[str]:
        """
        Store a single quote in MongoDB with deduplication and normalized fields.
        Returns the inserted ID as a string, or None if already exists.
        """
        try:
            quote_text = str(quote_data.get("quote", "")).strip()
            author_text = str(quote_data.get("author", "Unknown")).strip()
            if not quote_text:
                return None

            quote_hash = self._generate_quote_hash(quote_text, author_text)

            # Check if quote already exists in database
            existing = await self.quotes_collection.find_one({"quote_hash": quote_hash})
            if existing:
                return None

            # Categorize and normalize
            raw_category = quote_data.get("category")
            tags = quote_data.get("tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]
            category = self.categorize_quote(quote_text, raw_category, tags)

            if category not in tags:
                tags.append(category)

            quote_doc = {
                "quote": quote_text,
                "author": author_text,
                "category": category,
                "tags": [str(t).lower().strip() for t in tags if str(t).strip()],
                "quote_hash": quote_hash,
                "image_url": quote_data.get("image_url"),
                "image_source": quote_data.get("image_source"),
                "image_photographer": quote_data.get("image_photographer"),
                "image_search_query": quote_data.get("image_search_query"),
                "person_story": quote_data.get("person_story"),
                "daily_action": quote_data.get("daily_action"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = await self.quotes_collection.insert_one(quote_doc)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error storing quote: {str(e)}")
            return None

    async def import_quotes_from_dataset(self, dataset_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Import quotes from a local JSON dataset into MongoDB with deduplication.
        Optimized with batch distinct query and bulk insertion for high performance.
        """
        if not dataset_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dataset_path = os.path.join(base_dir, "data", "quotes.json")

        if not os.path.exists(dataset_path):
            print(f"Dataset file not found at: {dataset_path}")
            return {
                "total_in_dataset": 0,
                "imported": 0,
                "duplicates_skipped": 0,
                "total_in_db": await self.get_quote_count()
            }

        try:
            with open(dataset_path, "r", encoding="utf-8") as f:
                quotes_data = json.load(f)
        except Exception as e:
            print(f"Failed to read dataset JSON from {dataset_path}: {e}")
            return {"error": str(e), "imported": 0}

        if not isinstance(quotes_data, list):
            print("Invalid dataset format: expected JSON array of quote objects.")
            return {"error": "Invalid format", "imported": 0}

        # 1. Prepare normalized docs and hashes in memory
        prepared_docs = []
        hashes = []
        for item in quotes_data:
            quote_text = str(item.get("quote", "")).strip()
            author_text = str(item.get("author", "Unknown")).strip()
            if not quote_text:
                continue

            q_hash = self._generate_quote_hash(quote_text, author_text)
            raw_cat = item.get("category")
            tags = item.get("tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]
            category = self.categorize_quote(quote_text, raw_cat, tags)
            if category not in tags:
                tags.append(category)

            doc = {
                "quote": quote_text,
                "author": author_text,
                "category": category,
                "tags": [str(t).lower().strip() for t in tags if str(t).strip()],
                "quote_hash": q_hash,
                "image_url": item.get("image_url"),
                "image_source": item.get("image_source"),
                "image_photographer": item.get("image_photographer"),
                "image_search_query": item.get("image_search_query"),
                "person_story": item.get("person_story"),
                "daily_action": item.get("daily_action"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            prepared_docs.append(doc)
            hashes.append(q_hash)

        # 2. Batch check existing quote hashes in MongoDB in a single query
        existing_hashes = set(await self.quotes_collection.distinct(
            "quote_hash",
            {"quote_hash": {"$in": hashes}}
        ))

        # 3. Filter out existing items
        new_docs = []
        seen_in_batch = set()
        for doc in prepared_docs:
            h = doc["quote_hash"]
            if h not in existing_hashes and h not in seen_in_batch:
                new_docs.append(doc)
                seen_in_batch.add(h)

        imported_count = 0
        if new_docs:
            insert_res = await self.quotes_collection.insert_many(new_docs, ordered=False)
            imported_count = len(insert_res.inserted_ids)

        total_db = await self.get_quote_count()
        skipped_count = len(quotes_data) - imported_count

        print(f"Dataset import complete: {imported_count} imported, {skipped_count} duplicates/skipped, {total_db} total in DB.")
        return {
            "total_in_dataset": len(quotes_data),
            "imported": imported_count,
            "duplicates_skipped": skipped_count,
            "total_in_db": total_db
        }

    async def get_quote_count(self) -> int:
        """Get the total number of quotes in MongoDB."""
        return await self.quotes_collection.count_documents({})

    async def ensure_minimum_quotes(self, minimum: int = 50):
        """
        Ensure minimum number of quotes in MongoDB by importing from the local dataset.
        """
        current_count = await self.get_quote_count()
        if current_count < minimum:
            print(f"Current quote count ({current_count}) is below minimum ({minimum}). Importing dataset...")
            await self.import_quotes_from_dataset()

    async def get_eligible_quote_for_user(
        self,
        user_id: str,
        interests: Optional[List[str]] = None,
        days: int = 365
    ) -> Optional[Dict[str, Any]]:
        """
        Select an eligible quote for a user:
        1. Finds all quote IDs delivered to this user within the last 365 days.
        2. Excludes those quote IDs (handles both ObjectId and string matches).
        3. Prioritizes quotes matching the user's selected interests.
        4. Returns one eligible quote or None if no quotes are available.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # 1. Aggregate quote IDs sent to this user in the last 365 days
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "sent_at": {"$gte": cutoff_date},
                    "status": "sent"
                }
            },
            {
                "$group": {
                    "_id": None,
                    "quote_ids": {"$addToSet": "$quote_id"}
                }
            }
        ]

        sent_quotes_result = list(await self.db.delivery_history.aggregate(pipeline).to_list(length=1))
        raw_excluded_ids = sent_quotes_result[0]["quote_ids"] if sent_quotes_result else []

        # Build list of ObjectId exclusions
        obj_excluded = []
        for qid in raw_excluded_ids:
            if isinstance(qid, ObjectId):
                obj_excluded.append(qid)
            elif isinstance(qid, str) and ObjectId.is_valid(qid):
                obj_excluded.append(ObjectId(qid))
            elif qid:
                obj_excluded.append(qid)

        # Base filter excluding recently delivered quotes
        base_query = {"_id": {"$nin": obj_excluded}} if obj_excluded else {}

        # 2. Try matching user's preferred interest categories
        if interests:
            interest_categories = [str(i).lower().strip() for i in interests if str(i).strip()]
            if interest_categories:
                interest_query = {
                    **base_query,
                    "category": {"$in": interest_categories}
                }
                matching_quotes = list(await self.quotes_collection.find(interest_query).to_list(length=None))
                if matching_quotes:
                    selected = random.choice(matching_quotes)
                    selected["id"] = str(selected.pop("_id"))
                    return selected

        # 3. Fallback: Select from any eligible quote not received in 365 days
        all_eligible_quotes = list(await self.quotes_collection.find(base_query).to_list(length=None))
        if all_eligible_quotes:
            selected = random.choice(all_eligible_quotes)
            selected["id"] = str(selected.pop("_id"))
            return selected

        # 4. If all quotes were sent in 365 days, select from all available quotes
        all_quotes = list(await self.quotes_collection.find({}).to_list(length=None))
        if all_quotes:
            selected = random.choice(all_quotes)
            selected["id"] = str(selected.pop("_id"))
            return selected

        return None

    async def update_quote_image(self, quote_id: str, image_data: Dict[str, Any]):
        """Cache image data on the quote document in MongoDB."""
        try:
            target_id = ObjectId(quote_id) if isinstance(quote_id, str) and ObjectId.is_valid(quote_id) else quote_id
            await self.quotes_collection.update_one(
                {"_id": target_id},
                {
                    "$set": {
                        "image_url": image_data.get("url"),
                        "image_source": image_data.get("source"),
                        "image_photographer": image_data.get("photographer"),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            print(f"Error updating quote image for {quote_id}: {e}")
