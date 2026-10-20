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


# ===== 图书市场（多源：GitHub repo + OSS 混合） =====
import re
import time
import asyncio

from app.service.magazine import MagazineService

# 顶层文件夹名 → 中文分类名；未映射的用原始文件夹名
CATEGORY_NAMES = {
    "01_economist": "经济学人",
    "02_new_yorker": "纽约客",
    "04_atlantic": "大西洋月刊",
    "05_wired": "连线",
}

_books_cache = {"data": None, "ts": 0}
_BOOKS_CACHE_TTL = 3600

_magazine_service = MagazineService()


def _parse_book_path(path: str, source_name: str, size: int = 0) -> Optional[dict]:
    """把仓库/OSS 里的相对路径解析成 book 记录。路径约定：category/issue/filename.pdf"""
    parts = path.split("/")
    if len(parts) < 3:
        return None
    category, issue_dir, filename = parts[0], parts[1], parts[2]
    m = re.search(r"\d{4}\.\d{2}\.\d{2}", issue_dir)
    issue = m.group(0) if m else issue_dir
    return {
        "category": category,
        "category_name": CATEGORY_NAMES.get(category, category),
        "issue": issue,
        "filename": filename,
        "pdf_path": path,
        "size": size,
        "source": source_name,
    }


async def _fetch_github_books(source: dict) -> list:
    """从单个 GitHub repo 拉取 PDF 列表。"""
    owner, repo, branch = source.get("owner"), source.get("repo"), source.get("branch", "master")
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        tree = resp.json().get("tree", [])

    books = []
    for item in tree:
        path = item.get("path", "")
        if not path.endswith(".pdf"):
            continue
        b = _parse_book_path(path, source.get("name") or f"{owner}/{repo}", item.get("size", 0))
        if b:
            books.append(b)
    return books


async def _fetch_oss_books(source: dict) -> list:
    """从阿里云 OSS bucket 拉取 PDF 列表（prefix 过滤 .pdf）。SDK 缺失或配置不全时返回空。"""
    try:
        import oss2
    except ImportError:
        return []
    bucket_name, endpoint = source.get("bucket"), source.get("endpoint")
    ak, sk = source.get("access_key_id"), source.get("access_key_secret")
    prefix = source.get("prefix", "")
    if not (bucket_name and endpoint and ak and sk):
        return []
    try:
        bucket = oss2.Bucket(oss2.Auth(ak, sk), endpoint, bucket_name)
        books = []
        for obj in oss2.ObjectIterator(bucket, prefix=prefix):
            key = obj.key
            if not key.endswith(".pdf"):
                continue
            rel = key[len(prefix):].lstrip("/") if prefix else key
            b = _parse_book_path(rel, source.get("name") or bucket_name, obj.size)
            if b:
                books.append(b)
        return books
    except Exception:
        return []


async def _fetch_all_books():
    """并行拉取所有源，合并去重（相同 category+issue+filename 合并 source 标签）。"""
    now = time.time()
    if _books_cache["data"] and now - _books_cache["ts"] < _BOOKS_CACHE_TTL:
        return _books_cache["data"]

    sources = settings.market_sources()
    results = await asyncio.gather(*[
        (_fetch_github_books(s) if s.get("type") == "github" else _fetch_oss_books(s))
        for s in sources
    ], return_exceptions=True)

    merged = {}
    for books in results:
        if isinstance(books, Exception):
            continue  # 单个源失败不阻塞其他源
        for b in books:
            key = (b["category"], b["issue"], b["filename"])
            if key in merged:
                if b["source"] not in merged[key]["source"]:
                    merged[key]["source"] += "、" + b["source"]
            else:
                merged[key] = b

    books = sorted(merged.values(), key=lambda b: (b["category"], b["issue"]), reverse=True)
    _books_cache["data"] = books
    _books_cache["ts"] = now
    return books


def _find_source(name: str) -> Optional[dict]:
    for s in settings.market_sources():
        if s.get("name") == name:
            return s
    return None


@router.get("/books")
async def list_books(user: AuthUser = Depends(get_current_user), refresh: int = 0):
    """列出所有源的图书，合并成一个列表按文件夹分类，书标来源。refresh=1 强制重新拉取。"""
    if refresh:
        _books_cache["data"] = None
        _books_cache["ts"] = 0
    try:
        books = await _fetch_all_books()
    except Exception as e:
        raise HTTPException(502, f"获取图书列表失败: {str(e)[:120]}")

    grouped = {}
    for b in books:
        grouped.setdefault(b["category"], {"category": b["category"], "name": b["category_name"], "books": []})
        grouped[b["category"]]["books"].append(b)
    return {"total": len(books), "categories": list(grouped.values())}


@router.post("/import")
async def import_book(req: BookImportRequest, user: AuthUser = Depends(get_current_user)):
    """从指定源下载图书 PDF 并拆分进杂志书架。"""
    source = _find_source(req.source) if req.source else None
    # 兼容旧调用：没传 source 时默认第一个源
    if not source:
        sources = settings.market_sources()
        if not sources:
            raise HTTPException(400, "未配置图书源")
        source = sources[0]

    try:
        if source.get("type") == "github":
            raw_url = f"https://api.github.com/repos/{source['owner']}/{source['repo']}/contents/{req.pdf_path}?ref={source.get('branch', 'master')}"
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                resp = await client.get(raw_url, headers={"Accept": "application/vnd.github.raw"})
                resp.raise_for_status()
                content = resp.content
        elif source.get("type") == "oss":
            try:
                import oss2
            except ImportError:
                raise HTTPException(502, "OSS SDK 未安装")
            prefix = source.get("prefix", "")
            key = req.pdf_path if (not prefix or req.pdf_path.startswith(prefix)) else prefix + req.pdf_path
            bucket = oss2.Bucket(oss2.Auth(source["access_key_id"], source["access_key_secret"]), source["endpoint"], source["bucket"])
            content = bucket.get_object(key).read()
        else:
            raise HTTPException(400, f"不支持的类型: {source.get('type')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"下载失败: {str(e)[:120]}")

    mag = _magazine_service.save_upload(req.filename, content)
    return {
        "id": mag["id"],
        "filename": mag["filename"],
        "status": mag["status"],
        "article_count": mag["article_count"],
        "message": f"已下载并拆分，{mag['article_count']} 篇文章，去书架点「评级入库」",
    }
