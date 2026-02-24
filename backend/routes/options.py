"""
Options routes for the NVDA Earnings War Room.

Endpoints:
  GET /api/options/gex      — Gamma Exposure calculation across all strikes
  GET /api/options/unusual  — Unusual options activity scan

Both endpoints resolve the options chain from the in-memory cache first and
fall back to FMP when the cache is cold.  The current NVDA spot price
required by the GEX engine is resolved the same way.

All endpoints degrade gracefully: a 503 is returned when data cannot be
obtained from either source.  Calculation errors inside the engines are also
caught and surfaced as 503s so the rest of the dashboard keeps working.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.config import settings
from backend.engines.gex_engine import calculate_gex
from backend.engines.unusual_activity import scan_unusual_activity

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER: str = "NVDA"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_options_chain(request: Request) -> list[dict] | None:
    """
    Resolve the NVDA options chain, preferring the in-memory cache.

    Returns the raw FMP options chain list, or None when no data is available
    from either source.
    """
    cached = await cache.get(f"options:{_TICKER}")
    if cached is not None:
        logger.debug("Options chain cache hit for %s", _TICKER)
        return cached

    logger.debug("Options chain cache miss for %s — fetching from FMP", _TICKER)
    client = request.app.state.fmp_client

    try:
        chain = await client.get_options_chain(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching options chain for %s", _TICKER)
        return None

    if chain is not None:
        await cache.set(f"options:{_TICKER}", chain, ttl=settings.cache_ttl_options)

    return chain


async def _get_current_price(request: Request) -> float | None:
    """
    Resolve the current NVDA spot price, preferring the in-memory cache.

    Extracts ``quote[0]["price"]`` from the cached or freshly-fetched quote.
    Returns None when no price is obtainable.
    """
    cached = await cache.get(f"price:{_TICKER}")
    quote: list[dict] | None = cached

    if quote is None:
        logger.debug("Price cache miss for %s — fetching from FMP for options route", _TICKER)
        client = request.app.state.fmp_client
        try:
            quote = await client.get_quote(_TICKER)
        except Exception:
            logger.exception("Unexpected error fetching quote for %s (options route)", _TICKER)
            return None

        if quote is not None:
            await cache.set(f"price:{_TICKER}", quote, ttl=settings.cache_ttl_price)

    if not quote or not isinstance(quote, list) or len(quote) == 0:
        logger.error("Could not resolve price for %s — quote is empty or invalid", _TICKER)
        return None

    price_raw = quote[0].get("price")
    if price_raw is None:
        logger.error("Quote for %s has no 'price' field: %r", _TICKER, quote[0])
        return None

    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        logger.error("Non-numeric price in quote for %s: %r", _TICKER, price_raw)
        return None

    if price <= 0:
        logger.error("Non-positive price for %s: %.4f", _TICKER, price)
        return None

    return price


# ---------------------------------------------------------------------------
# GET /gex
# ---------------------------------------------------------------------------

@router.get("/gex", summary="Gamma Exposure (GEX) across all NVDA option strikes")
async def get_gex(request: Request) -> dict:
    """
    Compute Gamma Exposure for every live NVDA option strike.

    Resolution:
      1. Options chain — from ``cache.get("options:NVDA")`` or FMP fallback.
      2. Spot price    — from ``cache.get("price:NVDA")``  or FMP fallback,
                         extracted as ``quote[0]["price"]``.
      3. Both are passed to ``calculate_gex(chain, price)``; the resulting
         ``GexResult`` is serialised via ``.model_dump()`` and returned.

    Raises:
        HTTPException(503): When the options chain or price cannot be obtained,
                            or when the engine raises an unexpected exception.
    """
    chain = await _get_options_chain(request)
    if chain is None:
        logger.error("GEX endpoint: options chain unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Options chain data temporarily unavailable. Please retry shortly.",
        )

    price = await _get_current_price(request)
    if price is None:
        logger.error("GEX endpoint: current price unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Current price data temporarily unavailable. Please retry shortly.",
        )

    try:
        result = await calculate_gex(chain, price)
    except Exception:
        logger.exception("GEX engine raised an unexpected exception for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="GEX calculation failed. Please retry shortly.",
        )

    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /unusual
# ---------------------------------------------------------------------------

@router.get("/unusual", summary="Unusual options activity for NVDA")
async def get_unusual_activity(request: Request) -> dict:
    """
    Scan the NVDA options chain for contracts with abnormally high volume/OI.

    Resolution:
      1. Options chain — from ``cache.get("options:NVDA")`` or FMP fallback.
      2. Passed to ``scan_unusual_activity(chain)``; the resulting
         ``UnusualActivityResult`` is serialised via ``.model_dump()``.

    Raises:
        HTTPException(503): When the options chain cannot be obtained, or when
                            the engine raises an unexpected exception.
    """
    chain = await _get_options_chain(request)
    if chain is None:
        logger.error("Unusual activity endpoint: options chain unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Options chain data temporarily unavailable. Please retry shortly.",
        )

    try:
        result = await scan_unusual_activity(chain)
    except Exception:
        logger.exception(
            "Unusual activity engine raised an unexpected exception for %s", _TICKER
        )
        raise HTTPException(
            status_code=503,
            detail="Unusual activity scan failed. Please retry shortly.",
        )

    return result.model_dump()
