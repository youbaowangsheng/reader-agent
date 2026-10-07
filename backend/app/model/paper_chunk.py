from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, UniqueConstraint, Index, UUID
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.model.database import Base


class PaperChunk(Base):
    __tablename__ = "paper_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(50), nullable=False)  # e.g. "doc_abc_c0001"
    heading = Column(String(255), default="")
    page_range = Column(String(50), default="")
    chapter_index = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    paper = relationship("Paper", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("paper_id", "chunk_id", name="uq_paper_chunk"),
        Index("ix_paper_chunk_paper_id", "paper_id"),
    )