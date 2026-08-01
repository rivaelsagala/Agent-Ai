"""Database helpers (lightweight JSON-backed store for chat history)."""
import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from app.config import BASE_DIR


class JSONStore:
    """A tiny append-only JSON store used for demo persistence."""

    def __init__(self, name: str):
        self.path = BASE_DIR / "data" / f"{name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def append(self, record: dict) -> None:
        with self._lock:
            data = self._load_unlocked()
            data.append(record)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=f".{self.path.stem}-",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    json.dump(data, temporary, indent=2)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_path = Path(temporary.name)
                os.replace(temporary_path, self.path)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()

    def load(self) -> list:
        with self._lock:
            return self._load_unlocked()

    def _load_unlocked(self) -> list:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))


chat_history = JSONStore("chat_history")
