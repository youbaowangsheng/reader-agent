"""Reader-agent business service layer."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from reader_agent.ai_backend import build_ai_backend
from reader_agent.rag import (
    ConversationMemoryStore,
    detect_fact_conflicts,
    JsonVectorStore,
    RetrievedChunk,
    validate_citation_consistency,
)
from reader_agent.tools import parse_epub, parse_pdf, save_notes


@dataclass
class GenerationResult:
    source_path: Path
    note_path: Path
    index_path: Path
    title: str


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", (name or "").strip())
    cleaned = cleaned.replace("\n", " ").strip(" .")
    return cleaned[:120] or "Untitled"


def parse_source(source_path: Path) -> Dict[str, Any]:
    """Parse source file with format-aware parser."""
    if source_path.suffix.lower() == ".pdf":
        parsed = parse_pdf.func(str(source_path))
    elif source_path.suffix.lower() == ".epub":
        parsed = parse_epub.func(str(source_path))
    else:
        raise ValueError(f"Unsupported file type: {source_path.suffix}")
    return json.loads(parsed)


def generate_note_for_file(source_path: Path) -> GenerationResult:
    """Parse source document, build index, generate note, and persist mapping."""
    source_path = source_path.resolve()
    parsed_doc = parse_source(source_path)
    title = parsed_doc.get("title") or source_path.stem

    backend = build_ai_backend()
    markdown = backend.generate_reading_note(parsed_doc, str(source_path))
    filename = f"{_sanitize_filename(title)}_阅读笔记.md"
    message = save_notes.func(markdown_content=markdown, filename=filename)
    note_path = _extract_saved_path(message, fallback=Path(filename)).resolve()

    store = JsonVectorStore()
    index_path = store.build_index(source_path=source_path, parsed_doc=parsed_doc, note_path=note_path).resolve()
    store.register_note_mapping(source_path=source_path, note_path=note_path)

    return GenerationResult(
        source_path=source_path,
        note_path=note_path,
        index_path=index_path,
        title=str(title),
    )


def find_note_file(source_path: Path) -> Optional[Path]:
    """Find note file via strict manifest mapping first, fallback to exact stem match."""
    source_path = source_path.resolve()
    store = JsonVectorStore()
    mapped = store.find_note_for_source(source_path)
    if mapped:
        return mapped

    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    candidates = list(output_dir.glob("*_阅读笔记.md"))
    exact = [m for m in candidates if m.name.replace("_阅读笔记.md", "") == source_path.stem]
    return exact[0] if exact else None


def get_index_for_note(note_path: Path) -> Optional[Dict[str, Any]]:
    return JsonVectorStore().load_index_by_note(note_path.resolve())


def get_index_for_source(source_path: Path) -> Optional[Dict[str, Any]]:
    return JsonVectorStore().load_index_by_source(source_path.resolve())


def answer_question_with_rag(
    question: str,
    index_data: Dict[str, Any],
    chat_history: Optional[List[Dict[str, str]]] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """RAG query: retrieve chunks and ask backend for citation-grounded answer."""
    store = JsonVectorStore()
    retrieved = store.search(index_data=index_data, query=question, top_k=top_k)
    chunks_payload = [_retrieved_chunk_to_payload(c) for c in retrieved]
    doc_id = str(index_data.get("doc_id", ""))
    memory_store = ConversationMemoryStore()
    memory_facts = memory_store.recent_facts(doc_id=doc_id, limit=5) if doc_id else []
    backend = build_ai_backend()
    response = backend.answer_with_citations(
        question=question,
        retrieved_chunks=chunks_payload,
        chat_history=chat_history or [],
        source_title=str(index_data.get("title", "")),
        memory_facts=memory_facts,
    )
    response["citations"] = _enrich_citations(response.get("citations", []), retrieved)
    response["facts"] = _normalize_facts(response.get("facts", []), response.get("citations", []), response.get("answer", ""))
    response["fact_conflicts"] = detect_fact_conflicts(response.get("facts", []), memory_facts)

    min_citations = int(os.getenv("RAG_MIN_CITATIONS", "2"))
    consistent = validate_citation_consistency(
        response,
        retrieved,
        min_citations=min_citations,
        require_quote_overlap=True,
    )
    if not consistent:
        response = {
            "answer": "未能生成可靠引用。请重试或换一种提问方式。",
            "citations": [],
        }
    elif doc_id:
        memory_store.append_turn(
            doc_id=doc_id,
            question=question,
            answer=response.get("answer", ""),
            citations=response.get("citations", []),
            facts=response.get("facts", []),
        )

    return {
        "answer": response.get("answer", "").strip(),
        "citations": response.get("citations", []),
        "retrieved": [c.__dict__ for c in retrieved],
        "memory_used": memory_facts,
        "facts": response.get("facts", []),
        "fact_conflicts": response.get("fact_conflicts", []),
    }


def suggest_term_questions(note_markdown: str, limit: int = 8) -> List[str]:
    """Extract terms from markdown concept table and generate follow-up prompts."""
    terms: List[str] = []
    for line in note_markdown.splitlines():
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 2:
            continue
        left = cols[0]
        if left in ("术语", "------", "---") or set(left) <= {"-"}:
            continue
        if left and left not in terms:
            terms.append(left)
        if len(terms) >= limit:
            break
    return [f"这个术语在文中的定义和作用是什么：{t}？" for t in terms]


def get_recent_memory(index_data: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    doc_id = str(index_data.get("doc_id", ""))
    if not doc_id:
        return []
    return ConversationMemoryStore().recent_facts(doc_id=doc_id, limit=limit)


def clear_recent_memory(index_data: Dict[str, Any]) -> None:
    doc_id = str(index_data.get("doc_id", ""))
    if doc_id:
        ConversationMemoryStore().clear(doc_id)


def _retrieved_chunk_to_payload(c: RetrievedChunk) -> Dict[str, Any]:
    return {
        "chunk_id": c.chunk_id,
        "heading": c.heading,
        "page_range": c.page_range,
        "chapter_index": c.chapter_index,
        "text": c.text,
        "score": round(c.score, 6),
    }


def _enrich_citations(citations: List[Dict[str, Any]], retrieved: List[RetrievedChunk]) -> List[Dict[str, Any]]:
    by_id = {c.chunk_id: c for c in retrieved}
    rows: List[Dict[str, Any]] = []
    for c in citations:
        cid = str(c.get("chunk_id", "")).strip()
        hit = by_id.get(cid)
        if not hit:
            continue
        rows.append(
            {
                "chunk_id": cid,
                "quote": c.get("quote") or hit.text[:180],
                "heading": c.get("heading") or hit.heading,
                "page_range": c.get("page_range") or hit.page_range or (f"chapter {hit.chapter_index}" if hit.chapter_index else ""),
            }
        )
    return rows


def _extract_saved_path(message: str, fallback: Path) -> Path:
    match = re.search(r"Notes saved to:\s*(.+)$", message)
    if match:
        return Path(match.group(1).strip())
    return fallback


def _normalize_facts(facts: List[Dict[str, Any]], citations: List[Dict[str, Any]], answer: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for f in facts or []:
        claim = str(f.get("claim", "")).strip()
        if not claim:
            continue
        conf = f.get("confidence", 0.6)
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.6
        conf = max(0.0, min(1.0, conf))
        evidence = str(f.get("evidence", "")).strip()
        citation_ids = f.get("citation_chunk_ids", [])
        if not isinstance(citation_ids, list):
            citation_ids = []
        rows.append(
            {
                "claim": claim[:260],
                "confidence": round(conf, 2),
                "evidence": evidence[:240],
                "citation_chunk_ids": [str(x) for x in citation_ids[:4]],
            }
        )
    if rows:
        return rows[:5]

    fallback_ids = [c.get("chunk_id", "") for c in citations[:2] if c.get("chunk_id")]
    return [
        {
            "claim": (answer or "暂无可结构化结论")[:260],
            "confidence": 0.5,
            "evidence": "由回答自动回填",
            "citation_chunk_ids": fallback_ids,
        }
    ]
