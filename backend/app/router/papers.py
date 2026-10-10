from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from uuid import UUID
import shutil
import os
import uuid

from app.model.database import get_db
from app.model.paper import Paper
from app.schema.paper import (
    PaperSummary,
    PaperDetail,
    PaperUploadResponse,
    PaperDeleteResponse,
)
from app.service.parsing import parse_document
from app.service.rag import RAGService
from app.service.fipai import FIPAIService
from app.service.notes import NoteService
from config import get_settings
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/papers", tags=["papers"])
settings = get_settings()


def get_storage_url(filename: str) -> str:
    """Get the URL path for a stored file."""
    return f"/storage/{filename}"


@router.post("/upload", response_model=PaperUploadResponse)
async def upload_paper(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
):
    """Upload PDF/EPUB file."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".pdf", ".epub"]:
        raise HTTPException(400, "Only PDF and EPUB files supported")

    # Generate unique file path
    file_id = uuid.uuid4()
    stored_filename = f"{file_id}_{file.filename}"
    storage_dir = settings.storage_url
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, stored_filename)

    # Save file
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create paper record - store relative URL for frontend access
    paper = Paper(
        id=file_id,
        user_id=user.id,
        filename=file.filename,
        file_url=get_storage_url(stored_filename),
        status="pending",
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    return PaperUploadResponse(
        id=paper.id,
        filename=paper.filename,
        status=paper.status,
        message="File uploaded successfully",
    )


@router.get("", response_model=List[PaperSummary])
async def list_papers(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """List user's papers."""
    stmt = (
        select(Paper)
        .where(Paper.user_id == user.id)
        .order_by(Paper.last_read_at.desc().nullslast(), Paper.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    papers = result.scalars().all()
    return [PaperSummary.model_validate(p) for p in papers]


@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paper details."""
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user.id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    return PaperDetail.model_validate(paper)


@router.post("/{paper_id}/read")
async def mark_read(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录最后阅读时间（用于待读列表按阅读时间排序）。"""
    from datetime import datetime, timezone
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user.id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    paper.last_read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"paper_id": str(paper_id), "last_read_at": paper.last_read_at.isoformat()}


@router.delete("/{paper_id}", response_model=PaperDeleteResponse)
async def delete_paper(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete paper and all related data."""
    stmt_get = select(Paper).where(Paper.id == paper_id, Paper.user_id == user.id)
    result_get = await db.execute(stmt_get)
    paper = result_get.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")

    stored_filename = os.path.basename(paper.file_url or "")
    file_path = os.path.join(settings.storage_url, stored_filename)

    stmt = delete(Paper).where(Paper.id == paper_id, Paper.user_id == user.id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(404, "Paper not found")

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    return PaperDeleteResponse(deleted=True, paper_id=paper_id)


async def process_paper_task(paper_id: UUID, db_url: str):
    """Background task to parse paper and build index."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    # Import all models to ensure relationships are registered
    from app.model.paper import Paper, PaperNote  # noqa: F401
    from app.model.fact_card import FactCard  # noqa: F401
    from app.model.paper_chunk import PaperChunk  # noqa: F401
    from app.model.paper_chunk_vector import PaperChunkVector  # noqa: F401
    from app.model.session_memory import SessionMemory  # noqa: F401

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        from sqlalchemy import select

        stmt = select(Paper).where(Paper.id == paper_id)
        result = await session.execute(stmt)
        paper = result.scalar_one_or_none()

        if not paper:
            return

        try:
            paper.status = "processing"
            await session.commit()

            # Reconstruct absolute path for parsing
            stored_filename = os.path.basename(paper.file_url)
            file_path = os.path.join(settings.storage_url, stored_filename)

            # Parse document
            parsed_doc = parse_document(file_path)

            # Clean null characters from content (PostgreSQL cannot handle null bytes)
            def clean_text(obj):
                if isinstance(obj, str):
                    return obj.replace('\x00', '')
                elif isinstance(obj, dict):
                    return {k: clean_text(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_text(item) for item in obj]
                return obj

            parsed_doc = clean_text(parsed_doc)

            # Update paper with parsed structure
            paper.paper_metadata = {"title": parsed_doc.get("title", paper.filename)}
            paper.parsed_structure = parsed_doc
            paper.status = "parsed"
            await session.commit()

            # Build RAG index
            rag_service = RAGService(session)
            chunk_count = await rag_service.build_index(
                paper_id=str(paper.id),
                parsed_doc=parsed_doc,
            )

            # Auto-generate note for a ready paper to close the ingestion loop
            if settings.auto_generate_note:
                try:
                    fipai = FIPAIService()
                    note_service = NoteService(session, fipai)
                    await note_service.generate_note(paper, force=False)
                except Exception as note_exc:
                    # Keep paper usable for RAG even if note generation fails
                    paper.error_message = f"note_generation_failed: {str(note_exc)[:200]}"
                    await session.commit()

            paper.status = "ready"
            await session.commit()

        except Exception as e:
            paper.status = "error"
            paper.error_message = str(e)
            await session.commit()
        finally:
            await engine.dispose()


@router.post("/{paper_id}/parse")
async def trigger_parse(
    paper_id: UUID,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger paper parsing and RAG index building."""
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user.id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")

    if paper.status in ("processing", "ready"):
        return {"status": paper.status, "message": "Paper already processed or processing"}

    background_tasks.add_task(process_paper_task, paper_id, settings.database_url)

    paper.status = "processing"
    await db.commit()

    return {"status": "processing", "message": "Parsing started in background"}
