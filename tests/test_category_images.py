import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.image_service import ImageService
from services.quote_service import QuoteService


@pytest.mark.asyncio
class TestCategoryImages:
    """Tests for 150 category images, idempotent seeding, and retrieval."""

    def test_category_images_dataset_file_completeness(self):
        """Verify data/category_images.json has 150 images for each of the 9 categories (1,350 total)."""
        dataset_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "category_images.json"
        )
        assert os.path.exists(dataset_path)

        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1350

        # Count per category
        category_counts = {}
        for item in data:
            cat = item.get("category")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            assert "url" in item and item["url"].startswith("http")
            assert "image_reference" in item
            assert item.get("active") is True

        assert len(category_counts) == 9
        for cat in QuoteService.APP_CATEGORIES:
            assert category_counts.get(cat) == 150

    async def test_idempotent_image_seeding(self, db: AsyncIOMotorDatabase):
        """Seeding category images twice produces zero duplicates and retains exact count."""
        img_service = ImageService(db)

        # 1. Clean test category images
        await db.category_images.delete_many({})

        # 2. First seed run
        res1 = await img_service.seed_category_images()
        assert res1["success"] is True
        assert res1["imported"] == 1350
        assert res1["duplicates_skipped"] == 0

        # 3. Second seed run (must be completely idempotent)
        res2 = await img_service.seed_category_images()
        assert res2["success"] is True
        assert res2["imported"] == 0
        assert res2["duplicates_skipped"] == 1350

        count_in_db = await db.category_images.count_documents({})
        assert count_in_db == 1350

    async def test_get_image_for_category(self, db: AsyncIOMotorDatabase):
        """Retrieving an image for a specific category returns a matching active image."""
        img_service = ImageService(db)
        await img_service.seed_category_images()

        for category in ["success", "career", "study", "discipline", "happiness"]:
            img = await img_service.get_image_for_category(category)
            assert isinstance(img, dict)
            assert "url" in img and img["url"].startswith("http")
            assert "source" in img
            assert "photographer" in img
            assert "image_reference" in img
