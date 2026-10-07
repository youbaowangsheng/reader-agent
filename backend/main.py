from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import os

from config import get_settings
from app.model.database import engine, Base
from app.model.project import Project  # noqa: F401 - registers model

from app.router import papers, chunks, notes, fact_cards, sessions, auth, projects, market

settings = get_settings()
settings.validate_security_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup: create tables if they don't exist
    async with engine.begin() as conn:
        # Enable pgvector extension for PostgreSQL
        if conn.dialect.name == "postgresql":
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass  # Extension might already exist
        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Reader Agent Backend API - PDF/EPUB parsing, RAG, and AI-powered paper reading",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded papers
storage_path = settings.storage_url
if settings.public_storage_enabled and os.path.exists(storage_path):
    app.mount("/storage", StaticFiles(directory=storage_path), name="storage")

# Include routers
app.include_router(auth.router)
app.include_router(papers.router)
app.include_router(chunks.router)
app.include_router(notes.router)
app.include_router(fact_cards.router)
app.include_router(sessions.router)
app.include_router(projects.router)
app.include_router(market.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "reader-agent-backend"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Reader Agent Backend",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug,
    )
