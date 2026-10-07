import httpx
import json
import os
from typing import Any, Dict, List, Optional

from config import get_settings

settings = get_settings()


class FIPAIService:
    """Async FIPAI client for all AI tasks."""

    def __init__(self):
        self.base_url = settings.fipai_base_url.rstrip("/")
        self.instance_id = settings.fipai_instance_id
        self.bearer_token = settings.fipai_bearer_token
        self.api_key = settings.fipai_api_key
        self.timeout = settings.fipai_timeout_sec

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/instances/{self.instance_id}/run"
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def generate_reading_note(self, parsed_doc: Dict[str, Any], source_path: str) -> str:
        """Generate structured reading note markdown."""
        payload = {
            "session_id": f"reader-agent-{self.instance_id}",
            "input": {
                "task": "generate_reading_note",
                "source_path": source_path,
                "document": parsed_doc,
            },
        }
        data = await self._run(payload)
        output = self._pick_report(data.get("output"))
        return self._extract_markdown(output)

    async def answer_with_citations(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]],
        source_title: str = "",
        memory_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Answer question with explicit citations."""
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
        data = await self._run(payload)
        output = self._pick_report(data.get("output"))
        answer, citations, facts = self._extract_answer_with_citations(output)
        if not answer:
            raise RuntimeError("FIPAI response does not contain answer text")
        return {"answer": answer, "citations": citations, "facts": facts}

    async def generate_summary(
        self,
        parsed_doc: Dict[str, Any],
        tier: str = "2m",
    ) -> Dict[str, Any]:
        """Generate tiered summary: 10s, 2m, or 10m."""
        task_map = {
            "10s": "generate_summary_10s",
            "2m": "generate_summary_2m",
            "10m": "generate_summary_10m",
        }
        task = task_map.get(tier, "generate_summary_2m")
        payload = {
            "session_id": f"reader-agent-{self.instance_id}",
            "input": {
                "task": task,
                "document": parsed_doc,
            },
        }
        data = await self._run(payload)
        output = self._pick_report(data.get("output"))
        return {"summary": self._extract_markdown(output) or str(output)}

    async def extract_fact_card(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract a fact card from text."""
        payload = {
            "session_id": f"reader-agent-{self.instance_id}",
            "input": {
                "task": "extract_fact_card",
                "text": text,
                "context": context or {},
            },
        }
        data = await self._run(payload)
        output = self._pick_report(data.get("output"))
        return self._safe_json_from_text(str(output) if isinstance(output, str) else output)

    async def evaluate_paper(self, parsed_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall evaluation (novelty, rigor, reproducibility, pros, cons)."""
        payload = {
            "session_id": f"reader-agent-{self.instance_id}",
            "input": {
                "task": "evaluate_paper",
                "document": parsed_doc,
            },
        }
        data = await self._run(payload)
        output = self._pick_report(data.get("output"))
        return self._safe_json_from_text(str(output) if isinstance(output, str) else output)

    @staticmethod
    def _pick_report(output: Any) -> Any:
        if isinstance(output, dict) and "report" in output:
            return output.get("report")
        return output

    @staticmethod
    def _extract_markdown(output: Any) -> str:
        if isinstance(output, str):
            return output
        if not isinstance(output, dict):
            return ""

        candidates = [
            output.get("note_markdown"),
            output.get("final_markdown"),
            output.get("markdown"),
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
    def _extract_answer_with_citations(output: Any) -> tuple:
        if isinstance(output, str):
            parsed = FIPAIService._safe_json_from_text(output)
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


def get_fipai_service() -> FIPAIService:
    return FIPAIService()