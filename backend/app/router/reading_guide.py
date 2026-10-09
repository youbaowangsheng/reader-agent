from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.model.database import get_db
from app.model.paper import Paper
from app.service.llm import LLMService
from app.service.reading_guide import ReadingGuideService
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/papers/{paper_id}/reading-guide", tags=["reading-guide"])


class GuideGenerateRequest(BaseModel):
    force: bool = False


class EngagementUpdate(BaseModel):
    judgments: Optional[Dict[str, str]] = None
    notes: Optional[Dict[str, str]] = None
    my_view: Optional[str] = None
    quiz_answers: Optional[Dict[str, str]] = None


async def get_paper(paper_id: UUID, user_id: UUID, db: AsyncSession) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@router.get("")
async def get_reading_guide(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取导读产物。"""
    paper = await get_paper(paper_id, user.id, db)
    return paper.reading_guide or {"status": "none"}


@router.post("/generate")
async def generate_reading_guide(
    paper_id: UUID,
    request: GuideGenerateRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """触发导读生成（异步），force=true 支持重新生成。"""
    paper = await get_paper(paper_id, user.id, db)
    if paper.status != "ready":
        raise HTTPException(400, "Paper not ready. Parse first.")
    background_tasks.add_task(_generate_task, paper_id, request.force)
    return {"paper_id": str(paper_id), "status": "processing", "message": "导读生成已启动"}


async def _generate_task(paper_id: UUID, force: bool, max_retries: int = 2):
    """后台任务：生成导读，带重试。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import asyncio

    settings_obj = __import__("config", fromlist=["get_settings"]).get_settings()
    engine = create_async_engine(settings_obj.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    last_error = None
    for attempt in range(max_retries):
        async with async_session() as session:
            stmt = select(Paper).where(Paper.id == paper_id)
            result = await session.execute(stmt)
            paper = result.scalar_one_or_none()
            if not paper:
                await engine.dispose()
                return
            try:
                llm = LLMService()
                service = ReadingGuideService(session, llm)
                await service.generate(paper, force=force)
                await engine.dispose()
                return
            except Exception as e:
                last_error = e
                print(f"Reading guide generation error (attempt {attempt + 1}/{max_retries}): {str(e)[:200]}")
                await session.rollback()
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

    # 全部失败：标记导读状态 error
    try:
        async with async_session() as session:
            stmt = select(Paper).where(Paper.id == paper_id)
            result = await session.execute(stmt)
            paper = result.scalar_one_or_none()
            if paper:
                paper.reading_guide = {"status": "error", "error": str(last_error)[:200]}
                await session.commit()
    except Exception:
        pass
    finally:
        await engine.dispose()


@router.put("/engagement")
async def save_engagement(
    paper_id: UUID,
    payload: EngagementUpdate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """存用户交互（判断/看法/观点/检测答案），浅合并。"""
    paper = await get_paper(paper_id, user.id, db)
    llm = LLMService()
    service = ReadingGuideService(db, llm)
    data = payload.model_dump(exclude_none=True)
    return await service.save_engagement(paper, data)


@router.get("/engagement/export")
async def export_engagement(
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出认同观点 + 看法 + 整体观点为 Markdown。"""
    paper = await get_paper(paper_id, user.id, db)
    llm = LLMService()
    service = ReadingGuideService(db, llm)
    markdown = service.export_engagement(paper)
    return {"markdown": markdown}
