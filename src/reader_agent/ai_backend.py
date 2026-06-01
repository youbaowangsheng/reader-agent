"""AI backend adapters for Reader Agent business layer."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from urllib import error, request

from langchain_openai import ChatOpenAI


SYSTEM_PROMPT = """你是一个专业的学术阅读助手。请根据给定的英文论文/文献结构化内容，生成中文阅读笔记。

输出必须是完整 Markdown，严格包含以下章节：
1. # 《标题》阅读笔记
2. ## 一句话总结
3. ## 章节要点
4. ## 核心概念（表格）
5. ## 概念关系图（Mermaid）
6. ## 引用图谱（表格）
7. ## 批判性思考
8. ## 原文摘录（保留英文原句并标注页码/章节）

要求：
- 面向“英文论文阅读”场景，术语解释准确
- 结论必须以输入文档内容为依据，不要编造
- 核心概念不少于10条
- 批判性思考不少于3条
"""


class AIBackend(ABC):
    """Abstract AI backend capability."""

    @abstractmethod
    def generate_reading_note(self, parsed_doc: Dict[str, Any], source_path: str) -> str:
        """Generate note markdown from parsed document."""

    @abstractmethod
    def answer_with_citations(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]] | None = None,
        source_title: str = "",
        memory_facts: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Answer question with explicit citations."""


class DirectLLMBackend(AIBackend):
    """Direct OpenAI-compatible backend (legacy mode)."""

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

        self.llm = ChatOpenAI(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            temperature=0.3,
            max_tokens=8192,
        )

    def generate_reading_note(self, parsed_doc: Dict[str, Any], source_path: str) -> str:
        prompt = self._build_user_prompt(parsed_doc, source_path)
        resp = self.llm.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        return getattr(resp, "content", "") or ""

    def answer_with_citations(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]] | None = None,
        source_title: str = "",
        memory_facts: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        history_text = json.dumps(chat_history or [], ensure_ascii=False, indent=2)
        chunks_text = json.dumps(retrieved_chunks, ensure_ascii=False, indent=2)
        memory_text = json.dumps(memory_facts or [], ensure_ascii=False, indent=2)
        prompt = f"""你是英文论文阅读助手。请根据检索到的片段回答问题，不能编造。

source_title: {source_title}
question: {question}
chat_history: {history_text}
memory_facts: {memory_text}
retrieved_chunks: {chunks_text}

请只返回 JSON（不要 markdown）：
{{
  "answer": "中文回答，必要时保留英文术语",
  "citations": [
    {{
      "chunk_id": "doc_xxx_c0001",
      "quote": "引用的原文片段（尽量短）",
      "heading": "章节标题",
      "page_range": "页码范围或章节号"
    }}
  ],
  "facts": [
    {{
      "claim": "可复用的结论",
      "confidence": 0.0,
      "evidence": "证据简述",
      "citation_chunk_ids": ["doc_xxx_c0001"]
    }}
  ]
}}
"""
        resp = self.llm.invoke(
            [
                {"role": "system", "content": "你是严谨的学术问答助手。所有结论都要引用给定片段。"},
                {"role": "user", "content": prompt},
            ]
        )
        text = getattr(resp, "content", "") or ""
        parsed = _safe_json_from_text(text)
        answer = parsed.get("answer", "") if isinstance(parsed, dict) else ""
        citations = parsed.get("citations", []) if isinstance(parsed, dict) else []
        facts = parsed.get("facts", []) if isinstance(parsed, dict) else []
        return {"answer": answer or text, "citations": citations, "facts": facts}

    @staticmethod
    def _build_user_prompt(parsed_doc: Dict[str, Any], source_path: str) -> str:
        sections = parsed_doc.get("sections", [])
        trimmed_sections: List[Dict[str, Any]] = []
        for sec in sections[:20]:
            content = (sec.get("content") or "")[:4000]
            trimmed_sections.append(
                {
                    "heading": sec.get("heading", ""),
                    "content": content,
                    "page_range": sec.get("page_range", ""),
                    "chapter_index": sec.get("chapter_index", ""),
                }
            )
        compact_doc = {
            "title": parsed_doc.get("title"),
            "total_pages": parsed_doc.get("total_pages"),
            "total_chapters": parsed_doc.get("total_chapters"),
            "section_count": parsed_doc.get("section_count"),
            "sections": trimmed_sections,
        }
        return (
            f"source_path: {source_path}\n\n"
            "请基于以下结构化文档内容输出阅读笔记 Markdown：\n"
            f"{json.dumps(compact_doc, ensure_ascii=False, indent=2)}"
        )


class FIPAIBackend(AIBackend):
    """FIPAI platform backend via instance run API."""

    def __init__(self):
        self.base_url = os.getenv("FIPAI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        self.instance_id = os.getenv("FIPAI_INSTANCE_ID")
        if not self.instance_id:
            raise ValueError("FIPAI_INSTANCE_ID not set")
        self.bearer_token = os.getenv("FIPAI_BEARER_TOKEN", "")
        self.api_key = os.getenv("FIPAI_API_KEY", "")
        self.timeout = int(os.getenv("FIPAI_TIMEOUT_SEC", "120"))

    def generate_reading_note(self, parsed_doc: Dict[str, Any], source_path: str) -> str:
        payload = {
            "session_id": f"reader-agent-{self.instance_id}",
            "input": {
                "task": "generate_reading_note",
                "source_path": source_path,
                "document": parsed_doc,
                "system_prompt": SYSTEM_PROMPT,
            },
        }
        data = self._run(payload)
        output = self._pick_report(data.get("output"))
        note = self._extract_markdown(output)
        if not note:
            raise RuntimeError("FIPAI response does not contain note markdown")
        return note

    def answer_with_citations(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]] | None = None,
        source_title: str = "",
        memory_facts: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        payload = {
            "session_id": f"reader-agent-{self.instance_id}",
            "input": {
                "task": "answer_with_citations",
                "question": question,
                "source_title": source_title,
                "chat_history": chat_history or [],
                "memory_facts": memory_facts or [],
                "retrieved_chunks": retrieved_chunks,
            },
        }
        data = self._run(payload)
        output = self._pick_report(data.get("output"))
        answer, citations, facts = self._extract_answer_with_citations(output)
        if not answer:
            raise RuntimeError("FIPAI response does not contain answer text")
        return {"answer": answer, "citations": citations, "facts": facts}

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/instances/{self.instance_id}/run"
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        req = request.Request(
            url=url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"FIPAI request failed: HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"FIPAI request failed: {exc.reason}") from exc

        return json.loads(body)

    @staticmethod
    def _extract_markdown(output: Any) -> str:
        if isinstance(output, str):
            return output
        if not isinstance(output, dict):
            return ""

        candidates = [
            output.get("note_markdown"),
            output.get("final_markdown"),
            output.get("raw"),
            output.get("final"),
        ]
        for item in candidates:
            if isinstance(item, str) and item.strip():
                return item

        parsed = output.get("parsed")
        if isinstance(parsed, dict):
            for key in ("note_markdown", "markdown", "final_markdown"):
                val = parsed.get(key)
                if isinstance(val, str) and val.strip():
                    return val
        return ""

    @staticmethod
    def _extract_answer_with_citations(output: Any) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        if isinstance(output, str):
            parsed = _safe_json_from_text(output)
            if isinstance(parsed, dict):
                return (
                    str(parsed.get("answer", "")).strip(),
                    parsed.get("citations", []) or [],
                    parsed.get("facts", []) or [],
                )
            return output.strip(), [], []

        if not isinstance(output, dict):
            return "", [], []

        answer = ""
        for key in ("answer", "final_answer", "raw", "final"):
            if isinstance(output.get(key), str) and output[key].strip():
                answer = output[key].strip()
                break
        citations = output.get("citations", [])
        facts = output.get("facts", [])

        parsed = output.get("parsed")
        if isinstance(parsed, dict):
            if not answer:
                for key in ("answer", "final_answer", "markdown"):
                    val = parsed.get(key)
                    if isinstance(val, str) and val.strip():
                        answer = val.strip()
                        break
            if not citations and isinstance(parsed.get("citations"), list):
                citations = parsed.get("citations")
            if not facts and isinstance(parsed.get("facts"), list):
                facts = parsed.get("facts")

        if not isinstance(citations, list):
            citations = []
        if not isinstance(facts, list):
            facts = []
        return answer, citations, facts

    @staticmethod
    def _pick_report(output: Any) -> Any:
        if isinstance(output, dict) and "report" in output:
            return output.get("report")
        return output


def _safe_json_from_text(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    try:
        parsed = json.loads(raw.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return {}
    return {}


def build_ai_backend() -> AIBackend:
    """Factory for selecting AI backend by environment."""
    provider = os.getenv("AI_PROVIDER", "direct").strip().lower()
    if provider == "fipai":
        return FIPAIBackend()
    if provider == "direct":
        return DirectLLMBackend()
    raise ValueError(f"Unsupported AI_PROVIDER: {provider}")
