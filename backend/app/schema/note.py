from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID


class NoteBase(BaseModel):
    pass


class KeyConcept(BaseModel):
    term: str
    definition: str
    page_ref: List[int] = Field(default_factory=list)


class KeyCitation(BaseModel):
    ref_id: str
    role: str
    description: str


class OverallEvaluation(BaseModel):
    novelty: int = Field(default=3, ge=1, le=5, description="1-5星级评分")
    rigor: int = Field(default=3, ge=1, le=5)
    reproducibility: int = Field(default=3, ge=1, le=5)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    recommendation: str = Field(default="⚪按需", description="🔴精读 / 🟡速读 / ⚪按需")


class PaperNoteDetail(BaseModel):
    id: UUID
    paper_id: UUID
    summary: str
    key_concepts: List[KeyConcept]
    key_citations: List[KeyCitation]
    critical_questions: List[str]
    overall_evaluation: OverallEvaluation

    model_config = {"from_attributes": True}


class NoteGenerateRequest(BaseModel):
    force_refresh: bool = False


class NoteGenerateResponse(BaseModel):
    paper_id: UUID
    status: str
    message: str