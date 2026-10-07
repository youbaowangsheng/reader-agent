from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PaperInProject(BaseModel):
    id: UUID
    filename: str
    status: str
    added_at: datetime


class ProjectListItem(BaseModel):
    id: UUID
    name: str
    description: str
    paper_count: int
    created_at: datetime
    updated_at: datetime


class ProjectDetail(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    papers: List[PaperInProject]
    created_at: datetime
    updated_at: datetime
