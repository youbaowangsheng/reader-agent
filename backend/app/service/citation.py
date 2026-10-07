import re
from typing import Any, Dict, List


def quote_overlaps(text: str, quote: str) -> bool:
    source = re.sub(r"\s+", " ", (text or "")).strip().lower()
    q = re.sub(r"\s+", " ", (quote or "")).strip().lower()
    if not source or not q:
        return False
    if len(q) < 12:
        return q in source
    if q in source:
        return True
    src_tokens = set(re.findall(r"[A-Za-z0-9_]+|[一-鿿]", source))
    q_tokens = set(re.findall(r"[A-Za-z0-9_]+|[一-鿿]", q))
    if not src_tokens or not q_tokens:
        return False
    overlap = len(src_tokens & q_tokens) / max(1, len(q_tokens))
    return overlap >= 0.6


def validate_citations(
    citations: List[Dict[str, Any]],
    retrieved_map: Dict[str, str],
    min_required: int = 2,
) -> bool:
    if len(citations) < max(1, int(min_required)):
        return False
    for c in citations:
        cid = str(c.get("chunk_id", "")).strip()
        quote = str(c.get("quote", "")).strip()
        if not cid or cid not in retrieved_map:
            return False
        if not quote:
            return False
        if not quote_overlaps(retrieved_map[cid], quote):
            return False
    return True
