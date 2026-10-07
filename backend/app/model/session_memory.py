from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UUID
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.model.database import Base


class SessionMemory(Base):
    __tablename__ = "session_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    turn_type = Column(String(20), nullable=False)  # 'user' or 'assistant'
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    citations = Column(JSONB, default=list)
    facts = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    paper = relationship("Paper", back_populates="session_memory")

    __table_args__ = (
        Index("ix_session_paper_session", "paper_id", "session_id"),
    )