"""阅读记录路由：标记读完、查询已读。"""
import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.service.reading_log import ReadingLogStore

router = APIRouter(prefix="/api/reading", tags=["reading"])

_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_store = ReadingLogStore(os.path.join(_data_dir, "reading_log.json"))


class MarkReadRequest(BaseModel):
    type: str  # intensive | extensive | paper
    id: str


@router.post("/mark-read")
async def mark_read(req: MarkReadRequest):
    return _store.mark_read(req.type, req.id)


@router.get("")
async def list_read():
    return {"read": _store.all_read()}
