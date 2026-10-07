from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import httpx

from app.model.database import get_db
from app.model.paper import Paper
from app.model.fact_card import FactCard
from app.schema.market import (
    PaperRecommendItem,
    MarketSearchRequest,
    MarketSearchResponse,
)
from app.core.security import get_current_user, AuthUser
from config import get_settings

router = APIRouter(prefix="/api/market", tags=["market"])
settings = get_settings()


@router.get("/recommendations", response_model=List[PaperRecommendItem])
async def get_recommendations(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI-recommended papers for the user based on their projects."""
    # For now, return a curated list of ready papers
    # In production, this would call FIPAI to generate recommendations
    stmt = (
        select(Paper)
        .where(Paper.user_id == user.id, Paper.status == 'ready')
        .order_by(Paper.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    papers = result.scalars().all()

    return [
        PaperRecommendItem(
            id=p.id,
            filename=p.filename,
            status=p.status,
            tag="📄 已解析",
            hot_count=0,
        )
        for p in papers
    ]


@router.get("/hot", response_model=List[PaperRecommendItem])
async def get_hot_papers(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get hot papers with most annotations."""
    stmt = (
        select(
            Paper.id,
            Paper.filename,
            Paper.status,
            func.count(FactCard.id).label('fact_count'),
        )
        .outerjoin(FactCard, Paper.id == FactCard.paper_id)
        .where(Paper.user_id == user.id)
        .group_by(Paper.id)
        .order_by(func.count(FactCard.id).desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        PaperRecommendItem(
            id=row.id,
            filename=row.filename,
            status=row.status,
            tag="🔥 热读",
            hot_count=row.fact_count,
        )
        for row in rows
    ]


@router.post("/search", response_model=MarketSearchResponse)
async def search_papers(
    req: MarketSearchRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search papers by filename or metadata."""
    search = f"%{req.query}%"
    stmt = (
        select(Paper)
        .where(
            Paper.user_id == user.id,
            Paper.filename.ilike(search),
        )
        .order_by(Paper.status == 'ready', Paper.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    papers = result.scalars().all()

    return MarketSearchResponse(
        query=req.query,
        results=[
            PaperRecommendItem(
                id=p.id,
                filename=p.filename,
                status=p.status,
                tag="🔍 搜索结果",
                hot_count=0,
            )
            for p in papers
        ],
    )


@router.post("/import-by-doi")
async def import_by_doi(
    doi: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import paper by DOI (placeholder - would download from arXiv/DOI)."""
    # Placeholder: in production, would call FIPAI or arXiv API
    return {
        "message": "DOI import not yet implemented",
        "doi": doi,
    }
