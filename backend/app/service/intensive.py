"""精读训练服务：语料库加载 + 精读导读生成（持久化）+ 概要写作评分。"""
import json
import os
from typing import Any, Dict, List, Optional

from app.service.llm import LLMService
from app.service.generated import GeneratedStore, now_iso


class IntensiveService:
    """精读训练（真实外刊 AI 导读 + 概要写作），独立于论文解析流程。"""

    def __init__(self):
        data_dir = os.path.dirname(self._data_path())
        self.guide_store = GeneratedStore(os.path.join(data_dir, "generated", "guides.json"))

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
                "created_at": a.get("created_at", ""),
            })
        return result

    def list_articles(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        articles = self._load_articles()
        # 新入库（杂志评级）排在前面
        articles.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        return [
            {"id": a["id"], "title": a["title"], "level": a["level"],
             "topic": a["topic"], "word_count": a["word_count"],
             "created_at": a.get("created_at", "")}
            for a in articles[offset:offset + limit]
        ]

    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        for a in self._load_articles():
            if a["id"] == article_id:
                return a
        return None

    def get_generated_guide(self, article_id: int) -> Optional[Dict[str, Any]]:
        """返回已生成的导读（不重新生成），无则 None。"""
        cached = self.guide_store.get(article_id)
        return cached.get("guide") if cached else None

    def list_generated(self) -> List[Dict[str, Any]]:
        """列出所有已生成导读的文章（目录页用）。"""
        result = []
        for aid, cached in self.guide_store.all().items():
            try:
                article = self.get_article(int(aid))
            except ValueError:
                continue
            if not article:
                continue
            result.append({
                "article_id": article["id"],
                "title": article["title"],
                "level": article["level"],
                "topic": article["topic"],
                "word_count": article["word_count"],
                "generated_at": cached.get("generated_at", ""),
            })
        result.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
        return result

    async def generate_guide(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """生成导读（有缓存直接返回，避免重复生成浪费 token）。"""
        cached = self.guide_store.get(article["id"])
        if cached and cached.get("guide"):
            return cached["guide"]
        llm = LLMService()
        guide = await llm.generate_intensive_guide(article["title"], article["body"])
        if guide and "error" not in guide:
            self.guide_store.set(article["id"], {"guide": guide, "generated_at": now_iso()})
        return guide

    async def score_summary(
        self, article: Dict[str, Any], key_points: List[str], summary: str
    ) -> Dict[str, Any]:
        llm = LLMService()
        return await llm.score_summary(article["title"], article["body"], key_points, summary)
