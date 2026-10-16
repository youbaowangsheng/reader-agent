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


class ExtensiveScoreRequest(BaseModel):
    passage: str
    questions: List[dict]
    answers: Dict[str, str]


@router.get("/articles")
async def list_articles():
    return _service.list_articles()


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@router.post("/articles/{article_id}/guide")
async def generate_guide(article_id: int):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.generate_guide(article)


@router.post("/articles/{article_id}/score")
async def score_summary(article_id: int, req: ScoreRequest):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.score_summary(article, req.key_points, req.summary)


@router.post("/articles/{article_id}/extensive")
async def generate_extensive(article_id: int):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.generate_extensive(article)


@router.post("/articles/{article_id}/extensive/score")
async def score_extensive(article_id: int, req: ExtensiveScoreRequest):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.score_extensive(article, req.passage, req.questions, req.answers)
