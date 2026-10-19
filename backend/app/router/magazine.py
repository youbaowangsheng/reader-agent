"""杂志书架路由：上传杂志 PDF/EPUB → 拆分 → 评级入库 / 加入原文阅读。"""
import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.magazine import MagazineService
from app.model.database import get_db
from app.model.paper import Paper
from app.core.security import get_current_user, AuthUser
from app.router.papers import process_paper_task
from config import get_settings

router = APIRouter(prefix="/api/magazine", tags=["magazine"])

_service = MagazineService()
_settings = get_settings()


@router.get("")
async def list_magazines():
    return _service.list_magazines()


@router.get("/{mid}")
async def get_magazine(mid: str):
    mag = _service.get_magazine(mid)
    if not mag:
        raise HTTPException(404, "Magazine not found")
    return mag


@router.post("/upload")
async def upload_magazine(file: UploadFile = File(...)):
    """上传杂志 PDF，立即拆分，返回拆出的文章列表。"""
    if not file.filename:
        raise HTTPException(400, "No filename")
    suffix = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if suffix not in ("pdf", "epub"):
        raise HTTPException(400, "Only PDF and EPUB files supported")
    content = await file.read()
    mag = _service.save_upload(file.filename, content)
    return {
        "id": mag["id"],
        "filename": mag["filename"],
        "status": mag["status"],
        "article_count": mag["article_count"],
        "articles": [
            {"title": a["title"], "word_count": a["word_count"], "author": a.get("author", "")}
            for a in mag["articles"][:60]
        ],
    }


@router.post("/{mid}/import")
async def import_articles(mid: str, background_tasks: BackgroundTasks):
    """后台评级并入库到精读/泛读语料（逐篇调 LLM，耗时较长）。"""
    mag = _service.get_magazine(mid)
    if not mag:
        raise HTTPException(404, "Magazine not found")
    if mag["status"] == "importing":
        return {"status": "importing", "message": "正在导入中"}
    background_tasks.add_task(_service.import_articles, mid)
    return {"status": "importing", "message": "已开始后台导入"}


@router.post("/{mid}/to-paper")
async def magazine_to_paper(
    mid: str,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """把杂志原文加入「原文阅读」：复制文件到 papers 存储、创建 Paper 并触发解析。"""
    mag = _service.get_magazine(mid)
    if not mag:
        raise HTTPException(404, "Magazine not found")

    stored_name = mag.get("file_path") or f"{mid}.pdf"
    src_path = os.path.join(_service.storage_dir, stored_name)
    if not os.path.exists(src_path):
        raise HTTPException(404, "原文文件不存在")

    file_id = uuid.uuid4()
    suffix = os.path.splitext(mag["filename"])[1].lower() or ".pdf"
    new_stored = f"{file_id}{suffix}"
    dest_dir = _settings.storage_url
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy(src_path, os.path.join(dest_dir, new_stored))

    paper = Paper(
        id=file_id,
        user_id=user.id,
        filename=mag["filename"],
        file_url=f"/storage/{new_stored}",
        status="pending",
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    background_tasks.add_task(process_paper_task, paper.id, _settings.database_url)
    paper.status = "processing"
    await db.commit()

    return {"id": str(paper.id), "filename": paper.filename, "status": "processing", "message": "已加入原文阅读"}
