from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class FactCardBase(BaseModel):
    claim: str
    evidence: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source: Dict[str, Any] = Field(default_factory=dict)


class FactCardCreate(FactCardBase):
    created_by: str = "user"
    creator_id: Optional[UUID] = None


class FactCardUpdate(BaseModel):
    claim: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = Field(ge=0.0, le=1.0, default=None)
    source: Optional[Dict[str, Any]] = None


class FactCardResponse(FactCardBase):
    id: UUID
    paper_id: UUID
    created_by: str
    creator_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FactCardDeleteResponse(BaseModel):
    deleted: bool
    fact_card_id: UUID