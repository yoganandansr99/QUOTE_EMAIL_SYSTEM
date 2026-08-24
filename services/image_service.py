import httpx
from typing import Optional, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings


class ImageService:
    def __init__(self):
        self.pexels_api_key = settings.pexels_api_key
        self.base_url = "https://api.pexels.com/v1"
        
        # Fallback images for when API fails
        self.fallback_images = [
            {
                "url": "https://images.pexels.com/photos/1114690/pexels-photo-1114690.jpeg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "Pixabay"
            },
            {
                "url": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "fauxels"
            },
            {
                "url": "https://images.pexels.com/photos/2662116/pexels-photo-2662116.jpeg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "Johannes Plenio"
            },
            {
                "url": "https://images.pexels.com/photos/33545/sunrise-phu-quoc-island-ocean.jpg?auto=compress&cs=tinysrgb&w=800",
                "source": "Pexels",
                "photographer": "Jcomp"
            }
        ]
    
    async def search_image(self, query: str, per_page: int = 1) -> Optional[Dict[str, Any]]:
        """Search for an image on Pexels based on the query."""
        if not self.pexels_api_key:
            return self._get_fallback_image()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                        return {
                            "url": photo.get("src", {}).get("large", photo.get("src", {}).get("original")),
                            "source": "Pexels",
                            "photographer": photo.get("photographer", "Unknown"),
                            "alt": photo.get("alt", query)
                        }
                
                return self._get_fallback_image()
                
        except Exception as e:
            print(f"Error fetching image from Pexels: {str(e)}")
            return self._get_fallback_image()
    
    def _get_fallback_image(self) -> Dict[str, Any]:
        """Get a random fallback image."""
        import random
        return random.choice(self.fallback_images)
    
    async def get_image_for_quote(self, quote: str, category: str, tags: list = None) -> Dict[str, Any]:
        """Get a relevant image for a quote."""
        # Build search query from quote context
        search_queries = []
        
        # Add category to search
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
        
        # Add tags if available
        if tags:
            search_queries.extend(tags[:2])
        
        # Try each query
        for query in search_queries:
            image = await self.search_image(query)
            if image:
                return image
        
        # If no image found, return fallback
        return self._get_fallback_image()
