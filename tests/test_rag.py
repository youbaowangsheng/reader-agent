from pathlib import Path

from reader_agent.rag import (
    ConversationMemoryStore,
    JsonVectorStore,
    detect_fact_conflicts,
    validate_citation_consistency,
)


def _sample_doc():
    return {
        "title": "Sample Paper",
        "sections": [
            {
                "heading": "Introduction",
                "content": "Large language models can read papers. This section defines goals and background.",
                "page_range": "1-1",
            },
            {
                "heading": "Method",
                "content": "We chunk text, build embeddings, and retrieve top relevant passages with cosine similarity.",
                "page_range": "2-3",
            },
        ],
    }


def test_build_index_and_search(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    store = JsonVectorStore()
    source_path = tmp_path / "paper.pdf"
    source_path.write_text("dummy", encoding="utf-8")
    index_path = store.build_index(source_path=source_path, parsed_doc=_sample_doc())
    assert index_path.exists()

    loaded = store.load_index_by_source(source_path)
    assert loaded is not None
    assert loaded["chunk_count"] > 0

    hits = store.search(loaded, "how retrieval works", top_k=3)
    assert len(hits) >= 1
    assert hits[0].chunk_id
    assert isinstance(hits[0].score, float)


def test_manifest_mapping_and_lookup(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    store = JsonVectorStore()
    source_path = tmp_path / "a.pdf"
    note_path = tmp_path / "a_阅读笔记.md"
    source_path.write_text("x", encoding="utf-8")
    note_path.write_text("# note", encoding="utf-8")

    store.build_index(source_path=source_path, parsed_doc=_sample_doc(), note_path=note_path)
    mapped = store.find_note_for_source(source_path)
    assert mapped == note_path.resolve()


def test_citation_consistency(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    store = JsonVectorStore()
    source_path = tmp_path / "b.pdf"
    source_path.write_text("x", encoding="utf-8")
    index = store.build_index(source_path=source_path, parsed_doc=_sample_doc())
    loaded = store.load_index_by_source(source_path)
    hits = store.search(loaded, "chunk embeddings", top_k=2)

    ok_answer = {
        "answer": "test",
        "citations": [
            {"chunk_id": hits[0].chunk_id, "quote": hits[0].text[:40]},
            {"chunk_id": hits[1].chunk_id, "quote": hits[1].text[:40]},
        ],
    }
    bad_answer_missing = {"answer": "test", "citations": [{"chunk_id": "not_exist", "quote": "x"}]}
    bad_answer_single = {"answer": "test", "citations": [{"chunk_id": hits[0].chunk_id, "quote": hits[0].text[:40]}]}
    bad_answer_quote = {
        "answer": "test",
        "citations": [
            {"chunk_id": hits[0].chunk_id, "quote": "completely unrelated words"},
            {"chunk_id": hits[1].chunk_id, "quote": hits[1].text[:40]},
        ],
    }
    assert validate_citation_consistency(ok_answer, hits) is True
    assert validate_citation_consistency(bad_answer_missing, hits) is False
    assert validate_citation_consistency(bad_answer_single, hits) is False
    assert validate_citation_consistency(bad_answer_quote, hits) is False


def test_memory_store(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    store = ConversationMemoryStore()
    doc_id = "doc_test123"

    store.append_turn(
        doc_id=doc_id,
        question="q1",
        answer="a1",
        citations=[{"chunk_id": "c1", "quote": "text one", "heading": "h", "page_range": "1-1"}],
        facts=[{"claim": "fact1", "confidence": 0.8, "evidence": "e1"}],
    )
    store.append_turn(
        doc_id=doc_id,
        question="q2",
        answer="a2",
        citations=[{"chunk_id": "c2", "quote": "text two", "heading": "h2", "page_range": "2-2"}],
        facts=[{"claim": "fact2", "confidence": 0.7, "evidence": "e2"}],
    )

    facts = store.recent_facts(doc_id, limit=2)
    assert len(facts) == 2
    assert facts[-1]["claim"] == "fact2"
    assert facts[-1]["confidence"] == 0.7
    assert facts[-1]["citations"][0]["chunk_id"] == "c2"

    store.clear(doc_id)
    assert store.recent_facts(doc_id, limit=2) == []


def test_fact_conflict_detection():
    memory = [{"claim": "The method does not improve recall under noisy settings."}]
    new_facts = [{"claim": "The method improves recall under noisy settings."}]
    conflicts = detect_fact_conflicts(new_facts, memory)
    assert len(conflicts) >= 1
    assert conflicts[0]["reason"] == "polarity_mismatch"
