"""
Sentiment routes for the NVDA Earnings War Room.

Endpoints:
  GET /api/sentiment/      — Processed Twitter/X sentiment analysis
  GET /api/sentiment/news  — Recent NVDA news articles from FMP

The root endpoint resolves raw tweet data from the in-memory cache or
SocialData.tools, passes it through the Twitter sentiment engine, and
returns the processed SentimentResult.

All endpoints degrade gracefully: a 503 is returned when data cannot
be obtained.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.config import settings
from backend.engines.sentiment_engine import process_twitter_sentiment, SentimentResult

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER: str = "NVDA"
_NEWS_LIMIT: int = 50


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_tweets(request: Request) -> list[dict] | None:
    """
    Resolve raw NVDA tweets, preferring the in-memory cache.

    Returns the raw tweet list, or None when no data is available
    from either source.
    """
    cache_key = f"sentiment:{_TICKER}"
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("Sentiment cache hit for %s", _TICKER)
        return cached

    logger.debug("Sentiment cache miss for %s — fetching from SocialData", _TICKER)
    client = request.app.state.socialdata_client

    try:
        tweets = await client.search_tweets(f"${_TICKER}")
    except Exception:
        logger.exception("Unexpected error fetching tweets for %s from SocialData", _TICKER)
        return None

    if tweets is not None:
        await cache.set(cache_key, tweets, ttl=settings.cache_ttl_social)

    return tweets


# ---------------------------------------------------------------------------
# GET / — processed sentiment from Twitter/X
# ---------------------------------------------------------------------------

@router.get("/", summary="Processed NVDA social sentiment analysis from Twitter/X")
async def get_sentiment(request: Request) -> dict:
    """
    Return processed social sentiment analysis for NVDA.

    Resolution order:
      1. Raw tweet data from in-memory cache (key ``sentiment:NVDA``).
      2. SocialData.tools Twitter search via the shared SocialDataClient.
      3. Raw tweets passed to ``process_twitter_sentiment()`` from the engine.

    The engine handles empty data gracefully by returning neutral defaults,
    so a 503 is only raised when no raw data can be obtained at all.

    Raises:
        HTTPException(503): When both the cache and SocialData return no data,
                            or when the sentiment engine raises an unexpected
                            exception.
    """
    tweets = await _get_tweets(request)

    if tweets is None:
        logger.error(
            "Sentiment endpoint: tweet data unavailable for %s — cache miss and SocialData returned None",
            _TICKER,
        )
        raise HTTPException(
            status_code=503,
            detail="Sentiment data temporarily unavailable. Please retry shortly.",
        )

    try:
        result: SentimentResult = await process_twitter_sentiment(tweets)
    except Exception:
        logger.exception(
            "Twitter sentiment engine raised an unexpected exception for %s", _TICKER
        )
        raise HTTPException(
            status_code=503,
            detail="Sentiment processing failed. Please retry shortly.",
        )

    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /news — recent NVDA news (still from FMP — working endpoint)
# ---------------------------------------------------------------------------

@router.get("/news", summary="Recent NVDA news articles")
async def get_news(request: Request) -> dict:
    """
    Return the most recent NVDA news articles from FMP.

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
