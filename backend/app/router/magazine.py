"""杂志书架路由：上传杂志 PDF → 拆分 → 评级入库。"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from app.service.magazine import MagazineService

router = APIRouter(prefix="/api/magazine", tags=["magazine"])

_service = MagazineService()


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
    if suffix != "pdf":
        raise HTTPException(400, "Only PDF files supported")
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
