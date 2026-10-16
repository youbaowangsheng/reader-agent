"""泛读训练服务：新闻短文语料加载 + 大意检测 + 评分。"""
import json
import os
from typing import Any, Dict, List, Optional

from app.service.llm import LLMService


class ExtensiveService:
    """泛读训练（新闻短文快速读 + 大意检测），独立于精读语料。"""

    def __init__(self):
        self.articles = self._load_articles()

    def _data_path(self) -> str:
        # backend/data/news_articles.json
        return os.path.join(os.path.dirname(__file__), "..", "..", "data", "news_articles.json")

    def _load_articles(self) -> List[Dict[str, Any]]:
        try:
            with open(self._data_path(), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
        result = []
        for i, a in enumerate(data):
            body = a.get("body", "")
            if not body or len(body.split()) < 80:
                continue
            result.append({
                "id": i,
                "title": a.get("title", ""),
                "body": body,
                "word_count": a.get("word_count", len(body.split())),
                "source": a.get("source", ""),
                "link": a.get("link", ""),
            })
        return result

    def list_articles(self) -> List[Dict[str, Any]]:
        return [
            {"id": a["id"], "title": a["title"],
             "word_count": a["word_count"], "source": a["source"]}
            for a in self.articles
        ]

    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        for a in self.articles:
            if a["id"] == article_id:
                return a
        return None

    async def generate_questions(self, article: Dict[str, Any]) -> Dict[str, Any]:
        llm = LLMService()
        return await llm.generate_extensive_questions(article["title"], article["body"])

    async def score(
        self, article: Dict[str, Any],
        questions: List[Dict[str, Any]], answers: Dict[str, str],
    ) -> Dict[str, Any]:
        llm = LLMService()
        return await llm.score_extensive(article["title"], article["body"], questions, answers)
