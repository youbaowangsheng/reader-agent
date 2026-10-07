from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Float, UUID
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.model.database import Base


class FactCard(Base):
    __tablename__ = "fact_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    claim = Column(Text, nullable=False)
    evidence = Column(Text, default="")
    confidence = Column(Float, default=0.5)  # 0.0 - 1.0
    source = Column(JSONB, default=dict)  # {chunk_id, page, heading}
    created_by = Column(String(20), nullable=False)  # 'ai' or 'user'
    creator_id = Column(PGUUID, nullable=True)  # user UUID if created_by='user'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    paper = relationship("Paper", back_populates="fact_cards")