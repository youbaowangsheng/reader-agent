"""泛读训练服务：新闻短文语料加载 + 大意检测 + 评分。"""
import json
import os
from typing import Any, Dict, List, Optional

from app.service.llm import LLMService
from app.service.generated import GeneratedStore, now_iso


class ExtensiveService:
    """泛读训练（新闻短文快速读 + 大意检测），独立于精读语料。"""

    def __init__(self):
        data_dir = os.path.dirname(self._data_path())
        self.question_store = GeneratedStore(os.path.join(data_dir, "generated", "questions.json"))

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
                "created_at": a.get("created_at", ""),
            })
        return result

    def list_articles(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        articles = self._load_articles()
        # 新入库（杂志评级）排在前面
        articles.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        return [
            {"id": a["id"], "title": a["title"],
             "word_count": a["word_count"], "source": a["source"],
             "created_at": a.get("created_at", "")}
            for a in articles[offset:offset + limit]
        ]

    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        for a in self._load_articles():
            if a["id"] == article_id:
                return a
        return None

    def get_generated_questions(self, article_id: int) -> Optional[Dict[str, Any]]:
        """返回已生成的大意检测题（不重新生成），无则 None。"""
        cached = self.question_store.get(article_id)
        return cached.get("questions") if cached else None

    def list_generated(self) -> List[Dict[str, Any]]:
        """列出所有已生成检测题的文章（目录页用）。"""
        result = []
        for aid, cached in self.question_store.all().items():
            try:
                article = self.get_article(int(aid))
            except ValueError:
                continue
            if not article:
                continue
            result.append({
                "article_id": article["id"],
                "title": article["title"],
                "word_count": article["word_count"],
                "source": article["source"],
                "generated_at": cached.get("generated_at", ""),
            })
        result.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
        return result

    async def generate_questions(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """生成大意检测题（有缓存直接返回，避免重复生成）。"""
        cached = self.question_store.get(article["id"])
        if cached and cached.get("questions"):
            return cached["questions"]
        llm = LLMService()
        questions = await llm.generate_extensive_questions(article["title"], article["body"])
        if questions and "error" not in questions:
            self.question_store.set(
                article["id"], {"questions": questions, "generated_at": now_iso()}
            )
        return questions

    async def score(
        self, article: Dict[str, Any],
        questions: List[Dict[str, Any]], answers: Dict[str, str],
    ) -> Dict[str, Any]:
        llm = LLMService()
        return await llm.score_extensive(article["title"], article["body"], questions, answers)
