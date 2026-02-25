"""
Earnings routes for the NVDA Earnings War Room.

Endpoints:
  GET /api/earnings/          — Consolidated calendar + estimates + surprises
  GET /api/earnings/calendar  — Earnings calendar only
  GET /api/earnings/estimates — Analyst estimates only
  GET /api/earnings/surprises — Earnings surprises only

All endpoints resolve data from the in-memory cache first and fall back to FMP
when the cache is cold.  Individual data fields degrade independently: for the
consolidated endpoint a 503 is only raised when ALL three sub-requests fail.
Individual sub-endpoints raise 503 when their specific data source fails.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER: str = "NVDA"

# Hardcoded NVDA earnings date — FMP calendar often omits NVDA from its
# 4,000-entry dump.  This guarantees the countdown always has a target.
_NVDA_EARNINGS_FALLBACK: dict = {
    "date": "2026-02-25",
    "symbol": "NVDA",
    "eps": None,
    "epsEstimated": None,
    "revenue": None,
    "revenueEstimated": None,
}


def _ensure_nvda_in_calendar(calendar: list[dict]) -> list[dict]:
    """If NVDA is missing from the FMP earnings calendar, inject the
    hardcoded fallback entry so the frontend countdown always works."""
    if any(entry.get("symbol") == _TICKER for entry in calendar):
        return calendar
    logger.info("NVDA not found in FMP earnings calendar — injecting fallback entry")
    return [_NVDA_EARNINGS_FALLBACK, *calendar]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_calendar(request: Request) -> list[dict] | None:
    """
    Resolve the earnings calendar, preferring the in-memory cache.

    Returns the raw FMP earnings calendar list, or None when no data is
    available from either source.
    """
    cached = await cache.get("earnings:calendar")
    if cached is not None:
        logger.debug("Earnings calendar cache hit")
        return cached

    logger.debug("Earnings calendar cache miss — fetching from FMP")
    client = request.app.state.fmp_client

    try:
        data = await client.get_earnings_calendar()
    except Exception:
        logger.exception("Unexpected error fetching earnings calendar from FMP")
        return None

    if data is not None:
        await cache.set("earnings:calendar", data, ttl=settings.cache_ttl_earnings)

    return data


async def _get_estimates(request: Request) -> list[dict] | None:
    """
    Resolve analyst estimates for NVDA, preferring the in-memory cache.

    Returns the raw FMP analyst estimates list, or None when no data is
    available from either source.
    """
    cache_key = f"earnings:estimates:{_TICKER}"
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("Earnings estimates cache hit for %s", _TICKER)
        return cached

    logger.debug("Earnings estimates cache miss for %s — fetching from FMP", _TICKER)
    client = request.app.state.fmp_client

    try:
        data = await client.get_analyst_estimates(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching analyst estimates for %s from FMP", _TICKER)
        return None

    if data is not None:
        await cache.set(cache_key, data, ttl=settings.cache_ttl_earnings)

    return data


async def _get_surprises(request: Request) -> list[dict] | None:
    """
    Resolve earnings surprises for NVDA, preferring the in-memory cache.

    Returns the raw FMP earnings surprises list, or None when no data is
    available from either source.
    """
    cache_key = f"earnings:surprises:{_TICKER}"
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("Earnings surprises cache hit for %s", _TICKER)
        return cached

    logger.debug("Earnings surprises cache miss for %s — fetching from FMP", _TICKER)
    client = request.app.state.fmp_client

    try:
        data = await client.get_earnings_surprises(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching earnings surprises for %s from FMP", _TICKER)
        return None

    if data is not None:
        await cache.set(cache_key, data, ttl=settings.cache_ttl_earnings)

    return data


# ---------------------------------------------------------------------------
# GET / — consolidated earnings data
# ---------------------------------------------------------------------------

@router.get("/", summary="Consolidated NVDA earnings data")
async def get_earnings(request: Request) -> dict:
    """
    Return a consolidated payload containing earnings calendar, analyst
    estimates, and earnings surprises for NVDA.

    Resolution order for each field:
      1. In-memory cache.
      2. FMP API via the shared FMP client.

    Individual fields degrade independently and may be None when their
    specific data source fails.  A 503 is raised only when ALL three
    sub-requests fail simultaneously.

    Raises:
        HTTPException(503): When all three data sources (calendar, estimates,
                            surprises) fail to return data.
    """
    calendar = await _get_calendar(request)
    estimates = await _get_estimates(request)
    surprises = await _get_surprises(request)

    if calendar is None and estimates is None and surprises is None:
        logger.error(
            "Earnings endpoint: all three data sources failed for %s", _TICKER
        )
        raise HTTPException(
            status_code=503,
            detail="Earnings data temporarily unavailable. Please retry shortly.",
        )

    # The consolidated endpoint returns a single NVDA calendar entry (not
    # the full list) to match the frontend EarningsConsolidated type.
    if calendar is not None:
        calendar = _ensure_nvda_in_calendar(calendar)
        nvda_entry = next(
            (e for e in calendar if e.get("symbol") == _TICKER),
            _NVDA_EARNINGS_FALLBACK,
        )
    else:
        nvda_entry = _NVDA_EARNINGS_FALLBACK

    return {
        "calendar": nvda_entry,
        "estimates": estimates,
        "surprises": surprises,
    }


# ---------------------------------------------------------------------------
# GET /calendar — earnings calendar
# ---------------------------------------------------------------------------

@router.get("/calendar", summary="NVDA earnings calendar")
async def get_earnings_calendar(request: Request) -> dict:
    """
    Return the NVDA earnings calendar.

    Resolution order:
      1. In-memory cache (key ``earnings:calendar``).
      2. FMP API via the shared FMP client.
      3. Hardcoded NVDA fallback if NVDA is missing from FMP data.

    Raises:
        HTTPException(503): When both the cache and FMP return no data.
    """
    data = await _get_calendar(request)

    if data is None:
        # Even if FMP is completely down, return the hardcoded NVDA entry
        # so the countdown still works.
        logger.warning(
            "Earnings calendar data unavailable from FMP — returning hardcoded NVDA fallback"
        )
        return {"data": [_NVDA_EARNINGS_FALLBACK]}

    return {"data": _ensure_nvda_in_calendar(data)}


# ---------------------------------------------------------------------------
# GET /estimates — analyst estimates
# ---------------------------------------------------------------------------

@router.get("/estimates", summary="NVDA analyst estimates")
async def get_earnings_estimates(request: Request) -> dict:
    """
    Return analyst estimates for NVDA.

    Resolution order:
      1. In-memory cache (key ``earnings:estimates:NVDA``).
      2. FMP API via the shared FMP client.

    Raises:
        HTTPException(503): When both the cache and FMP return no data.
    """
    data = await _get_estimates(request)

    if data is None:
        logger.error("Earnings estimates endpoint: data unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Analyst estimates data temporarily unavailable. Please retry shortly.",
        )

    return {"data": data}


# ---------------------------------------------------------------------------
# GET /surprises — earnings surprises
# ---------------------------------------------------------------------------

@router.get("/surprises", summary="NVDA earnings surprises")
async def get_earnings_surprises(request: Request) -> dict:
    """
    Return earnings surprises for NVDA.

    Resolution order:
      1. In-memory cache (key ``earnings:surprises:NVDA``).
      2. FMP API via the shared FMP client.

    Raises:
        HTTPException(503): When both the cache and FMP return no data.
    """
    data = await _get_surprises(request)

    if data is None:
        logger.error("Earnings surprises endpoint: data unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Earnings surprises data temporarily unavailable. Please retry shortly.",
        )

    return {"data": data}
