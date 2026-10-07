from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
import httpx
import httpx

from app.model.database import get_db
from app.model.paper import Paper
from app.model.paper_chunk import PaperChunk
from app.schema.chunk import (
    ChunkSearchQuery,
    ChunkSearchResult,
    ChunkDetail,
    QARequest,
    QAResponse,
)
from app.service.rag import RAGService
from app.service.fipai import FIPAIService
from app.service.notes import QAService
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/papers/{paper_id}/chunks", tags=["chunks"])


async def get_paper(paper_id: UUID, user_id: UUID, db: AsyncSession) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@router.post("/search", response_model=List[ChunkSearchResult])
async def search_chunks(
    paper_id: UUID,
    query: ChunkSearchQuery,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """RAG search - returns relevant chunks with scores."""
    paper = await get_paper(paper_id, user.id, db)

    if paper.status != "ready":
        raise HTTPException(400, "Paper not ready. Parse first.")

    rag_service = RAGService(db)
    chunks = await rag_service.search(
        paper_id=str(paper_id),
        query=query.query,
        top_k=query.top_k,
    )

    return [
        ChunkSearchResult(
            chunk_id=c.chunk_id,
            score=c.score,
            heading=c.heading,
            page_range=c.page_range,
            chapter_index=c.chapter_index,
            text=c.text,
        )
        for c in chunks
    ]


@router.get("/{chunk_id}", response_model=ChunkDetail)
async def get_chunk(
    paper_id: UUID,
    chunk_id: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get specific chunk by ID."""
    await get_paper(paper_id, user.id, db)

    rag_service = RAGService(db)
    chunk = await rag_service.get_chunk(paper_id=str(paper_id), chunk_id=chunk_id)
    if not chunk:
        raise HTTPException(404, "Chunk not found")

    return ChunkDetail(
        id=chunk.id,
        chunk_id=chunk.chunk_id,
        heading=chunk.heading,
        page_range=chunk.page_range,
        chapter_index=chunk.chapter_index,
        content=chunk.content,
    )


@router.post("/qa", response_model=QAResponse)
async def ask_question(
    paper_id: UUID,
    question: QARequest,
    session_id: UUID = Header(..., alias="X-Session-ID"),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Q&A with citations."""
    paper = await get_paper(paper_id, user.id, db)

    if paper.status != "ready":
        raise HTTPException(400, "Paper not ready. Parse first.")

    try:
        fipai = FIPAIService()
        qa_service = QAService(db, fipai)

        result = await qa_service.answer(
            paper=paper,
            question=question.question,
            session_id=session_id,
            chat_history=question.chat_history,
            top_k=question.top_k,
        )

        return QAResponse(
            answer=result["answer"],
            citations=result["citations"],
            facts=result["facts"],
            fact_conflicts=result.get("fact_conflicts"),
        )
    except HTTPException:
        raise
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError,
            httpx.PoolTimeout, httpx.WriteError, httpx.ReadError) as e:
        raise HTTPException(503, "AI service unavailable. Please try again later.")
    except Exception as e:
        err_str = str(e).lower()
        if ("connection" in err_str or "connect" in err_str or "httpx" in err_str or
                "timeout" in err_str or "all connection attempts failed" in err_str):
            raise HTTPException(503, f"AI service unavailable. Details: {str(e)[:100]}")
        raise HTTPException(500, f"Q&A failed: {str(e)}")
