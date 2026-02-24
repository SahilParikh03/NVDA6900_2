"""
Price routes for the NVDA Earnings War Room.

Endpoints:
  GET /api/price/         — Current NVDA quote (cache-first, FMP fallback)
  GET /api/price/history  — Historical OHLCV data (direct FMP call)
  GET /api/price/change   — Price performance across multiple periods (direct FMP call)

All endpoints degrade gracefully: a 503 is returned when both the cache and
the FMP API are unable to supply data. The application never crashes on a
missing or malformed response.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Ticker is always NVDA for this project.
_TICKER: str = "NVDA"


# ---------------------------------------------------------------------------
# GET / — current quote
# ---------------------------------------------------------------------------

@router.get("/", summary="Current NVDA quote")
async def get_price(request: Request) -> dict:
    """
    Return the current NVDA price data.

    Resolution order:
      1. In-memory cache (key ``price:NVDA``).
      2. FMP ``/v3/quote/NVDA`` via the shared FMP client.

    On success the raw FMP quote list is returned unchanged so the frontend
    always receives the same shape regardless of the data source.

    Raises:
        HTTPException(503): When both the cache and FMP return no data.
    """
    cached = await cache.get(f"price:{_TICKER}")
    if cached is not None:
        logger.debug("Price cache hit for %s", _TICKER)
        return {"source": "cache", "data": cached}

    logger.debug("Price cache miss for %s — fetching from FMP", _TICKER)
    client = request.app.state.fmp_client

    try:
        quote = await client.get_quote(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching quote for %s", _TICKER)
        quote = None

    if not quote:
        logger.error("Price unavailable for %s — cache miss and FMP returned None", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Price data temporarily unavailable. Please retry shortly.",
        )

    # Populate cache so the next request within the TTL window is served locally.
    await cache.set(f"price:{_TICKER}", quote, ttl=settings.cache_ttl_price)

    return {"source": "fmp", "data": quote}


# ---------------------------------------------------------------------------
# GET /history — historical OHLCV
# ---------------------------------------------------------------------------

@router.get("/history", summary="Historical OHLCV data")
async def get_price_history(request: Request) -> dict:
    """
    Return historical OHLCV (Open/High/Low/Close/Volume) data for NVDA.

    This endpoint calls FMP directly on every request — the full historical
    dataset is large and changes infrequently enough that caching is handled
    at the scheduler layer, not here.

    Raises:
        HTTPException(503): When FMP returns no data.
    """
    client = request.app.state.fmp_client

    try:
        history = await client.get_historical_price(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching historical price for %s", _TICKER)
        history = None

    if not history:
        logger.error("Historical price unavailable for %s — FMP returned None", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Historical price data temporarily unavailable. Please retry shortly.",
        )

    return history


# ---------------------------------------------------------------------------
# GET /change — price performance across periods
# ---------------------------------------------------------------------------

@router.get("/change", summary="Price performance across time periods")
async def get_price_change(request: Request) -> dict:
    """
    Return NVDA price performance across standard time periods (1D, 5D, 1M, …).

    Calls the FMP ``/v3/stock-price-change/NVDA`` endpoint directly.

    Raises:
        HTTPException(503): When FMP returns no data.
    """
    client = request.app.state.fmp_client

    try:
        change_data = await client.get_stock_price_change(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching price change for %s", _TICKER)
        change_data = None

    if not change_data:
        logger.error("Price change data unavailable for %s — FMP returned None", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Price change data temporarily unavailable. Please retry shortly.",
        )

    # FMP returns a list; return the first element if present so callers get
    # a single flat object, but keep the raw list shape as a fallback.
    if isinstance(change_data, list) and len(change_data) > 0:
        return {"data": change_data[0]}

    return {"data": change_data}
