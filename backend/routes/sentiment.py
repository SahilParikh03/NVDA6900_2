"""
Sentiment routes for the NVDA Earnings War Room.

Endpoints:
  GET /api/sentiment/      — Processed sentiment analysis (composite score, label, ROC)
  GET /api/sentiment/news  — Recent NVDA news articles

The root endpoint resolves raw social sentiment data from the in-memory cache
or FMP, passes it through the sentiment engine, and returns the processed
SentimentResult.  The news endpoint calls FMP directly on every request.

All endpoints degrade gracefully: a 503 is returned when data cannot be
obtained.  Engine errors are caught and surfaced as 503s so the rest of the
dashboard keeps working.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.config import settings
from backend.engines.sentiment_engine import process_sentiment, SentimentResult

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER: str = "NVDA"
_NEWS_LIMIT: int = 50


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_raw_sentiment(request: Request) -> list[dict] | None:
    """
    Resolve raw social sentiment data for NVDA, preferring the in-memory cache.

    Returns the raw FMP social sentiment list, or None when no data is
    available from either source.
    """
    cache_key = f"sentiment:{_TICKER}"
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("Sentiment cache hit for %s", _TICKER)
        return cached

    logger.debug("Sentiment cache miss for %s — fetching from FMP", _TICKER)
    client = request.app.state.fmp_client

    try:
        data = await client.get_social_sentiment(_TICKER)
    except Exception:
        logger.exception("Unexpected error fetching social sentiment for %s from FMP", _TICKER)
        return None

    if data is not None:
        await cache.set(cache_key, data, ttl=settings.cache_ttl_sentiment)

    return data


# ---------------------------------------------------------------------------
# GET / — processed sentiment
# ---------------------------------------------------------------------------

@router.get("/", summary="Processed NVDA social sentiment analysis")
async def get_sentiment(request: Request) -> dict:
    """
    Return processed social sentiment analysis for NVDA.

    Resolution order:
      1. Raw sentiment data from in-memory cache (key ``sentiment:NVDA``).
      2. FMP ``/v4/social-sentiment`` via the shared FMP client.
      3. Raw data passed to ``process_sentiment()`` from the sentiment engine.

    The engine handles empty data gracefully by returning neutral defaults,
    so a 503 is only raised when no raw data can be obtained at all.

    Raises:
        HTTPException(503): When both the cache and FMP return no data,
                            or when the sentiment engine raises an unexpected
                            exception.
    """
    raw_data = await _get_raw_sentiment(request)

    if raw_data is None:
        logger.error(
            "Sentiment endpoint: raw data unavailable for %s — cache miss and FMP returned None",
            _TICKER,
        )
        raise HTTPException(
            status_code=503,
            detail="Sentiment data temporarily unavailable. Please retry shortly.",
        )

    try:
        result: SentimentResult = await process_sentiment(raw_data)
    except Exception:
        logger.exception(
            "Sentiment engine raised an unexpected exception for %s", _TICKER
        )
        raise HTTPException(
            status_code=503,
            detail="Sentiment processing failed. Please retry shortly.",
        )

    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /news — recent NVDA news
# ---------------------------------------------------------------------------

@router.get("/news", summary="Recent NVDA news articles")
async def get_news(request: Request) -> dict:
    """
    Return the most recent NVDA news articles.

    Calls FMP ``/v3/stock_news`` directly on every request with a limit of
    50 articles.  News is intentionally not cached at the route layer because
    freshness is critical and the scheduler manages any background prefetching.

    Raises:
        HTTPException(503): When FMP returns no data.
    """
    client = request.app.state.fmp_client

    try:
        news = await client.get_stock_news(_TICKER, limit=_NEWS_LIMIT)
    except Exception:
        logger.exception("Unexpected error fetching stock news for %s from FMP", _TICKER)
        news = None

    if not news:
        logger.error(
            "News endpoint: data unavailable for %s — FMP returned None or empty list",
            _TICKER,
        )
        raise HTTPException(
            status_code=503,
            detail="News data temporarily unavailable. Please retry shortly.",
        )

    return {"data": news}
