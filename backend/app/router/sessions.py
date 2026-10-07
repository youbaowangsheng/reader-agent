from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.model.database import get_db
from app.model.paper import Paper
from app.model.session_memory import SessionMemory
from app.schema.session import (
    SessionMemoryResponse,
    AddMemoryRequest,
    AddMemoryResponse,
    ClearMemoryResponse,
    MemoryTurn,
)
from app.service.session import SessionService
from app.core.security import get_current_user, AuthUser

router = APIRouter(
    prefix="/api/papers/{paper_id}/sessions/{session_id}/memory",
    tags=["sessions"],
)


async def get_paper(paper_id: UUID, user_id: UUID, db: AsyncSession) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@router.get("", response_model=SessionMemoryResponse)
async def get_memory(
    paper_id: UUID,
    session_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """Get session memory."""
    await get_paper(paper_id, user.id, db)

    session_service = SessionService(db)
    turns = await session_service.get_memory(paper_id, session_id, limit=limit)

    return SessionMemoryResponse(
        paper_id=paper_id,
        session_id=session_id,
        turns=[MemoryTurn.model_validate(t) for t in turns],
        total_count=len(turns),
    )


@router.post("", response_model=AddMemoryResponse)
async def add_memory(
    paper_id: UUID,
    session_id: UUID,
    request: AddMemoryRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a turn to session memory."""
    await get_paper(paper_id, user.id, db)

    session_service = SessionService(db)
    turn = await session_service.add_turn(
        paper_id=paper_id,
        session_id=session_id,
        turn_type=request.turn_type,
        question=request.question,
        answer=request.answer,
        citations=request.citations,
        facts=request.facts,
    )

    return AddMemoryResponse(added=True, turn_id=turn.id)


@router.delete("", response_model=ClearMemoryResponse)
async def clear_memory(
    paper_id: UUID,
    session_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear session memory."""
    await get_paper(paper_id, user.id, db)

    session_service = SessionService(db)
    count = await session_service.clear_memory(paper_id, session_id)

    return ClearMemoryResponse(
        cleared=True,
        paper_id=paper_id,
        session_id=session_id,
    )
