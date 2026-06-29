"""
In-memory LRU cache with TTL support.

Provides a thread-safe, size-limited cache with automatic expiry.
Designed as a drop-in layer for frequently accessed data (plans, settings, user profiles).
Future: swap with RedisCache using the same interface.
"""
import time
import logging
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryCache:
    """Thread-safe in-memory cache with TTL and LRU eviction."""

    def __init__(self, max_size: int = 2000, default_ttl: int = 300):
        self._data: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key. Returns default if not found or expired."""
        entry = self._data.get(key)
        if entry is None:
            self._misses += 1
            return default
        value, expire_at = entry
        if time.time() > expire_at:
            del self._data[key]
            self._misses += 1
            return default
        self._data.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set key with value and optional TTL (seconds)."""
        if key in self._data:
            del self._data[key]
        elif len(self._data) >= self._max_size:
            self._data.popitem(last=False)  # Evict oldest
        self._data[key] = (value, time.time() + (ttl or self._default_ttl))

    def delete(self, key: str):
        """Remove a specific key."""
        self._data.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        """Remove all keys starting with prefix."""
        keys_to_remove = [k for k in self._data if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._data[k]
        if keys_to_remove:
            logger.debug(f"Cache: invalidated {len(keys_to_remove)} keys with prefix '{prefix}'")

    def clear(self):
        """Remove all entries."""
        self._data.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache: cleared all entries")

    def cleanup_expired(self):
        """Remove all expired entries. Call periodically."""
        now = time.time()
        expired = [k for k, (_, exp) in self._data.items() if exp < now]
        for k in expired:
            del self._data[k]
        return len(expired)

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        now = time.time()
        active = sum(1 for _, (_, exp) in self._data.items() if exp > now)
        total_requests = self._hits + self._misses
        hit_rate = round(self._hits / total_requests * 100, 1) if total_requests > 0 else 0
        return {
            "total_entries": len(self._data),
            "active_entries": active,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": hit_rate,
        }

    def __contains__(self, key: str) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return False
        _, expire_at = entry
        return time.time() <= expire_at

    def __len__(self) -> int:
        return len(self._data)


# ── Global singleton ──────────────────────────────────────────
cache = MemoryCache(max_size=2000, default_ttl=300)
