from pydantic import BaseModel
from typing import List
from uuid import UUID


class PaperRecommendItem(BaseModel):
    id: UUID
    filename: str
    status: str
    tag: str
    hot_count: int = 0


class MarketSearchRequest(BaseModel):
    query: str


class MarketSearchResponse(BaseModel):
    query: str
    results: List[PaperRecommendItem]
