from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib


class Quote(BaseModel):
    quote: str
    author: str
    category: str
    tags: List[str] = []
    image_url: Optional[str] = None
    image_source: Optional[str] = None
    image_photographer: Optional[str] = None
    image_search_query: Optional[str] = None
    person_story: Optional[str] = None
    daily_action: Optional[str] = None
    quote_hash: str = ""
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()
    
    def generate_hash(self) -> str:
        normalized = f"{self.quote.lower().strip()}-{self.author.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()


class QuoteCreate(BaseModel):
    quote: str
    author: str
    category: str
    tags: List[str] = []
    image_url: Optional[str] = None
    image_source: Optional[str] = None
    image_photographer: Optional[str] = None
    image_search_query: Optional[str] = None
    person_story: Optional[str] = None
    daily_action: Optional[str] = None


class QuoteInDB(Quote):
    id: str
