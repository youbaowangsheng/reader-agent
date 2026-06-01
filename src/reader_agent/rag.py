"""RAG utilities: chunking, embeddings, vector store, and citation metadata."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _output_dir() -> Path:
    return Path(os.getenv("OUTPUT_DIR", "./output")).resolve()


def _rag_dir() -> Path:
    path = _output_dir() / ".rag"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path() -> Path:
    return _rag_dir() / "manifest.json"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", (text or "").lower())


def _chunk_text(text: str, max_chars: int = 900, overlap_chars: int = 150) -> List[str]:
    text = _normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += step
    return [c for c in chunks if c]


def hash_embed(text: str, dim: int = 384) -> List[float]:
    """Deterministic lightweight embedding using token hashing."""
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if (h[4] % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _doc_id_for_path(source_path: Path) -> str:
    key = str(source_path.resolve())
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float
    heading: str
    page_range: str
    chapter_index: Optional[int]
    text: str


class JsonVectorStore:
    """JSON-based vector store for a single-document retrieval flow."""

    def __init__(self):
        self.base = _rag_dir()

    def build_index(self, source_path: Path, parsed_doc: Dict[str, Any], note_path: Optional[Path] = None) -> Path:
        source_path = source_path.resolve()
        doc_id = _doc_id_for_path(source_path)
        title = parsed_doc.get("title") or source_path.stem
        rows: List[Dict[str, Any]] = []

        chunk_seq = 0
        for sec in parsed_doc.get("sections", []):
            heading = (sec.get("heading") or "Section").strip()
            page_range = str(sec.get("page_range") or "")
            chapter_index = sec.get("chapter_index")
            for part in _chunk_text(sec.get("content") or ""):
                chunk_seq += 1
                chunk_id = f"{doc_id}_c{chunk_seq:04d}"
                rows.append(
                    {
                        "chunk_id": chunk_id,
                        "heading": heading,
                        "page_range": page_range,
                        "chapter_index": chapter_index,
                        "text": part,
                        "embedding": hash_embed(part),
                    }
                )

        data = {
            "doc_id": doc_id,
            "title": title,
            "source_path": str(source_path),
            "note_path": str(note_path.resolve()) if note_path else "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(rows),
            "chunks": rows,
        }
        index_path = self.base / f"{doc_id}.json"
        index_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self._upsert_manifest(source_path=source_path, note_path=note_path, index_path=index_path)
        return index_path

    def load_index_by_source(self, source_path: Path) -> Optional[Dict[str, Any]]:
        doc_id = _doc_id_for_path(source_path.resolve())
        path = self.base / f"{doc_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_index_by_note(self, note_path: Path) -> Optional[Dict[str, Any]]:
        manifest = self._load_manifest()
        note_abs = str(note_path.resolve())
        for row in manifest.get("documents", []):
            if row.get("note_path") == note_abs:
                p = Path(row.get("index_path", ""))
                if p.exists():
                    return json.loads(p.read_text(encoding="utf-8"))
        return None

    def find_note_for_source(self, source_path: Path) -> Optional[Path]:
        manifest = self._load_manifest()
        source_abs = str(source_path.resolve())
        for row in manifest.get("documents", []):
            if row.get("source_path") == source_abs and row.get("note_path"):
                p = Path(row["note_path"])
                if p.exists():
                    return p
        return None

    def register_note_mapping(self, source_path: Path, note_path: Path) -> None:
        source_path = source_path.resolve()
        note_path = note_path.resolve()
        doc_id = _doc_id_for_path(source_path)
        index_path = self.base / f"{doc_id}.json"
        self._upsert_manifest(source_path=source_path, note_path=note_path, index_path=index_path)

        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8"))
            data["note_path"] = str(note_path)
            index_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def search(self, index_data: Dict[str, Any], query: str, top_k: int = 5) -> List[RetrievedChunk]:
        qv = hash_embed(query)
        scored: List[RetrievedChunk] = []

        for row in index_data.get("chunks", []):
            score = cosine_similarity(qv, row.get("embedding", []))
            scored.append(
                RetrievedChunk(
                    chunk_id=row.get("chunk_id", ""),
                    score=score,
                    heading=row.get("heading", ""),
                    page_range=row.get("page_range", ""),
                    chapter_index=row.get("chapter_index"),
                    text=row.get("text", ""),
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[: max(1, top_k)]

    def _load_manifest(self) -> Dict[str, Any]:
        path = _manifest_path()
        if not path.exists():
            return {"documents": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"documents": []}

    def _upsert_manifest(self, source_path: Path, note_path: Optional[Path], index_path: Path) -> None:
        manifest = self._load_manifest()
        source_abs = str(source_path.resolve())
        note_abs = str(note_path.resolve()) if note_path else ""
        index_abs = str(index_path.resolve())

        docs = manifest.get("documents", [])
        replaced = False
        for row in docs:
            if row.get("source_path") == source_abs:
                row["note_path"] = note_abs or row.get("note_path", "")
                row["index_path"] = index_abs
                row["updated_at"] = datetime.now(timezone.utc).isoformat()
                replaced = True
                break
        if not replaced:
            docs.append(
                {
                    "source_path": source_abs,
                    "note_path": note_abs,
                    "index_path": index_abs,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        manifest["documents"] = docs
        _manifest_path().write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


class ConversationMemoryStore:
    """Per-document conversation memory persisted to JSON."""

    def __init__(self):
        self.base = _rag_dir()

    def load(self, doc_id: str) -> Dict[str, Any]:
        path = self._path(doc_id)
        if not path.exists():
            return {"doc_id": doc_id, "turns": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"doc_id": doc_id, "turns": []}

    def append_turn(
        self,
        doc_id: str,
        question: str,
        answer: str,
        citations: List[Dict[str, Any]],
        facts: List[Dict[str, Any]],
    ) -> None:
        data = self.load(doc_id)
        turns = data.get("turns", [])
        turns.append(
            {
                "question": question.strip(),
                "answer": answer.strip(),
                "citations": citations,
                "facts": facts,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["turns"] = turns[-50:]
        self._path(doc_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def recent_facts(self, doc_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        data = self.load(doc_id)
        turns = data.get("turns", [])
        rows: List[Dict[str, Any]] = []
        for row in turns[-limit:]:
            fact_cards = row.get("facts", [])
            if isinstance(fact_cards, list) and fact_cards:
                for f in fact_cards[:3]:
                    rows.append(
                        {
                            "claim": f.get("claim", "")[:260],
                            "confidence": f.get("confidence", 0.0),
                            "evidence": f.get("evidence", "")[:240],
                            "citations": row.get("citations", [])[:3],
                        }
                    )
            else:
                rows.append(
                    {
                        "claim": row.get("answer", "")[:260],
                        "confidence": 0.5,
                        "evidence": "由回答自动回填",
                        "citations": row.get("citations", [])[:3],
                    }
                )
        return rows

    def clear(self, doc_id: str) -> None:
        p = self._path(doc_id)
        if p.exists():
            p.unlink()

    def _path(self, doc_id: str) -> Path:
        return self.base / f"{doc_id}_memory.json"


def _quote_overlaps(text: str, quote: str) -> bool:
    source = _normalize_text(text).lower()
    q = _normalize_text(quote).lower()
    if not source or not q:
        return False
    if len(q) < 12:
        return q in source
    if q in source:
        return True
    # fallback: partial token overlap for lightly transformed quotes
    source_tokens = set(_tokenize(source))
    quote_tokens = set(_tokenize(q))
    if not source_tokens or not quote_tokens:
        return False
    overlap = len(source_tokens & quote_tokens) / max(1, len(quote_tokens))
    return overlap >= 0.6


def validate_citation_consistency(
    answer: Dict[str, Any],
    retrieved: List[RetrievedChunk],
    min_citations: int = 2,
    require_quote_overlap: bool = True,
) -> bool:
    """Consistency check: citation count + chunk match + quote overlap."""
    valid_ids = {c.chunk_id for c in retrieved}
    by_id = {c.chunk_id: c for c in retrieved}
    citations = answer.get("citations", []) if isinstance(answer, dict) else []
    if not citations or len(citations) < max(1, min_citations):
        return False

    for c in citations:
        cid = str(c.get("chunk_id", "")).strip()
        if not cid or cid not in valid_ids:
            return False
        if require_quote_overlap:
            quote = str(c.get("quote", "")).strip()
            if not quote:
                return False
            if not _quote_overlaps(by_id[cid].text, quote):
                return False
    return True


def detect_fact_conflicts(new_facts: List[Dict[str, Any]], memory_facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect simple semantic conflicts between new and remembered fact cards."""
    conflicts: List[Dict[str, Any]] = []
    if not new_facts or not memory_facts:
        return conflicts

    for nf in new_facts:
        new_claim = _normalize_text(str(nf.get("claim", "")))
        if len(new_claim) < 8:
            continue
        new_tokens = set(_tokenize(new_claim))
        if not new_tokens:
            continue
        new_neg = _has_negation(new_claim)

        for mf in memory_facts:
            old_claim = _normalize_text(str(mf.get("claim", "")))
            if len(old_claim) < 8:
                continue
            old_tokens = set(_tokenize(old_claim))
            if not old_tokens:
                continue
            overlap = len(new_tokens & old_tokens) / max(1, min(len(new_tokens), len(old_tokens)))
            old_neg = _has_negation(old_claim)

            if overlap >= 0.7 and new_neg != old_neg:
                conflicts.append(
                    {
                        "new_claim": new_claim[:260],
                        "old_claim": old_claim[:260],
                        "overlap": round(overlap, 2),
                        "reason": "polarity_mismatch",
                    }
                )
    return conflicts[:6]


def _has_negation(text: str) -> bool:
    t = text.lower()
    markers = [
        " not ",
        " no ",
        " never ",
        " cannot ",
        " can't ",
        " without ",
        " 无",
        "不",
        "非",
        "没有",
        "并非",
    ]
    padded = f" {t} "
    return any(m in padded for m in markers)
