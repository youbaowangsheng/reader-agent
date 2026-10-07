from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.paper import Paper, PaperNote
from app.model.paper_chunk import PaperChunk
from app.service.fipai import FIPAIService
from app.service.rag import RAGService, chunk_text
from app.service.citation import validate_citations
from config import get_settings

settings = get_settings()


class NoteService:
    """Service for generating and managing paper notes."""

    def __init__(self, db: AsyncSession, fipai: FIPAIService):
        self.db = db
        self.fipai = fipai

    async def get_note(self, paper_id: UUID) -> Optional[PaperNote]:
        """Get paper note by paper ID."""
        stmt = select(PaperNote).where(PaperNote.paper_id == paper_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def generate_note(self, paper: Paper, force: bool = False) -> PaperNote:
        """Generate or update paper note."""
        existing = await self.get_note(paper.id)
        if existing and not force:
            return existing

        # Get parsed structure
        parsed_doc = paper.parsed_structure
        if not parsed_doc:
            raise ValueError("Paper has no parsed structure. Parse document first.")

        # Generate note via FIPAI
        markdown = await self.fipai.generate_reading_note(
            parsed_doc=parsed_doc,
            source_path=paper.file_url,
        )

        # Parse markdown to extract structured data
        structured = self._parse_note_markdown(markdown)

        # Create or update note
        if existing:
            existing.summary = structured.get("summary", "")
            existing.key_concepts = structured.get("key_concepts", [])
            existing.key_citations = structured.get("key_citations", [])
            existing.critical_questions = structured.get("critical_questions", [])
            existing.overall_evaluation = structured.get("overall_evaluation", {})
            note = existing
        else:
            note = PaperNote(
                paper_id=paper.id,
                summary=structured.get("summary", ""),
                key_concepts=structured.get("key_concepts", []),
                key_citations=structured.get("key_citations", []),
                critical_questions=structured.get("critical_questions", []),
                overall_evaluation=structured.get("overall_evaluation", {}),
            )
            self.db.add(note)

        await self.db.commit()
        await self.db.refresh(note)
        return note

    def _parse_note_markdown(self, markdown: str) -> Dict[str, Any]:
        """Parse note markdown to extract structured data."""
        # Simple parsing - in production, use more robust markdown parsing
        result = {
            "summary": "",
            "key_concepts": [],
            "key_citations": [],
            "critical_questions": [],
            "overall_evaluation": {},
        }

        # Extract summary (after "## 一句话总结")
        import re

        summary_match = re.search(r"##\s*一句话总结\s*\n(.+?)(?=\n##|\Z)", markdown, re.DOTALL)
        if summary_match:
            result["summary"] = summary_match.group(1).strip()

        # Extract concepts table
        concepts = re.findall(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", markdown)
        for term, definition in concepts:
            term = term.strip()
            definition = definition.strip()
            if term and definition and term not in ("术语", "------", "---"):
                result["key_concepts"].append(
                    {"term": term, "definition": definition, "page_ref": []}
                )

        # Extract critical questions
        questions = re.findall(r"\d+\.\s+(.+?)(?=\n\d+\.|\n##|\Z)", markdown)
        if questions:
            result["critical_questions"] = [q.strip() for q in questions if q.strip()]

        return result


class QAService:
    """Service for Q&A with citations."""

    def __init__(self, db: AsyncSession, fipai: FIPAIService):
        self.db = db
        self.fipai = fipai

    async def answer(
        self,
        paper: Paper,
        question: str,
        session_id: UUID,
        chat_history: List[Dict[str, str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Answer question with citations."""
        rag_service = RAGService(self.db)

        # Search relevant chunks
        retrieved = await rag_service.search(
            paper_id=str(paper.id),
            query=question,
            top_k=top_k,
        )

        # Get session memory facts
        from app.service.session import SessionService

        session_service = SessionService(self.db)
        memory_facts = await session_service.get_recent_facts(paper.id, session_id, limit=5)

        # Convert retrieved chunks to payload
        chunks_payload = [
            {
                "chunk_id": c.chunk_id,
                "heading": c.heading,
                "page_range": c.page_range,
                "chapter_index": c.chapter_index,
                "text": c.text,
                "score": round(c.score, 6),
            }
            for c in retrieved
        ]

        # Get paper title
        source_title = paper.paper_metadata.get("title", "") if paper.paper_metadata else ""

        # Call FIPAI
        response = await self.fipai.answer_with_citations(
            question=question,
            retrieved_chunks=chunks_payload,
            chat_history=chat_history or [],
            source_title=source_title,
            memory_facts=memory_facts,
        )

        # Enrich citations with actual chunk data
        citations = self._enrich_citations(response.get("citations", []), retrieved)
        facts = response.get("facts", [])
        if not self._validate_citations(citations, retrieved):
            return {
                "answer": "未能生成可靠引用。请重试或换一种提问方式。",
                "citations": [],
                "facts": [],
                "fact_conflicts": [],
            }

        # Store in session memory
        await session_service.add_turn(
            paper_id=paper.id,
            session_id=session_id,
            turn_type="user",
            question=question,
        )
        await session_service.add_turn(
            paper_id=paper.id,
            session_id=session_id,
            turn_type="assistant",
            answer=response.get("answer", ""),
            citations=citations,
            facts=facts,
        )

        # Detect fact conflicts
        fact_conflicts = self._detect_conflicts(facts, memory_facts)

        return {
            "answer": response.get("answer", "").strip(),
            "citations": citations,
            "facts": facts,
            "fact_conflicts": fact_conflicts,
        }

    def _validate_citations(self, citations: List[Dict[str, Any]], retrieved: List) -> bool:
        retrieved_map = {c.chunk_id: c.text for c in retrieved}
        return validate_citations(
            citations=citations,
            retrieved_map=retrieved_map,
            min_required=settings.rag_min_citations,
        )

    def _enrich_citations(
        self, citations: List[Dict[str, Any]], retrieved: List
    ) -> List[Dict[str, Any]]:
        """Enrich citations with actual chunk data."""
        by_id = {c.chunk_id: c for c in retrieved}
        rows = []
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
                    "page_range": c.get("page_range") or hit.page_range,
                }
            )
        return rows

    def _detect_conflicts(
        self, new_facts: List[Dict[str, Any]], memory_facts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between new and memory facts."""
        import re

        conflicts = []
        if not new_facts or not memory_facts:
            return conflicts

        def has_negation(text: str) -> bool:
            t = text.lower()
            markers = [" not ", " no ", " never ", " cannot ", " can't ", " without "]
            return any(m in f" {t} " for m in markers)

        def tokenize(text: str) -> set:
            return set(re.findall(r"[A-Za-z0-9_]+|[一-鿿]", text.lower()))

        for nf in new_facts:
            new_claim = str(nf.get("claim", "")).strip()
            if len(new_claim) < 8:
                continue
            new_tokens = tokenize(new_claim)
            if not new_tokens:
                continue
            new_neg = has_negation(new_claim)

            for mf in memory_facts:
                old_claim = str(mf.get("claim", "")).strip()
                if len(old_claim) < 8:
                    continue
                old_tokens = tokenize(old_claim)
                if not old_tokens:
                    continue
                overlap = len(new_tokens & old_tokens) / max(1, min(len(new_tokens), len(old_tokens)))
                old_neg = has_negation(old_claim)

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
