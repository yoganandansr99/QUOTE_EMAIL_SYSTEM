from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CategoryImage(BaseModel):
    category: str
    filename: str
    content_type: str = "image/jpeg"
    image_reference: str
    url: str
    photographer: Optional[str] = None
    source: Optional[str] = "Pexels / Curated CC0"
    alt: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CategoryImageInDB(CategoryImage):
    id: str
