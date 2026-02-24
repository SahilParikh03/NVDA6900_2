"""
In-memory TTL cache with an async interface.

Sits between the FMP API client and the rest of the application.
Provides lazy expiration: expired entries are removed on access, not on a
background schedule.

Usage:
    from backend.cache import cache            # module-level singleton
    from backend.cache import TTLCache         # for fresh instances in tests
"""

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """Async-compatible in-memory key-value store with per-entry TTL.

    Storage layout:
        _store: dict[str, tuple[Any, float]]
            key -> (value, expiry_timestamp)

    Expiration is lazy: entries are removed the first time an expired key is
    accessed via ``get()``.  No background cleanup task is started.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key* if it exists and has not expired.

        If the entry is found but its TTL has elapsed, the entry is deleted
        from the internal store before returning ``None``.

        Args:
            key: Cache key to look up.

        Returns:
            The cached value, or ``None`` if the key is absent or expired.
        """
        entry = self._store.get(key)
        if entry is None:
            logger.debug("Cache miss (not found): key=%r", key)
            return None

        value, expiry = entry
        if time.time() < expiry:
            logger.debug("Cache hit: key=%r", key)
            return value

        # Lazy expiration: remove the stale entry now.
        del self._store[key]
        logger.debug("Cache miss (expired): key=%r", key)
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Store *value* under *key* with a time-to-live of *ttl* seconds.

        Overwrites any existing entry for *key*.

        Args:
            key:   Cache key.
            value: Arbitrary value to store.  May be any Python object.
            ttl:   Seconds until the entry expires.  Must be a positive integer.
        """
        expiry: float = time.time() + ttl
        self._store[key] = (value, expiry)
        logger.debug("Cache set: key=%r  ttl=%ds  expires_at=%.3f", key, ttl, expiry)

    async def delete(self, key: str) -> None:
        """Remove *key* from the cache.

        A no-op if the key does not exist.

        Args:
            key: Cache key to remove.
        """
        removed = self._store.pop(key, None)
        if removed is not None:
            logger.debug("Cache delete: key=%r", key)
        else:
            logger.debug("Cache delete (not found): key=%r", key)

    async def clear(self) -> None:
        """Remove all entries from the cache."""
        count = len(self._store)
        self._store.clear()
        logger.debug("Cache cleared: removed %d entries", count)

    def size(self) -> int:
        """Return the number of entries currently in the store.

        This count includes entries whose TTL has already elapsed but that
        have not yet been lazily removed via a ``get()`` call.

        Returns:
            Integer count of stored entries.
        """
        return len(self._store)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
# Other modules import this instance directly:
#   from backend.cache import cache
cache = TTLCache()
