"""直接调用 LLM（OpenAI 兼容接口，默认 DeepSeek）生成 AI 导读。

后续若要接入 FIPAI 中台，可在此层替换为 FIPAI 调用，保持上层接口不变。
"""
import json
import httpx
from typing import Any, Dict, List, Optional

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
        max_tokens: Optional[int] = None,
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
        if max_tokens:
            payload["max_tokens"] = max_tokens
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

    async def generate_intensive_guide(self, title: str, body: str) -> Dict[str, Any]:
        """生成精读带读（逐段生词/长难句/背景/观点 + 概要写作任务）。"""
        system_prompt = (
            "你是高中英语精读教练。给一篇英文外刊文章生成「AI 带读」，帮助高中生提升精读能力。\n"
            "要求（务必精简，控制输出长度）：\n"
            "1. overview：一句话中文概述（40字内）\n"
            "2. paragraphs：把文章合并成 5-8 段（每段约 100-150 词），逐段带读。每段提取：\n"
            "   - text：本段原文（英文，从原文完整摘录，不要改写或截断）\n"
            "   - vocab：重点生词 2-3 个（只挑最关键的），每个含 word/pos/meaning（中文）/example（英文短句）\n"
            "   - long_sentences：长难句 0-1 个，每个含 text（原文）+ analysis（简短中文拆解）\n"
            "   - context：本段背景知识（中文，一句话，没有就省略）\n"
            "   - idea：本段核心观点（中文，一句话）\n"
            "3. writing_task：读后概要写作任务\n"
            "   - instruction：用 60-100 词概括全文\n"
            "   - key_points：评分要点 3-4 个（中文）\n"
            "只输出 JSON，不要任何 markdown 包裹，不要输出正文。"
        )
        user_prompt = (
            f"文章标题：{title}\n\n文章正文：\n{body}\n\n请输出 JSON：\n"
            + json.dumps({
                "overview": "...",
                "paragraphs": [{
                    "idx": 1,
                    "text": "...",
                    "vocab": [{"word": "...", "ipa": "...", "pos": "n.", "meaning": "...", "example": "..."}],
                    "long_sentences": [{"text": "...", "analysis": "..."}],
                    "context": "...",
                    "idea": "...",
                }],
                "writing_task": {"type": "summary", "instruction": "...", "key_points": ["..."]},
            }, ensure_ascii=False, indent=2)
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self._chat(messages, json_mode=True, temperature=0.4, max_tokens=8192)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"error": "生成精读带读失败", "raw": content[:500]}

    async def score_summary(
        self, title: str, body: str, key_points: List[str], summary: str
    ) -> Dict[str, Any]:
        """评分概要写作（要点覆盖/语言准确/连贯性）。"""
        system_prompt = (
            "你是高中英语老师。给学生的概要写作评分。\n"
            "评分维度：要点覆盖、语言准确性、连贯性。\n"
            "只输出 JSON：{\"score\": 总分(0-100), \"coverage\": 要点覆盖分(0-100), "
            "\"language\": 语言分(0-100), \"coherence\": 连贯分(0-100), "
            "\"comment\": 中文点评, \"suggestions\": [改进建议(中文)]}"
        )
        user_prompt = (
            f"文章标题：{title}\n\n文章正文（前1500词）：\n{body[:1500]}\n\n"
            f"评分要点：{json.dumps(key_points, ensure_ascii=False)}\n\n"
            f"学生概要：\n{summary}\n\n请评分。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self._chat(messages, json_mode=True, temperature=0.3)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"error": "评分失败", "raw": content[:500]}

    async def generate_extensive_guide(self, title: str, body: str) -> Dict[str, Any]:
        """生成泛读材料（150-300 词节选 + 大意检测题）。"""
        system_prompt = (
            "你是高中英语泛读教练。给一篇英文长文生成「泛读材料」，帮助学生练习快速阅读、抓大意。\n"
            "任务：\n"
            "1. passage：从长文里提取一个 150-300 词的「连续节选」（必须逐字摘取原文，不修改、不重写，保持段落完整，优先选最能代表文章主旨的开头段落）\n"
            "2. questions：2-3 道开放式大意检测题，考察主旨和关键信息（英文提问）\n"
            "3. 每道题的 answer：参考答案（英文）\n"
            "只输出 JSON，不要 markdown。"
        )
        user_prompt = (
            f"文章标题：{title}\n\n文章正文：\n{body[:6000]}\n\n请输出 JSON：\n"
            + json.dumps({
                "passage": "150-300词的原文节选",
                "questions": [
                    {"q": "What is the passage mainly about?", "answer": "..."},
                    {"q": "What key details does the passage mention?", "answer": "..."},
                ],
            }, ensure_ascii=False, indent=2)
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
        return {"error": "生成泛读材料失败", "raw": content[:500]}

    async def score_extensive(
        self, title: str, passage: str, questions: List[Dict[str, Any]], answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """评分泛读大意检测：判断学生回答 + 参考答案 + 中文反馈。"""
        system_prompt = (
            "你是高中英语泛读教练。判断学生的泛读大意回答是否正确，给参考答案和中文反馈。\n"
            "只输出 JSON：{\"results\": [{\"q\":\"问题\", \"correct\": true/false, "
            "\"reference\":\"参考答案\", \"feedback\":\"中文反馈\"}], \"overall\":\"总评(中文)\"}"
        )
        user_prompt = (
            f"文章标题：{title}\n\n泛读节选：\n{passage}\n\n"
            f"问题与参考答案：\n{json.dumps(questions, ensure_ascii=False)}\n\n"
            f"学生回答：\n{json.dumps(answers, ensure_ascii=False)}\n\n"
            "请判断每个回答是否正确，给参考答案和中文反馈。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self._chat(messages, json_mode=True, temperature=0.3)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"error": "泛读评分失败", "raw": content[:500]}

    async def generate_extensive_questions(self, title: str, body: str) -> Dict[str, Any]:
        """针对泛读短文生成大意检测题（短文即全文，不提取节选）。"""
        system_prompt = (
            "你是高中英语泛读教练。针对一篇英文短文生成大意检测题，帮助学生练习快速阅读、抓大意。\n"
            "任务：\n"
            "1. questions：2-3 道开放式大意检测题，考察文章主旨和关键信息（英文提问，问题简短）\n"
            "2. 每道题的 answer：参考答案（英文，一句话）\n"
            "只输出 JSON，不要 markdown。"
        )
        user_prompt = (
            f"文章标题：{title}\n\n文章正文：\n{body}\n\n请输出 JSON：\n"
            + json.dumps({
                "questions": [
                    {"q": "What is the article mainly about?", "answer": "..."},
                    {"q": "What key details does the article mention?", "answer": "..."},
                ],
            }, ensure_ascii=False, indent=2)
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
        return {"error": "生成大意检测题失败", "raw": content[:500]}


def get_llm_service() -> LLMService:
    return LLMService()
