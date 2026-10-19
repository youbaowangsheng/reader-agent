"""阅读记录路由：标记读完、查询已读、兴趣统计与断读检测。"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.service.reading_log import ReadingLogStore
from app.service.level import LevelStore

router = APIRouter(prefix="/api/reading", tags=["reading"])

_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_store = ReadingLogStore(os.path.join(_data_dir, "reading_log.json"))
_level_store = LevelStore(os.path.join(_data_dir, "level.json"))


class MarkReadRequest(BaseModel):
    type: str  # intensive | extensive | paper
    id: str


@router.post("/mark-read")
async def mark_read(req: MarkReadRequest):
    return _store.mark_read(req.type, req.id)


@router.get("")
async def list_read():
    return {"read": _store.all_read()}


@router.get("/level")
async def get_level():
    """当前阅读难度档位（1-5，对应精读 L1-L5）。"""
    return {"level": _level_store.get_level()}


def _id_to_topic() -> dict:
    """精读文章 id -> topic 映射（兴趣统计用）。"""
    mapping = {}
    try:
        with open(os.path.join(_data_dir, "articles_v1.json"), encoding="utf-8") as f:
            data = json.load(f)
        for i, a in enumerate(data):
            mapping[str(i)] = a.get("topic", "")
    except Exception:
        pass
    return mapping


@router.get("/stats")
async def get_stats():
    """兴趣统计（各 topic 精读读完篇数）+ 断读检测（距上次读完的天数）。"""
    reads = _store.all_read()
    id_to_topic = _id_to_topic()
    topics = {}
    last_read_at = None
    for r in reads:
        ra = r.get("read_at", "")
        if ra and (last_read_at is None or ra > last_read_at):
            last_read_at = ra
        if r.get("type") == "intensive":
            topic = id_to_topic.get(str(r.get("id")), "")
            if topic:
                topics[topic] = topics.get(topic, 0) + 1
    days_since = None
    if last_read_at:
        try:
            last_dt = datetime.fromisoformat(last_read_at)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - last_dt).days
        except ValueError:
            pass
    return {"topics": topics, "last_read_at": last_read_at, "days_since": days_since}
