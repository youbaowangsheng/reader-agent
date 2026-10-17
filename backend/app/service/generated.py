"""精读/泛读已生成内容的持久化存储（JSON 文件，单机够用）。

避免重复生成浪费 token：生成导读/检测题后保存，下次直接读。
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class GeneratedStore:
    """按 key 存 JSON 值的持久化存储，线程安全。"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get(self, key) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._load().get(str(key))

    def set(self, key, value: Dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            data[str(key)] = value
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return self._load()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
