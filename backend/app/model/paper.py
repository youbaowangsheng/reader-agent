from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.model.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    paper_metadata = Column(JSONB, default=dict)  # title, authors, abstract, keywords
    parsed_structure = Column(JSONB, default=dict)  # pages, chunks, toc
    reading_guide = Column(JSONB, default=dict)  # AI 导读产物（reading_plan/summary/trail/verdict/quiz）
    user_engagement = Column(JSONB, default=dict)  # 用户交互（judgments/notes/my_view/quiz_answers）
    status = Column(String(50), default="pending")  # pending/processing/ready/error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_read_at = Column(DateTime(timezone=True), nullable=True)  # 最后阅读时间（待读列表排序）

    # Relationships
    notes = relationship("PaperNote", back_populates="paper", uselist=False, cascade="all, delete-orphan")
    chunks = relationship("PaperChunk", back_populates="paper", cascade="all, delete-orphan")
    vectors = relationship("PaperChunkVector", back_populates="paper", cascade="all, delete-orphan")
    fact_cards = relationship("FactCard", back_populates="paper", cascade="all, delete-orphan")
    session_memory = relationship("SessionMemory", back_populates="paper", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_papers_user_created", "user_id", "created_at"),)


class PaperNote(Base):
    __tablename__ = "paper_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary = Column(Text, default="")
    key_concepts = Column(JSONB, default=list)  # [{term, definition, page_ref}]
    key_citations = Column(JSONB, default=list)  # [{ref_id, role, description}]
    critical_questions = Column(JSONB, default=list)  # [question]
    overall_evaluation = Column(JSONB, default=dict)  # {novelty, rigor, reproducibility, pros, cons, recommendation}
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    paper = relationship("Paper", back_populates="notes")