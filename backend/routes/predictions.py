"""
Predictions route module for the NVDA Earnings War Room.

Provides one endpoint:
  GET /api/predictions/ -- Synthesised qualitative outlook for NVDA

The outlook is a rule-based synthesis (NOT AI-generated) combining:
  - Price action (changePercentage)
  - Polymarket prediction market positioning
  - Twitter/X social sentiment score
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter()

PRICE_BULLISH_THRESHOLD: float = 2.0
PRICE_BEARISH_THRESHOLD: float = -2.0
SENTIMENT_BULLISH_THRESHOLD: float = 20.0
SENTIMENT_BEARISH_THRESHOLD: float = -20.0
CONFIDENCE_HIGH_RATIO: float = 1.0
CONFIDENCE_MODERATE_RATIO: float = 0.5
@router.get("/")
async def get_predictions(request: Request) -> dict[str, Any]:
    """
    Return a synthesised qualitative outlook for NVDA.

    Gathers cached data across price, polymarket, and sentiment, then
    applies deterministic rules to produce bullish / neutral / bearish signals.
    Graceful degradation: each signal is independently guarded -- if a data
    source or engine call fails, that signal is simply omitted.

    Returns HTTP 503 only when NO data is available whatsoever.
    """
    price_data: list[dict] | None = await cache.get("price:NVDA")
    polymarket_data: list[dict] | None = await cache.get("polymarket:NVDA")
    sentiment_data: list[dict] | None = await cache.get("sentiment:NVDA")

    any_data_available = any(
        d is not None for d in [price_data, polymarket_data, sentiment_data]
    )

    if not any_data_available:
        logger.warning("No NVDA data available in cache for predictions endpoint")
        raise HTTPException(
            status_code=503,
            detail="Prediction data temporarily unavailable",
        )

    signals: list[dict[str, str]] = []

    if price_data:
        try:
            _build_price_signal(price_data, signals)
        except Exception as exc:
            logger.error("Price signal generation failed: %s", exc)

    if polymarket_data:
        try:
            await _build_polymarket_signal(polymarket_data, signals)
        except Exception as exc:
            logger.error("Polymarket signal generation failed: %s", exc)

    if sentiment_data:
        try:
            await _build_sentiment_signal(sentiment_data, signals)
        except Exception as exc:
            logger.error("Sentiment signal generation failed: %s", exc)

    bullish_count = sum(1 for s in signals if s["direction"] == "bullish")
    bearish_count = sum(1 for s in signals if s["direction"] == "bearish")
    total_signals = len(signals)

    if bullish_count > bearish_count:
        outlook = "Bullish"
    elif bearish_count > bullish_count:
        outlook = "Bearish"
    else:
        outlook = "Neutral"

    if total_signals == 0:
        confidence = "low"
    else:
        dominant = max(bullish_count, bearish_count)
        ratio = dominant / total_signals
        if ratio >= CONFIDENCE_HIGH_RATIO:
            confidence = "high"
        elif ratio > CONFIDENCE_MODERATE_RATIO:
            confidence = "moderate"
        else:
            confidence = "low"

    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info(
        "Predictions: outlook=%s confidence=%s bullish=%d bearish=%d total=%d",
        outlook, confidence, bullish_count, bearish_count, total_signals,
    )

    return {
        "outlook": outlook,
        "confidence": confidence,
        "signals": signals,
        "last_updated": last_updated,
    }

def _build_price_signal(
    price_data: list[dict],
    signals: list[dict[str, str]],
) -> None:
    """
    Append a price-action signal based on changePercentage.

    Uses the first element of the price data list (most recent quote).
    No signal is appended if the required field is missing or cannot be cast
    to float.
    """
    if not price_data:
        return

    quote = price_data[0] if isinstance(price_data, list) else price_data
    if not isinstance(quote, dict):
        logger.warning("Price data element is not a dict: %r", type(quote))
        return

    raw_change = quote.get("changePercentage")
    if raw_change is None:
        logger.debug("changePercentage missing from price data -- skipping price signal")
        return

    try:
        change_pct = float(raw_change)
    except (TypeError, ValueError):
        logger.warning(
            "Cannot cast changePercentage to float: %r -- skipping price signal",
            raw_change,
        )
        return

    if change_pct > PRICE_BULLISH_THRESHOLD:
        signals.append(
            {
                "factor": "Price Action",
                "direction": "bullish",
                "detail": f"NVDA up {change_pct:.1f}% today",
            }
        )
        logger.debug("Price signal: bullish (%.2f%%)", change_pct)
    elif change_pct < PRICE_BEARISH_THRESHOLD:
        signals.append(
            {
                "factor": "Price Action",
                "direction": "bearish",
                "detail": f"NVDA down {abs(change_pct):.1f}% today",
            }
        )
        logger.debug("Price signal: bearish (%.2f%%)", change_pct)
    else:
        logger.debug("Price signal: neutral (%.2f%%) -- no signal appended", change_pct)

async def _build_polymarket_signal(
    polymarket_data: list[dict],
    signals: list[dict[str, str]],
) -> None:
    """
    Append a market positioning signal from Polymarket probability data.

    Uses the max_conviction level and the number of active price-level
    markets to determine if the prediction market is bullish or bearish.
    """
    from backend.engines.polymarket_engine import analyze_polymarket

    try:
        result = await analyze_polymarket(polymarket_data)

        if not result.price_levels:
            logger.debug("No Polymarket price levels -- skipping signal")
            return

        key = result.key_levels
        if key.max_conviction is not None and key.fifty_percent_level is not None:
            if key.max_conviction > key.fifty_percent_level:
                signals.append(
                    {
                        "factor": "Prediction Markets",
                        "direction": "bullish",
                        "detail": (
                            f"Max conviction at ${key.max_conviction:.0f}, "
                            f"market-expected level at ${key.fifty_percent_level:.0f}"
                        ),
                    }
                )
                logger.debug(
                    "Polymarket signal: bullish (max=%.0f > fifty=%.0f)",
                    key.max_conviction,
                    key.fifty_percent_level,
                )
            else:
                signals.append(
                    {
                        "factor": "Prediction Markets",
                        "direction": "bearish",
                        "detail": (
                            f"Max conviction at ${key.max_conviction:.0f}, "
                            f"market-expected level at ${key.fifty_percent_level:.0f}"
                        ),
                    }
                )
                logger.debug(
                    "Polymarket signal: bearish (max=%.0f <= fifty=%.0f)",
                    key.max_conviction,
                    key.fifty_percent_level,
                )
    except Exception as exc:
        logger.error("analyze_polymarket raised during predictions: %s", exc)

async def _build_sentiment_signal(
    tweet_data: list[dict],
    signals: list[dict[str, str]],
) -> None:
    """
    Append a sentiment signal based on Twitter/X sentiment analysis.
    """
    from backend.engines.sentiment_engine import process_twitter_sentiment

    try:
        sentiment_result = await process_twitter_sentiment(tweet_data)
        score = sentiment_result.current_score
        direction_label = sentiment_result.roc_direction

        if score > SENTIMENT_BULLISH_THRESHOLD:
            signals.append(
                {
                    "factor": "Sentiment",
                    "direction": "bullish",
                    "detail": f"Twitter score +{score:.0f}, {direction_label}",
                }
            )
            logger.debug("Sentiment signal: bullish (score=%.1f)", score)
        elif score < SENTIMENT_BEARISH_THRESHOLD:
            signals.append(
                {
                    "factor": "Sentiment",
                    "direction": "bearish",
                    "detail": f"Twitter score {score:.0f}, {direction_label}",
                }
            )
            logger.debug("Sentiment signal: bearish (score=%.1f)", score)
        else:
            logger.debug(
                "Sentiment signal: neutral (score=%.1f) -- no signal appended", score
            )
    except Exception as exc:
        logger.error("process_twitter_sentiment raised during predictions: %s", exc)
