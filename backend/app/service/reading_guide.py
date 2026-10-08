from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.paper import Paper
from app.service.fipai import FIPAIService


class ReadingGuideService:
    """AI 导读服务：生成 / 规范化 / 存储 / 重新生成 / 导出。"""

    def __init__(self, db: AsyncSession, fipai: FIPAIService):
        self.db = db
        self.fipai = fipai

    # ---- 导读生成 ----

    async def generate(self, paper: Paper, force: bool = False) -> Dict[str, Any]:
        """生成（或重新生成）导读产物，存回 paper.reading_guide。"""
        guide = paper.reading_guide or {}
        if guide.get("status") == "generated" and not force:
            return guide

        parsed_doc = paper.parsed_structure or {}
        if not parsed_doc.get("sections"):
            raise ValueError("论文尚未解析完成，无法生成导读。")

        # 标记生成中
        paper.reading_guide = {"status": "generating", "version": 1}
        await self.db.commit()

        # 调用 FIPAI 生成
        raw = await self.fipai.generate_reading_guide(
            parsed_doc=parsed_doc,
            source_path=paper.file_url or "",
        )

        # 规范化 + 锚点校验
        guide = self._normalize(raw, parsed_doc)
        paper.reading_guide = guide
        await self.db.commit()
        await self.db.refresh(paper)
        return paper.reading_guide

    def _normalize(self, raw: Dict[str, Any], parsed_doc: Dict[str, Any]) -> Dict[str, Any]:
        """规范化导读结构，校验锚点 page 范围、补全 highlight。"""
        raw = raw or {}
        total_pages = int(parsed_doc.get("total_pages") or 1)
        sections = parsed_doc.get("sections") or []

        reading_plan = raw.get("reading_plan") or {}
        trail = raw.get("trail") or []
        quiz = raw.get("quiz") or []

        normalized_trail: List[Dict[str, Any]] = []
        for i, t in enumerate(trail):
            anchor = t.get("anchor") or {}
            page = self._clamp_page(anchor.get("page"), total_pages)
            highlight = anchor.get("highlight") or ""
            if not highlight:
                highlight = self._extract_highlight(sections, anchor.get("section_index"))
            normalized_trail.append({
                "id": t.get("id") or f"t{i + 1}",
                "where": t.get("where", ""),
                "type": t.get("type", "location"),
                "says": t.get("says", ""),
                "anchor": {
                    "page": page,
                    "section_index": anchor.get("section_index"),
                    "highlight": highlight,
                },
            })

        return {
            "status": "generated",
            "version": 1,
            "reading_plan": {
                "careful": reading_plan.get("careful") or [],
                "skim": reading_plan.get("skim") or [],
                "focus": reading_plan.get("focus") or [],
            },
            "summary": raw.get("summary", ""),
            "trail": normalized_trail,
            "verdict": raw.get("verdict") or {"text": "", "stars": 0},
            "quiz": quiz,
        }

    @staticmethod
    def _clamp_page(page, total_pages: int) -> int:
        try:
            p = int(page)
        except (TypeError, ValueError):
            return 1
        return max(1, min(p, total_pages))

    @staticmethod
    def _extract_highlight(sections: List[Dict], section_index) -> str:
        """从 section 提取锚点高亮句（FIPAI 未给 highlight 时兜底）。"""
        try:
            si = int(section_index)
            sec = sections[si]
        except (TypeError, ValueError, IndexError):
            return ""
        paras = sec.get("paragraphs") or []
        if paras:
            return paras[0].get("text", "")[:200]
        return (sec.get("content") or "")[:200]

    # ---- 用户交互 ----

    async def get_engagement(self, paper: Paper) -> Dict[str, Any]:
        return paper.user_engagement or {}

    async def save_engagement(self, paper: Paper, patch_data: Dict[str, Any]) -> Dict[str, Any]:
        """部分更新用户交互（浅合并）。"""
        current = dict(paper.user_engagement or {})
        current.update(patch_data or {})
        paper.user_engagement = current
        await self.db.commit()
        await self.db.refresh(paper)
        return paper.user_engagement

    def export_engagement(self, paper: Paper) -> str:
        """导出「认同观点 + 我的看法 + 整体观点」为 Markdown。"""
        eng = paper.user_engagement or {}
        guide = paper.reading_guide or {}
        meta = paper.paper_metadata or {}
        title = meta.get("title") or paper.filename

        lines: List[str] = [f"# 我的阅读观点 · {title}", ""]

        judgments = eng.get("judgments") or {}
        notes = eng.get("notes") or {}
        trail = guide.get("trail") or []

        # 认同的观点
        agreed = [t for t in trail if judgments.get(t.get("id")) == "agree"]
        if agreed:
            lines.append("## ✅ 我认同的观点")
            for t in agreed:
                lines.append(f"- {t.get('says', '')}")
            lines.append("")

        # 我的看法（每条停顿）
        if notes:
            lines.append("## 💬 我的看法")
            for tid, note in notes.items():
                where = next((t.get("where", "") for t in trail if t.get("id") == tid), tid)
                lines.append(f"- **{where}**：{note}")
            lines.append("")

        # 整体观点
        my_view = eng.get("my_view") or ""
        if my_view:
            lines.append("## 📝 我的整体观点")
            lines.append(my_view)
            lines.append("")

        if not (agreed or notes or my_view):
            lines.append("（暂无内容 —— 先对导读轨迹做判断、写下你的看法和整体观点。）")

        return "\n".join(lines).strip()
