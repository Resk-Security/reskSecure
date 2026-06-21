from __future__ import annotations
import time
from pathlib import Path
from threading import Lock, Thread
from typing import Callable, Optional

from .cache import trie_cache
from .policy_loader import PolicySet, load_policy


class PolicyWatcher:
    """Watches a policy file for changes and triggers cache invalidation."""

    def __init__(
        self,
        policy_path: str | Path,
        interval: float = 5.0,
        on_reload: Optional[Callable[[PolicySet], None]] = None,
        auto_start: bool = True,
    ):
        self._path = Path(policy_path)
        self._interval = interval
        self._on_reload = on_reload
        self._last_mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
        self._running = False
        self._thread: Optional[Thread] = None
        self._lock = Lock()
        self._current_policy: Optional[PolicySet] = None

        if auto_start:
            self.start()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = Thread(target=self._watch, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    @property
    def current_policy(self) -> Optional[PolicySet]:
        with self._lock:
            return self._current_policy

    def _watch(self) -> None:
        while self._running:
            try:
                if self._path.exists():
                    mtime = self._path.stat().st_mtime
                    if mtime > self._last_mtime:
                        self._last_mtime = mtime
                        policy = load_policy(self._path)
                        with self._lock:
                            self._current_policy = policy
                        trie_cache.invalidate_all()
                        if self._on_reload:
                            self._on_reload(policy)
            except Exception:
                pass
            time.sleep(self._interval)

    def __enter__(self) -> "PolicyWatcher":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()
