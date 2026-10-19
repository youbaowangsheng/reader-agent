"""阅读记录：持久化每次「读完」事件，支撑习惯养成与自适应闭环。"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List


class ReadingLogStore:
    """按 key=f"{type}:{id}" 存「读完」记录，线程安全（JSON 文件，单机够用）。"""

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

    def mark_read(self, rtype: str, rid: str) -> Dict[str, Any]:
        key = f"{rtype}:{rid}"
        entry = {
            "type": rtype,
            "id": str(rid),
            "read_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            data = self._load()
            data[key] = entry
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        return entry

    def is_read(self, rtype: str, rid: str) -> bool:
        return f"{rtype}:{rid}" in self._load()

    def all_read(self) -> List[Dict[str, Any]]:
        return list(self._load().values())
