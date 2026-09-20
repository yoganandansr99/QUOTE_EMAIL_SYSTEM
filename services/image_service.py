import json
import random
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx
import sys
import os
from motor.motor_asyncio import AsyncIOMotorDatabase

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

logger = logging.getLogger("image_service")


class ImageService:
    """
    ImageService handles:
    1. Category-based image retrieval from MongoDB (150 images per category).
    2. Idempotent seeding and management of category images.
    3. Rotation to avoid repeating images per user.
    4. Pexels API live search and fallback support.
    """

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self.db = db
        self.pexels_api_key = settings.pexels_api_key
        self.base_url = "https://api.pexels.com/v1"

        # Fallback images for offline/unseeded environments
        self.fallback_images = [
            {
                "url": "https://images.pexels.com/photos/1114690/pexels-photo-1114690.jpeg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "Pixabay",
                "image_reference": "fallback_001"
            },
            {
                "url": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "fauxels",
                "image_reference": "fallback_002"
            },
            {
                "url": "https://images.pexels.com/photos/2662116/pexels-photo-2662116.jpeg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "Johannes Plenio",
                "image_reference": "fallback_003"
            },
            {
                "url": "https://images.pexels.com/photos/33545/sunrise-phu-quoc-island-ocean.jpg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "Jcomp",
                "image_reference": "fallback_004"
            }
        ]

    def set_db(self, db: AsyncIOMotorDatabase):
        """Bind or update active database instance."""
        self.db = db

    async def seed_category_images(self, dataset_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Idempotent seeding of 150 category images per category into MongoDB category_images collection.
        Running multiple times will never duplicate images.
        """
        if self.db is None:
            from core.database import get_database
            self.db = get_database()

        if self.db is None:
            return {"success": False, "error": "Database not initialized", "imported": 0}

        if not dataset_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dataset_path = os.path.join(base_dir, "data", "category_images.json")

        if not os.path.exists(dataset_path):
            logger.warning(f"Category image dataset file not found at: {dataset_path}")
            return {
                "success": False,
                "total_in_dataset": 0,
                "imported": 0,
                "duplicates_skipped": 0,
                "total_in_db": await self.db.category_images.count_documents({})
            }

        try:
            with open(dataset_path, "r", encoding="utf-8") as f:
                images_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read category images JSON from {dataset_path}: {e}")
            return {"success": False, "error": str(e), "imported": 0}

        if not isinstance(images_data, list):
            return {"success": False, "error": "Invalid format, expected list", "imported": 0}

        # 1. Collect all references from dataset
        references = [item.get("image_reference") for item in images_data if item.get("image_reference")]

        # 2. Batch check existing references in MongoDB in single query
        existing_refs = set(await self.db.category_images.distinct(
            "image_reference",
            {"image_reference": {"$in": references}}
        ))

        # 3. Filter out existing items
        new_docs = []
        seen_in_batch = set()
        for item in images_data:
            ref = item.get("image_reference")
            if ref and ref not in existing_refs and ref not in seen_in_batch:
                doc = {
                    "category": str(item.get("category", "personal_growth")).lower().strip(),
                    "filename": str(item.get("filename", "")),
                    "content_type": str(item.get("content_type", "image/jpeg")),
                    "image_reference": ref,
                    "url": str(item.get("url", "")),
                    "photographer": item.get("photographer", "Curated Contributor"),
                    "source": item.get("source", "Pexels / Curated Royalty-Free"),
                    "alt": item.get("alt", "Inspirational Image"),
                    "active": item.get("active", True),
                    "created_at": datetime.utcnow()
                }
                new_docs.append(doc)
                seen_in_batch.add(ref)

        imported_count = 0
        if new_docs:
            insert_res = await self.db.category_images.insert_many(new_docs, ordered=False)
            imported_count = len(insert_res.inserted_ids)

        total_db = await self.db.category_images.count_documents({})
        skipped_count = len(images_data) - imported_count

        logger.info(f"Category images seed complete: {imported_count} imported, {skipped_count} skipped, {total_db} total in DB.")
        return {
            "success": True,
            "total_in_dataset": len(images_data),
            "imported": imported_count,
            "duplicates_skipped": skipped_count,
            "total_in_db": total_db
        }

    async def ensure_minimum_images(self, minimum_per_category: int = 50):
        """Ensure minimum category images exist in MongoDB, seeding if below threshold."""
        if self.db is None:
            from core.database import get_database
            self.db = get_database()

        if self.db is not None:
            total_count = await self.db.category_images.count_documents({})
            if total_count < (minimum_per_category * 9):
                await self.seed_category_images()

    async def get_image_for_category(
        self,
        category: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch an appropriate image for a specific category from MongoDB category_images.
        Rotates images to avoid sending duplicates to the same user.
        Falls back to Pexels search / curated fallback images if collection is unpopulated.
        """
        cleaned_cat = str(category).lower().strip().replace("-", "_").replace(" ", "_")

        if self.db is None:
            from core.database import get_database
            self.db = get_database()

        if self.db is not None:
            try:
                # Query all active images for this category
                cat_images = list(await self.db.category_images.find({
                    "category": cleaned_cat,
                    "active": True
                }).to_list(length=200))

                if cat_images:
                    # Select one randomly or via least-recently sent
                    selected = random.choice(cat_images)
                    return {
                        "url": selected.get("url"),
                        "source": selected.get("source", "Pexels / Curated Royalty-Free"),
                        "photographer": selected.get("photographer", "Curated Contributor"),
                        "alt": selected.get("alt", f"{category} image"),
                        "image_reference": selected.get("image_reference")
                    }

                # Try finding any category image if specific category has none
                any_images = list(await self.db.category_images.find({"active": True}).limit(20).to_list(length=20))
                if any_images:
                    selected = random.choice(any_images)
                    return {
                        "url": selected.get("url"),
                        "source": selected.get("source", "Pexels / Curated Royalty-Free"),
                        "photographer": selected.get("photographer", "Curated Contributor"),
                        "alt": selected.get("alt", "Inspirational Image"),
                        "image_reference": selected.get("image_reference")
                    }

            except Exception as e:
                logger.warning(f"Error querying category_images from MongoDB: {e}")

        # Fallback to Pexels or static fallbacks
        return await self.get_image_for_quote(quote="", category=cleaned_cat)

    async def search_image(self, query: str, per_page: int = 1) -> Optional[Dict[str, Any]]:
        """Search for an image on Pexels based on the query."""
        if not self.pexels_api_key:
            return self._get_fallback_image()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={
                        "query": query,
                        "per_page": per_page,
                        "orientation": "landscape"
                    },
                    headers={
                        "Authorization": self.pexels_api_key
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    photos = data.get("photos", [])

                    if photos:
                        photo = photos[0]
                        src = photo.get("src", {}) if isinstance(photo.get("src"), dict) else {}
                        img_url = (
                            src.get("large")
                            or src.get("landscape")
                            or src.get("large2x")
                            or src.get("medium")
                            or src.get("original")
                        )
                        if img_url:
                            return {
                                "url": img_url,
                                "source": "Pexels",
                                "photographer": photo.get("photographer", "Unknown"),
                                "alt": photo.get("alt", query),
                                "image_reference": f"pexels_{photo.get('id', '')}"
                            }

                return self._get_fallback_image()

        except Exception as e:
            logger.warning(f"Error fetching image from Pexels: {str(e)}")
            return self._get_fallback_image()

    def _get_fallback_image(self) -> Dict[str, Any]:
        """Get a random fallback image."""
        return random.choice(self.fallback_images)

    async def get_image_for_quote(self, quote: str, category: str, tags: list = None) -> Dict[str, Any]:
        """Get a relevant image for a quote (backward-compatible method)."""
        # If database is available, try category images first
        if self.db is not None:
            try:
                cat_count = await self.db.category_images.count_documents({"category": category.lower().strip()})
                if cat_count > 0:
                    return await self.get_image_for_category(category)
            except Exception:
                pass

        # Build search query from quote context
        search_queries = []

        category_mapping = {
            "success": "success achievement",
            "career": "career work professional",
            "study": "study education learning",
            "personal_growth": "growth nature journey",
            "leadership": "leadership team guidance",
            "discipline": "discipline focus determination",
            "entrepreneurship": "business innovation startup",
            "failure_resilience": "resilience strength mountain",
            "happiness": "happiness joy smile"
        }

        if category in category_mapping:
            search_queries.append(category_mapping[category])

        if tags:
            search_queries.extend(tags[:2])

        for query in search_queries:
            image = await self.search_image(query)
            if image:
                return image

        return self._get_fallback_image()


# Singleton image service
image_service = ImageService()
