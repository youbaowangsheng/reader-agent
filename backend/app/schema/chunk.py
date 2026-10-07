from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


class ChunkSearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkSearchResult(BaseModel):
    chunk_id: str
    score: float
    heading: str
    page_range: str
    chapter_index: Optional[int] = None
    text: str


class ChunkDetail(BaseModel):
    id: UUID
    chunk_id: str
    heading: str
    page_range: str
    chapter_index: Optional[int] = None
    content: str


class Citation(BaseModel):
    chunk_id: str
    quote: str
    heading: str
    page_range: str


class QARequest(BaseModel):
    question: str
    chat_history: List[dict] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class QAResponse(BaseModel):
    answer: str
    citations: List[Citation]
    facts: List[dict]
    fact_conflicts: Optional[List[dict]] = None