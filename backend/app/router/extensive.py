"""泛读训练路由。"""
import os
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.service.extensive import ExtensiveService
from app.service.level import LevelStore

router = APIRouter(prefix="/api/extensive", tags=["extensive"])

_service = ExtensiveService()
_level_store = LevelStore(os.path.join(os.path.dirname(__file__), "..", "..", "data", "level.json"))


class ExtensiveScoreRequest(BaseModel):
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


@router.get("/articles/{article_id}/questions")
async def get_questions(article_id: int):
    """返回已生成的大意检测题（不重新生成）。"""
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    questions = _service.get_generated_questions(article_id)
    if not questions:
        raise HTTPException(404, "Questions not generated yet")
    return questions


@router.get("/generated")
async def list_generated():
    """已生成检测题的文章目录。"""
    return _service.list_generated()


@router.post("/articles/{article_id}/questions")
async def generate_questions(article_id: int):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return await _service.generate_questions(article)


@router.post("/articles/{article_id}/score")
async def score_answers(article_id: int, req: ExtensiveScoreRequest):
    article = _service.get_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    result = await _service.score(article, req.questions, req.answers)
    # 难度自适应：正确率低降档、高升档
    try:
        results = result.get("results", []) or []
        if results:
            correct = sum(1 for r in results if r.get("correct"))
            rate = correct / len(results)
            if rate < 0.6:
                result["level"] = _level_store.adjust(-1)
            elif rate > 0.9:
                result["level"] = _level_store.adjust(1)
            else:
                result["level"] = _level_store.get_level()
    except Exception:
        pass
    return result
