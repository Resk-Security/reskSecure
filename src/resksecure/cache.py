from __future__ import annotations
import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple


class TrieCache:
    def __init__(self, ttl: int = 300):
        self._data: Dict[Tuple[int, str], Tuple[Any, float]] = {}
        self._ttl = ttl
        self._lock = Lock()

    def get(self, key: Tuple[int, str]) -> Any:
        with self._lock:
            if key not in self._data:
                return None
            entry, timestamp = self._data[key]
            if time.monotonic() - timestamp > self._ttl:
                del self._data[key]
                return None
            return entry

    def set(self, key: Tuple[int, str], value: Any) -> None:
        with self._lock:
            self._data[key] = (value, time.monotonic())

    def invalidate(
        self,
        mask: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> None:
        with self._lock:
            if mask is None and model_name is None:
                self._data.clear()
                return
            keys_to_delete = [
                k for k in self._data
                if (mask is None or k[0] == mask)
                and (model_name is None or k[1] == model_name)
            ]
            for k in keys_to_delete:
                del self._data[k]

    def invalidate_all(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


trie_cache = TrieCache()
