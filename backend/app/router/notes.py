from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.model.database import get_db
from app.model.paper import Paper, PaperNote
from app.schema.note import (
    PaperNoteDetail,
    NoteGenerateRequest,
    NoteGenerateResponse,
    KeyConcept,
    KeyCitation,
    OverallEvaluation,
)
from app.schema.paper import PaperDetail
from app.service.fipai import FIPAIService
from app.service.notes import NoteService
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/papers/{paper_id}/notes", tags=["notes"])


async def get_paper(paper_id: UUID, user_id: UUID, db: AsyncSession) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@router.get("", response_model=PaperNoteDetail)
async def get_note(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paper note."""
    paper = await get_paper(paper_id, user.id, db)

    if paper.status != "ready":
        raise HTTPException(400, "Paper not ready. Parse first.")

    stmt = select(PaperNote).where(PaperNote.paper_id == paper_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(404, "Note not found. Generate first.")

    return PaperNoteDetail(
        id=note.id,
        paper_id=note.paper_id,
        summary=note.summary,
        key_concepts=[KeyConcept(**c) for c in note.key_concepts] if note.key_concepts else [],
        key_citations=[KeyCitation(**c) for c in note.key_citations] if note.key_citations else [],
        critical_questions=note.critical_questions or [],
        overall_evaluation=OverallEvaluation(**note.overall_evaluation) if note.overall_evaluation else OverallEvaluation(),
    )


@router.post("/generate", response_model=NoteGenerateResponse)
async def generate_note(
    paper_id: UUID,
    request: NoteGenerateRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Generate or refresh paper note."""
    paper = await get_paper(paper_id, user.id, db)

    if paper.status != "ready":
        raise HTTPException(400, "Paper not ready. Parse first.")

    # Run in background to avoid timeout
    background_tasks.add_task(_generate_note_task, paper_id, request.force_refresh)

    return NoteGenerateResponse(
        paper_id=paper_id,
        status="processing",
        message="Note generation started in background",
    )


async def _generate_note_task(paper_id: UUID, force: bool, max_retries: int = 3):
    """Background task to generate note with retry logic."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import asyncio

    settings_obj = __import__("config", fromlist=["get_settings"]).get_settings()
    engine = create_async_engine(settings_obj.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    last_error = None
    for attempt in range(max_retries):
        async with async_session() as session:
            from sqlalchemy import select, update

            stmt = select(Paper).where(Paper.id == paper_id)
            result = await session.execute(stmt)
            paper = result.scalar_one_or_none()

            if not paper:
                return

            try:
                # Update status to processing
                await session.execute(
                    update(Paper)
                    .where(Paper.id == paper_id)
                    .values(status="processing", error_message=None)
                )
                await session.commit()

                fipai = FIPAIService()
                note_service = NoteService(session, fipai)
                await note_service.generate_note(paper, force=force)

                # Success - update status
                await session.execute(
                    update(Paper)
                    .where(Paper.id == paper_id)
                    .values(status="ready")
                )
                await session.commit()
                return  # Success, exit retry loop

            except Exception as e:
                last_error = e
                error_msg = f"attempt_{attempt + 1}/{max_retries}: {str(e)[:200]}"
                print(f"Note generation error: {error_msg}")

                # Update paper with error info
                try:
                    await session.rollback()
                    await session.execute(
                        update(Paper)
                        .where(Paper.id == paper_id)
                        .values(status="error", error_message=error_msg)
                    )
                    await session.commit()
                except Exception:
                    pass

                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s

    # All retries failed
    print(f"Note generation failed after {max_retries} attempts: {last_error}")
    try:
        async with async_session() as session:
            from sqlalchemy import update
            await session.execute(
                update(Paper)
                .where(Paper.id == paper_id)
                .values(
                    status="error",
                    error_message=f"Note generation failed after {max_retries} attempts: {str(last_error)[:200]}"
                )
            )
            await session.commit()
    except Exception:
        pass
    finally:
        await engine.dispose()


@router.post("/generate/sync", response_model=NoteGenerateResponse)
async def generate_note_sync(
    paper_id: UUID,
    request: NoteGenerateRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate note synchronously (for testing)."""
    paper = await get_paper(paper_id, user.id, db)

    if paper.status != "ready":
        raise HTTPException(400, "Paper not ready. Parse first.")

    try:
        fipai = FIPAIService()
        note_service = NoteService(db, fipai)
        await note_service.generate_note(paper, force=request.force_refresh)
        return NoteGenerateResponse(
            paper_id=paper_id,
            status="ready",
            message="Note generated successfully",
        )
    except Exception as e:
        raise HTTPException(500, str(e))
