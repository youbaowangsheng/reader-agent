from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class MemoryTurn(BaseModel):
    turn_type: str  # 'user' or 'assistant'
    question: Optional[str] = None
    answer: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class SessionMemoryResponse(BaseModel):
    paper_id: UUID
    session_id: UUID
    turns: List[MemoryTurn]
    total_count: int


class AddMemoryRequest(BaseModel):
    turn_type: str = Field(..., pattern="^(user|assistant)$")
    question: Optional[str] = None
    answer: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    facts: List[Dict[str, Any]] = Field(default_factory=list)


class AddMemoryResponse(BaseModel):
    added: bool
    turn_id: UUID


class ClearMemoryResponse(BaseModel):
    cleared: bool
    paper_id: UUID
    session_id: UUID