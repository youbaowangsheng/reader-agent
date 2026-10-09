"""直接调用 LLM（OpenAI 兼容接口，默认 DeepSeek）生成 AI 导读。

后续若要接入 FIPAI 中台，可在此层替换为 FIPAI 调用，保持上层接口不变。
"""
import json
import httpx
from typing import Any, Dict, List

from config import get_settings

settings = get_settings()


class LLMService:
    """直接 LLM 客户端，提供 AI 导读等生成能力。"""

    def __init__(self):
        self.base_url = (settings.openai_base_url or "").rstrip("/")
        self.api_key = settings.openai_api_key
        self.model = settings.llm_chat_model
        self.timeout = settings.fipai_timeout_sec

    def _chat_url(self) -> str:
        base = self.base_url
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    async def _chat(
        self,
        messages: List[Dict[str, Any]],
        json_mode: bool = False,
        temperature: float = 0.4,
    ) -> str:
        """调用 chat completions，返回文本内容。"""
        url = self._chat_url()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_reading_guide(
        self, parsed_doc: Dict[str, Any], source_path: str = ""
    ) -> Dict[str, Any]:
        """生成结构化 AI 导读（reading_plan/summary/trail/verdict/quiz）。"""
        sections = parsed_doc.get("sections", []) if isinstance(parsed_doc, dict) else []
        trimmed_sections = []
        for sec in sections[:30]:
            trimmed_sections.append({
                "heading": sec.get("heading", ""),
                "level": sec.get("level", 1),
                "page_range": sec.get("page_range", ""),
                "paragraphs": [
                    {"page": p.get("page"), "text": str(p.get("text", ""))[:600]}
                    for p in (sec.get("paragraphs") or [])[:10]
                ],
            })

        payload = {
            "title": parsed_doc.get("title", ""),
            "total_pages": parsed_doc.get("total_pages"),
            "section_count": parsed_doc.get("section_count"),
            "sections": trimmed_sections,
        }

        system_prompt = (
            "你是严谨的学术导读助手。通读论文后产出结构化「AI导读」。要求：\n"
            "1. reading_plan：精读2-4处(careful)、略读若干(skim)、重点盯3-5点(focus)\n"
            "2. summary：一句话总结\n"
            "3. trail：5-8处停顿，按阅读顺序；每处有 where/type/says/anchor；"
            "says 用第一人称、口语化、有态度（如「我存疑」「最巧的一笔」「要打个折」）；"
            "anchor.highlight 必须逐字引用原文 paragraphs 里的真实句子（防幻觉）\n"
            "4. verdict：text + stars(1-5)\n"
            "5. quiz：3-5道选择题，按论文长度/难度自适应；每题 q/options/answer/explain\n"
            "只输出 JSON，不要任何 markdown 包裹。"
        )

        user_prompt = (
            f"source_path: {source_path}\n\n"
            "请根据以下结构化内容生成 AI 导读（严格 JSON）：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "输出 JSON 结构：\n"
            "{\n"
            '  "reading_plan": {"careful": [{"ref":"§3","label":"...","note":"...","anchor":{"page":4,"section_index":2,"highlight":"原文句子"}}], "skim": [{"ref":"§2","label":"...","anchor":{"page":3,"section_index":1}}], "focus": ["①...","②..."]},\n'
            '  "summary": "一句话总结",\n'
            '  "trail": [{"where":"ABSTRACT","type":"location|thought|question|fig","says":"...","anchor":{"page":1,"section_index":0,"highlight":"原文句子"}}],\n'
            '  "verdict": {"text":"...","stars":4},\n'
            '  "quiz": [{"q":"...","options":["A..","B..","C..","D.."],"answer":"B","explain":"..."}]\n'
            "}\n"
            "注意：anchor 的 page 和 highlight 必须来自上面 sections 里的真实页码和真实段落文本。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        content = await self._chat(messages, json_mode=True, temperature=0.4)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"error": "生成导读失败", "raw": content[:500]}


def get_llm_service() -> LLMService:
    return LLMService()
