"""
Tests for backend.cache.TTLCache.

Each test creates a fresh TTLCache instance so the module-level singleton is
never touched and tests remain fully isolated.

Run with:
    pytest backend/tests/test_cache.py -v
"""

import asyncio
import time

import pytest

from backend.cache import TTLCache


# ---------------------------------------------------------------------------
# 1. Basic set / get round-trip
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_set_and_get() -> None:
    """A value stored with set() must be retrievable with get()."""
    c = TTLCache()
    await c.set("key1", {"price": 875.42}, ttl=60)
    result = await c.get("key1")
    assert result == {"price": 875.42}


# ---------------------------------------------------------------------------
# 2. Missing key returns None
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_missing_key() -> None:
    """get() on a key that was never set must return None."""
    c = TTLCache()
    result = await c.get("does_not_exist")
    assert result is None


# ---------------------------------------------------------------------------
# 3. Expired entry returns None
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_expired_entry_returns_none() -> None:
    """After TTL elapses, get() must return None for the expired key."""
    c = TTLCache()
    await c.set("short_lived", "temporary", ttl=1)
    await asyncio.sleep(1.1)
    result = await c.get("short_lived")
    assert result is None


# ---------------------------------------------------------------------------
# 4. Overwriting an existing key
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_overwrite_existing_key() -> None:
    """set() called twice on the same key must return the second value."""
    c = TTLCache()
    await c.set("ticker", "NVDA_v1", ttl=60)
    await c.set("ticker", "NVDA_v2", ttl=60)
    result = await c.get("ticker")
    assert result == "NVDA_v2"


# ---------------------------------------------------------------------------
# 5. Delete removes a key
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_key() -> None:
    """delete() must cause subsequent get() to return None."""
    c = TTLCache()
    await c.set("to_delete", 42, ttl=60)
    await c.delete("to_delete")
    result = await c.get("to_delete")
    assert result is None


# ---------------------------------------------------------------------------
# 6. Delete on a non-existent key does not raise
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_nonexistent_key() -> None:
    """delete() on a missing key must complete without raising any exception."""
    c = TTLCache()
    try:
        await c.delete("ghost_key")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"delete() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# 7. clear() removes all entries
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_clear_removes_all() -> None:
    """After clear(), get() must return None for every previously stored key."""
    c = TTLCache()
    keys = ["alpha", "beta", "gamma"]
    for k in keys:
        await c.set(k, k.upper(), ttl=60)

    await c.clear()

    for k in keys:
        assert await c.get(k) is None, f"Expected None for key {k!r} after clear()"


# ---------------------------------------------------------------------------
# 8. size() reflects the number of stored entries
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_size() -> None:
    """size() must return the number of entries currently held in the store."""
    c = TTLCache()
    assert c.size() == 0

    await c.set("a", 1, ttl=60)
    await c.set("b", 2, ttl=60)
    await c.set("c", 3, ttl=60)

    assert c.size() == 3


# ---------------------------------------------------------------------------
# 9. Different TTLs — short TTL expires first
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_different_ttls() -> None:
    """A key with ttl=1 must expire before a key with ttl=60."""
    c = TTLCache()
    await c.set("fast", "soon_gone", ttl=1)
    await c.set("slow", "still_here", ttl=60)

    await asyncio.sleep(1.1)

    assert await c.get("fast") is None, "fast key should have expired"
    assert await c.get("slow") == "still_here", "slow key should still be valid"


# ---------------------------------------------------------------------------
# 10. Expired entry is cleaned from the internal dict on get()
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_expired_entry_is_cleaned_on_get() -> None:
    """get() on an expired key must remove the entry from the internal store."""
    c = TTLCache()
    await c.set("cleanup_me", "value", ttl=1)

    # Before expiry the entry is present.
    assert c.size() == 1

    await asyncio.sleep(1.1)

    # Trigger lazy cleanup via get().
    result = await c.get("cleanup_me")
    assert result is None

    # The internal dict must now be empty.
    assert c.size() == 0, (
        "Expired entry was not cleaned from _store after get() returned None"
    )
