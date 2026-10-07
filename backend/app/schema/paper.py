from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class PaperBase(BaseModel):
    filename: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PaperCreate(PaperBase):
    user_id: UUID


class PaperSummary(BaseModel):
    id: UUID
    user_id: UUID
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaperDetail(BaseModel):
    id: UUID
    user_id: UUID
    filename: str
    file_url: str
    paper_metadata: Dict[str, Any] = Field(default_factory=dict)
    parsed_structure: Dict[str, Any] = Field(default_factory=dict)
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaperUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    message: str


class PaperDeleteResponse(BaseModel):
    deleted: bool
    paper_id: UUID