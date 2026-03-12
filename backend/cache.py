"""
Simple TTL-based in-memory cache.
No disk, no database — data evicts after expiry and is re-fetched
from upstream on the next request.

Thread-safe via a simple lock since FastAPI runs background tasks
on a threadpool.
"""

from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """
    Key-value cache with per-entry TTL.

    Usage:
        cache = TTLCache(default_ttl=300)
        cache.set("satnogs:2026-01-01:2026-01-14", data)
        result = cache.get("satnogs:2026-01-01:2026-01-14")
    """

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry.expires_at:
                del self._store[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            expires = time.time() + (ttl if ttl is not None else self.default_ttl)
            self._store[key] = CacheEntry(value=value, expires_at=expires)

    def invalidate(self, prefix: str = "") -> int:
        """Remove entries matching a key prefix. Returns count removed."""
        with self._lock:
            if not prefix:
                count = len(self._store)
                self._store.clear()
                return count
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def stats(self) -> dict:
        with self._lock:
            now = time.time()
            total = len(self._store)
            alive = sum(1 for e in self._store.values() if now <= e.expires_at)
            return {"total_entries": total, "alive": alive, "expired": total - alive}


# ── Global cache instance ───────────────────────────────────────────
# TTL is set from config at import time in main.py; default 5 min
cache = TTLCache(default_ttl=300)