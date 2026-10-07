from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from uuid import UUID

from app.model.database import get_db
from app.model.paper import Paper
from app.model.fact_card import FactCard
from app.schema.fact_card import (
    FactCardCreate,
    FactCardUpdate,
    FactCardResponse,
    FactCardDeleteResponse,
)
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/papers/{paper_id}/fact-cards", tags=["fact-cards"])


async def get_paper(paper_id: UUID, user_id: UUID, db: AsyncSession) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@router.get("", response_model=List[FactCardResponse])
async def list_fact_cards(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List fact cards for paper."""
    await get_paper(paper_id, user.id, db)

    stmt = (
        select(FactCard)
        .where(FactCard.paper_id == paper_id)
        .order_by(FactCard.created_at.desc())
    )
    result = await db.execute(stmt)
    cards = result.scalars().all()
    return [FactCardResponse.model_validate(c) for c in cards]


@router.post("", response_model=FactCardResponse)
async def create_fact_card(
    paper_id: UUID,
    card: FactCardCreate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a fact card."""
    await get_paper(paper_id, user.id, db)

    fact_card = FactCard(
        paper_id=paper_id,
        claim=card.claim,
        evidence=card.evidence,
        confidence=card.confidence,
        source=card.source,
        created_by=card.created_by,
        creator_id=card.creator_id or user.id,
    )
    db.add(fact_card)
    await db.commit()
    await db.refresh(fact_card)

    return FactCardResponse.model_validate(fact_card)


@router.get("/{fact_card_id}", response_model=FactCardResponse)
async def get_fact_card(
    paper_id: UUID,
    fact_card_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific fact card."""
    await get_paper(paper_id, user.id, db)

    stmt = select(FactCard).where(
        FactCard.id == fact_card_id,
        FactCard.paper_id == paper_id,
    )
    result = await db.execute(stmt)
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(404, "Fact card not found")

    return FactCardResponse.model_validate(card)


@router.put("/{fact_card_id}", response_model=FactCardResponse)
async def update_fact_card(
    paper_id: UUID,
    fact_card_id: UUID,
    card: FactCardUpdate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a fact card."""
    await get_paper(paper_id, user.id, db)

    stmt = select(FactCard).where(
        FactCard.id == fact_card_id,
        FactCard.paper_id == paper_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(404, "Fact card not found")

    if card.claim is not None:
        existing.claim = card.claim
    if card.evidence is not None:
        existing.evidence = card.evidence
    if card.confidence is not None:
        existing.confidence = card.confidence
    if card.source is not None:
        existing.source = card.source

    await db.commit()
    await db.refresh(existing)

    return FactCardResponse.model_validate(existing)


@router.delete("/{fact_card_id}", response_model=FactCardDeleteResponse)
async def delete_fact_card(
    paper_id: UUID,
    fact_card_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a fact card."""
    await get_paper(paper_id, user.id, db)

    stmt = delete(FactCard).where(
        FactCard.id == fact_card_id,
        FactCard.paper_id == paper_id,
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(404, "Fact card not found")

    return FactCardDeleteResponse(deleted=True, fact_card_id=fact_card_id)
