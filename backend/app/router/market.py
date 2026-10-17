from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import httpx
import os

from app.model.database import get_db
from app.model.paper import Paper
from app.model.fact_card import FactCard
from app.schema.market import (
    PaperRecommendItem,
    MarketSearchRequest,
    MarketSearchResponse,
    BookImportRequest,
)
from app.core.security import get_current_user, AuthUser
from app.router.papers import get_storage_url
from config import get_settings

router = APIRouter(prefix="/api/market", tags=["market"])
settings = get_settings()


@router.get("/recommendations", response_model=List[PaperRecommendItem])
async def get_recommendations(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Paper)
        .where(Paper.user_id == user.id, Paper.status == 'ready')
        .order_by(Paper.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    papers = result.scalars().all()
    return [
        PaperRecommendItem(id=p.id, filename=p.filename, status=p.status, tag="📄 已解析", hot_count=0)
        for p in papers
    ]


@router.get("/hot", response_model=List[PaperRecommendItem])
async def get_hot_papers(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
        PaperRecommendItem(id=row.id, filename=row.filename, status=row.status, tag="🔥 热读", hot_count=row.fact_count)
        for row in rows
    ]


@router.post("/search", response_model=MarketSearchResponse)
async def search_papers(
    req: MarketSearchRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
            PaperRecommendItem(id=p.id, filename=p.filename, status=p.status, tag="🔍 搜索结果", hot_count=0)
            for p in papers
        ],
    )


@router.post("/import-by-doi")
async def import_by_doi(
    doi: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"message": "DOI import not yet implemented", "doi": doi}


# ===== 图书市场（阿里云 OSS） =====
# OSS 图书目录约定：
#   {base}/books.json            -> {"books": [{title, cover_url, pdf_url, category, category_name, issue, size}]}
#   {base}/covers/{name}.jpg     -> 封面图
#   {base}/pdfs/{name}.pdf       -> PDF
# OSS 尚未配置时返回空列表 + oss_ready=false，前端显示"建设中"。

OSS_BOOKS_JSON_URL = os.environ.get("OSS_BOOKS_JSON_URL", "")


@router.get("/books")
async def list_books():
    """列出图书市场的书（从阿里云 OSS 读目录，未配置时返回空）。"""
    if not OSS_BOOKS_JSON_URL:
        return {"total": 0, "categories": [], "oss_ready": False}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OSS_BOOKS_JSON_URL)
            resp.raise_for_status()
            data = resp.json()
        books = data.get("books", []) if isinstance(data, dict) else []
    except Exception as e:
        return {"total": 0, "categories": [], "oss_ready": False, "error": str(e)[:120]}

    grouped = {}
    for b in books:
        cat = b.get("category", "其他")
        grouped.setdefault(cat, {"category": cat, "name": b.get("category_name", cat), "books": []})
        grouped[cat]["books"].append(b)
    return {"total": len(books), "categories": list(grouped.values()), "oss_ready": True}


@router.post("/import")
async def import_book(req: BookImportRequest):
    """下载图书 PDF 到书架（从 OSS，未配置时提示）。"""
    if not OSS_BOOKS_JSON_URL:
        raise HTTPException(503, "图书市场（OSS）尚未配置")
    # 未来：从 OSS 下载 req.pdf_url 到 storage，再走杂志拆分流程
    raise HTTPException(501, "OSS 下载尚未实现")
