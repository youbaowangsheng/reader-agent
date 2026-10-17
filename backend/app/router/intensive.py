"""精读训练路由。"""
from typing import List, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.service.intensive import IntensiveService

router = APIRouter(prefix="/api/intensive", tags=["intensive"])

_service = IntensiveService()


class ScoreRequest(BaseModel):
    key_points: List[str]
    summary: str


@router.get("/articles")
async def list_articles():
    return _service.list_articles()


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@router.get("/articles/{article_id}/guide")
async def get_guide(article_id: int):
    """返回已生成的导读（不重新生成）。"""
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    guide = _service.get_generated_guide(article_id)
    if not guide:
        raise HTTPException(404, "Guide not generated yet")
    return guide


@router.post("/articles/{article_id}/guide")
async def generate_guide(article_id: int):
    """生成导读（有缓存直接返回，不重复生成）。"""
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.generate_guide(article)


@router.get("/generated")
async def list_generated():
    """已生成导读的文章目录。"""
    return _service.list_generated()


@router.post("/articles/{article_id}/score")
async def score_summary(article_id: int, req: ScoreRequest):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.score_summary(article, req.key_points, req.summary)
