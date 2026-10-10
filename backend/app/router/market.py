from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import httpx
import time
import uuid
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
from app.router.papers import process_paper_task, get_storage_url
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


# ===== GitHub 图书市场 =====
import re

GITHUB_OWNER = "youbaowangsheng"
GITHUB_REPO = "awesome-english-ebooks"
GITHUB_BRANCH = "master"

CATEGORY_NAMES = {
    "01_economist": "经济学人",
    "02_new_yorker": "纽约客",
    "04_atlantic": "大西洋月刊",
    "05_wired": "连线",
}

_books_cache = {"data": None, "ts": 0}
_BOOKS_CACHE_TTL = 3600  # 1 小时


async def _fetch_books():
    """从 GitHub 仓库读取图书（英语杂志）列表，带缓存。"""
    now = time.time()
    if _books_cache["data"] and now - _books_cache["ts"] < _BOOKS_CACHE_TTL:
        return _books_cache["data"]

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}?recursive=1"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        tree = resp.json().get("tree", [])

    books = []
    for item in tree:
        path = item.get("path", "")
        if not path.endswith(".pdf"):
            continue
        parts = path.split("/")
        if len(parts) < 3:
            continue
        category, issue_dir, filename = parts[0], parts[1], parts[2]
        if category not in CATEGORY_NAMES:
            continue
        m = re.search(r"\d{4}\.\d{2}\.\d{2}", issue_dir)
        issue = m.group(0) if m else issue_dir
        books.append({
            "category": category,
            "category_name": CATEGORY_NAMES[category],
            "issue": issue,
            "filename": filename,
            "pdf_path": path,
            "size": item.get("size", 0),
        })

    books.sort(key=lambda b: (b["category"], b["issue"]), reverse=True)
    _books_cache["data"] = books
    _books_cache["ts"] = now
    return books


@router.get("/books")
async def list_books(user: AuthUser = Depends(get_current_user)):
    """列出 GitHub 仓库里的图书，按杂志分类分组。"""
    try:
        books = await _fetch_books()
    except Exception as e:
        raise HTTPException(502, f"获取图书列表失败: {str(e)[:120]}")

    grouped = {}
    for b in books:
        grouped.setdefault(b["category"], {"category": b["category"], "name": b["category_name"], "books": []})
        grouped[b["category"]]["books"].append(b)
    return {"total": len(books), "categories": list(grouped.values())}


@router.post("/import")
async def import_book(
    req: BookImportRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """下载图书 PDF 到书架并触发解析。"""
    raw_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{req.pdf_path}?ref={GITHUB_BRANCH}"
    file_id = uuid.uuid4()
    stored_filename = f"{file_id}_{req.filename}"
    storage_dir = settings.storage_url
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, stored_filename)

    try:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            resp = await client.get(raw_url, headers={"Accept": "application/vnd.github.raw"})
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)
    except Exception as e:
        raise HTTPException(502, f"下载失败: {str(e)[:120]}")

    paper = Paper(
        id=file_id,
        user_id=user.id,
        filename=req.filename,
        file_url=get_storage_url(stored_filename),
        status="pending",
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    background_tasks.add_task(process_paper_task, file_id, settings.database_url)
    return {"id": file_id, "filename": req.filename, "status": "processing", "message": "已下载到书架，正在解析"}
