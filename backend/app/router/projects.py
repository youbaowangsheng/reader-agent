from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from uuid import UUID
from datetime import datetime

from app.model.database import get_db
from app.model.project import Project, project_papers
from app.model.paper import Paper
from app.schema.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectDetail,
    ProjectListItem,
    PaperInProject,
)
from app.core.security import get_current_user, AuthUser

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=List[ProjectListItem])
async def list_projects(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all projects for current user."""
    stmt = (
        select(Project, func.count(project_papers.c.paper_id).label('paper_count'))
        .outerjoin(project_papers, Project.id == project_papers.c.project_id)
        .where(Project.user_id == user.id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        ProjectListItem(
            id=p.id,
            name=p.name,
            description=p.description or '',
            paper_count=count,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p, count in rows
    ]


@router.post("", response_model=ProjectDetail)
async def create_project(
    data: ProjectCreate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(
        user_id=user.id,
        name=data.name,
        description=data.description or '',
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectDetail(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description or '',
        papers=[],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project with papers."""
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    # Get papers in project
    paper_stmt = (
        select(Paper)
        .join(project_papers, Paper.id == project_papers.c.paper_id)
        .where(project_papers.c.project_id == project_id)
        .order_by(project_papers.c.added_at.desc())
    )
    paper_result = await db.execute(paper_stmt)
    papers = paper_result.scalars().all()

    return ProjectDetail(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description or '',
        papers=[
            PaperInProject(
                id=p.id,
                filename=p.filename,
                status=p.status,
                added_at=datetime.utcnow(),
            )
            for p in papers
        ],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.put("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project name/description."""
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    project.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(project)

    # Get papers
    paper_stmt = (
        select(Paper)
        .join(project_papers, Paper.id == project_papers.c.paper_id)
        .where(project_papers.c.project_id == project_id)
    )
    paper_result = await db.execute(paper_stmt)
    papers = paper_result.scalars().all()

    return ProjectDetail(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description or '',
        papers=[
            PaperInProject(id=p.id, filename=p.filename, status=p.status, added_at=datetime.utcnow())
            for p in papers
        ],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete project."""
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    await db.delete(project)
    await db.commit()
    return {"ok": True}


@router.post("/{project_id}/papers/{paper_id}")
async def add_paper_to_project(
    project_id: UUID,
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a paper to project."""
    # Verify project ownership
    proj_stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    proj_result = await db.execute(proj_stmt)
    if not proj_result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    # Verify paper ownership
    paper_stmt = select(Paper).where(Paper.id == paper_id, Paper.user_id == user.id)
    paper_result = await db.execute(paper_stmt)
    if not paper_result.scalar_one_or_none():
        raise HTTPException(404, "Paper not found")

    try:
        await db.execute(
            project_papers.insert().values(project_id=project_id, paper_id=paper_id)
        )
        await db.commit()
    except Exception:
        pass  # Already exists

    # Update project timestamp
    await db.execute(
        Project.__table__.update().where(Project.id == project_id).values(updated_at=datetime.utcnow())
    )
    await db.commit()

    return {"ok": True}


@router.delete("/{project_id}/papers/{paper_id}")
async def remove_paper_from_project(
    project_id: UUID,
    paper_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a paper from project."""
    proj_stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    proj_result = await db.execute(proj_stmt)
    if not proj_result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    await db.execute(
        project_papers.delete().where(
            project_papers.c.project_id == project_id,
            project_papers.c.paper_id == paper_id,
        )
    )
    await db.commit()
    return {"ok": True}
