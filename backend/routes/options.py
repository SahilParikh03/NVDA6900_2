"""
Options / Polymarket routes for the NVDA Earnings War Room.

Endpoints:
  GET /api/options/heatmap       — Polymarket probability heatmap (replaces GEX)
  GET /api/options/supplementary — Non-price-level NVDA prediction markets

After FMP dropped options chain data entirely, Polymarket binary prediction
markets serve as the replacement data source for the GEX Heatmap panel.
The heatmap endpoint returns strike-level implied probabilities, key conviction
levels, and aggregate market data.

All endpoints degrade gracefully: a 503 is returned when data cannot be
obtained from either source.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.config import settings
from backend.engines.polymarket_engine import analyze_polymarket

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER: str = "NVDA"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_polymarket_data(request: Request) -> list[dict] | None:
    """
    Resolve Polymarket NVDA markets, preferring the in-memory cache.

    Returns the raw list of market dicts, or None when no data is available.
    """
    cached = await cache.get(f"polymarket:{_TICKER}")
    if cached is not None:
        logger.debug("Polymarket cache hit for %s", _TICKER)
        return cached

    logger.debug("Polymarket cache miss for %s — fetching from API", _TICKER)
    client = request.app.state.polymarket_client

    try:
        markets = await client.search_markets(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching Polymarket markets for %s", _TICKER)
        return None

    if markets is not None:
        await cache.set(f"polymarket:{_TICKER}", markets, ttl=settings.cache_ttl_polymarket)

    return markets


# ---------------------------------------------------------------------------
# GET /heatmap — Polymarket probability heatmap (replaces GEX)
# ---------------------------------------------------------------------------

@router.get("/heatmap", summary="Polymarket probability heatmap for NVDA price levels")
async def get_heatmap(request: Request) -> dict:
    """
    Return a probability heatmap derived from Polymarket prediction markets.

    This replaces the former GEX (Gamma Exposure) endpoint. Instead of
    options-derived gamma, it returns:
      - Per-strike implied probabilities from binary YES/NO markets
      - Key conviction levels (max, 50%, low)
      - Supplementary non-price-level markets (earnings beat/miss, etc.)
      - Aggregate volume and market count

    Resolution:
      1. Raw market data from in-memory cache (key ``polymarket:NVDA``).
      2. Polymarket Gamma API via the shared PolymarketClient.
      3. Raw data passed to ``analyze_polymarket()`` from the engine.

    Raises:
        HTTPException(503): When data cannot be obtained or engine fails.
    """
    markets = await _get_polymarket_data(request)
    if markets is None:
        logger.error("Heatmap endpoint: Polymarket data unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Polymarket data temporarily unavailable. Please retry shortly.",
        )

    try:
        result = await analyze_polymarket(markets)
    except Exception:
        logger.exception("Polymarket engine raised an unexpected exception for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Polymarket analysis failed. Please retry shortly.",
        )

    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /supplementary — non-price NVDA prediction markets
# ---------------------------------------------------------------------------

@router.get("/supplementary", summary="Supplementary NVDA prediction markets")
async def get_supplementary(request: Request) -> dict:
    """
    Return non-price-level NVDA prediction markets (earnings beat/miss, etc.).

    This is a convenience endpoint that extracts only the supplementary
    markets from the full Polymarket analysis.

    Raises:
        HTTPException(503): When data cannot be obtained or engine fails.
    """
    markets = await _get_polymarket_data(request)
    if markets is None:
        logger.error("Supplementary endpoint: Polymarket data unavailable for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Polymarket data temporarily unavailable. Please retry shortly.",
        )

    try:
        result = await analyze_polymarket(markets)
    except Exception:
        logger.exception("Polymarket engine raised an unexpected exception for %s", _TICKER)
        raise HTTPException(
            status_code=503,
            detail="Polymarket analysis failed. Please retry shortly.",
        )

    return {
        "supplementary": [m.model_dump() for m in result.supplementary],
        "market_count": result.market_count,
        "last_updated": result.last_updated,
    }
