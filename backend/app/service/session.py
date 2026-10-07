from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.session_memory import SessionMemory


class SessionService:
    """Session memory management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_memory(
        self, paper_id: UUID, session_id: UUID, limit: int = 50
    ) -> List[SessionMemory]:
        """Get session memory turns."""
        stmt = (
            select(SessionMemory)
            .where(
                SessionMemory.paper_id == paper_id,
                SessionMemory.session_id == session_id,
            )
            .order_by(SessionMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_turn(
        self,
        paper_id: UUID,
        session_id: UUID,
        turn_type: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        facts: Optional[List[Dict[str, Any]]] = None,
    ) -> SessionMemory:
        """Add a turn to session memory."""
        turn = SessionMemory(
            paper_id=paper_id,
            session_id=session_id,
            turn_type=turn_type,
            question=question,
            answer=answer,
            citations=citations or [],
            facts=facts or [],
        )
        self.db.add(turn)
        await self.db.commit()
        await self.db.refresh(turn)
        return turn

    async def clear_memory(self, paper_id: UUID, session_id: UUID) -> int:
        """Clear session memory. Returns number of deleted turns."""
        stmt = delete(SessionMemory).where(
            SessionMemory.paper_id == paper_id,
            SessionMemory.session_id == session_id,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def get_recent_facts(
        self, paper_id: UUID, session_id: UUID, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent facts from memory for context."""
        turns = await self.get_memory(paper_id, session_id, limit=limit)
        facts: List[Dict[str, Any]] = []
        for turn in turns:
            if turn.facts and isinstance(turn.facts, list):
                for f in turn.facts[:3]:
                    facts.append(
                        {
                            "claim": str(f.get("claim", ""))[:260],
                            "confidence": f.get("confidence", 0.5),
                            "evidence": str(f.get("evidence", ""))[:240],
                            "citations": turn.citations[:3] if turn.citations else [],
                        }
                    )
            else:
                # Fallback to answer as fact
                if turn.answer:
                    facts.append(
                        {
                            "claim": turn.answer[:260],
                            "confidence": 0.5,
                            "evidence": "由回答自动回填",
                            "citations": turn.citations[:3] if turn.citations else [],
                        }
                    )
        return facts[:limit]


def get_session_service(db: AsyncSession) -> SessionService:
    return SessionService(db)