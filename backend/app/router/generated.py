"""导读目录路由：汇总已生成的精读导读 + 泛读检测题。"""
from fastapi import APIRouter

from app.service.intensive import IntensiveService
from app.service.extensive import ExtensiveService

router = APIRouter(prefix="/api/generated", tags=["generated"])

_intensive = IntensiveService()
_extensive = ExtensiveService()


@router.get("")
async def list_all_generated():
    """汇总所有已生成内容（精读导读 + 泛读检测题），供导读目录页使用。"""
    return {
        "guides": _intensive.list_generated(),
        "questions": _extensive.list_generated(),
    }
