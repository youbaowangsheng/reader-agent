"""精读训练服务：语料库加载 + 精读带读生成 + 概要写作评分。"""
import json
import os
from typing import Any, Dict, List, Optional

from app.service.llm import LLMService


class IntensiveService:
    """精读训练（真实外刊 AI 带读 + 概要写作），独立于论文解析流程。"""

    def __init__(self):
        self.articles = self._load_articles()

    def _data_path(self) -> str:
        # backend/data/articles_v1.json
        return os.path.join(os.path.dirname(__file__), "..", "..", "data", "articles_v1.json")

    def _load_articles(self) -> List[Dict[str, Any]]:
        try:
            with open(self._data_path(), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
        result = []
        for i, a in enumerate(data):
            body = a.get("body", "")
            if not body or len(body.split()) < 200:
                continue
            result.append({
                "id": i,
                "title": a.get("title", ""),
                "body": body,
                "level": a.get("level", "L4"),
                "topic": a.get("topic", ""),
                "word_count": a.get("word_count", len(body.split())),
                "source": a.get("source", ""),
            })
        return result

    def list_articles(self) -> List[Dict[str, Any]]:
        return [
            {"id": a["id"], "title": a["title"], "level": a["level"],
             "topic": a["topic"], "word_count": a["word_count"]}
            for a in self.articles
        ]

    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        for a in self.articles:
            if a["id"] == article_id:
                return a
        return None

    async def generate_guide(self, article: Dict[str, Any]) -> Dict[str, Any]:
        llm = LLMService()
        return await llm.generate_intensive_guide(article["title"], article["body"])

    async def score_summary(
        self, article: Dict[str, Any], key_points: List[str], summary: str
    ) -> Dict[str, Any]:
        llm = LLMService()
        return await llm.score_summary(article["title"], article["body"], key_points, summary)
