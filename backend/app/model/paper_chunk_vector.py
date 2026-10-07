from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, UUID
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.model.database import Base


class PaperChunkVector(Base):
    __tablename__ = "paper_chunks_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(String(50), nullable=False)
    # pgvector vector type - stored as TEXT in SQLAlchemy, database handles vector type
    embedding = Column(Text, nullable=False)  # JSON serialized list of floats

    paper = relationship("Paper", back_populates="vectors")

    __table_args__ = (
        UniqueConstraint("paper_id", "chunk_id", name="uq_paper_vector"),
        Index("ix_paper_vector_paper_id", "paper_id"),
    )