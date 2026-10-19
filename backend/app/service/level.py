"""当前阅读难度档位（1-5，对应精读 L1-L5），自适应闭环的核心状态。

评分后自动调档：低分降档、高分升档，目标是让人停在心流区间、不断读。
"""
import json
import os
import threading


class LevelStore:
    """读写当前难度档位，线程安全（JSON 文件，单机够用）。"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def get_level(self) -> int:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            lvl = int(data.get("level", 3))
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            lvl = 3
        return max(1, min(5, lvl))

    def adjust(self, delta: int) -> int:
        with self._lock:
            new = max(1, min(5, self.get_level() + delta))
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"level": new}, f)
            os.replace(tmp, self.path)
        return new
