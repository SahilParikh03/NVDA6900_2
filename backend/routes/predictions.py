"""
Predictions route module for the NVDA Earnings War Room.

Provides one endpoint:
  GET /api/predictions/ — Synthesised qualitative outlook for NVDA

The outlook is a rule-based synthesis (NOT AI-generated) combining:
  - Price action (changesPercentage)
  - Options positioning (GEX + unusual activity)
  - Social sentiment score
  - Earnings surprise history
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

PRICE_BULLISH_THRESHOLD: float = 2.0    # changesPercentage > 2% → bullish
PRICE_BEARISH_THRESHOLD: float = -2.0   # changesPercentage < -2% → bearish
GEX_BULLISH_THRESHOLD: float = 0.0      # total_gex > 0 → bullish
PCR_BEARISH_THRESHOLD: float = 1.0      # put_call_ratio_unusual > 1 → bearish
SENTIMENT_BULLISH_THRESHOLD: float = 20.0
SENTIMENT_BEARISH_THRESHOLD: float = -20.0
EARNINGS_BEAT_RATIO: float = 0.75       # > 75% beats in last 4 quarters → bullish
EARNINGS_LOOKBACK: int = 4              # number of recent quarters to inspect

# Confidence thresholds
CONFIDENCE_HIGH_RATIO: float = 1.0     # all signals agree
CONFIDENCE_MODERATE_RATIO: float = 0.5  # strict majority agrees


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get("/")
async def get_predictions(request: Request) -> dict[str, Any]:
    """
    Return a synthesised qualitative outlook for NVDA.

    Gathers cached data across price, options, sentiment, and earnings, then
    applies deterministic rules to produce bullish / neutral / bearish signals.
    Graceful degradation: each signal is independently guarded — if a data
    source or engine call fails, that signal is simply omitted.

    Returns HTTP 503 only when NO data is available whatsoever.
    """
    # -----------------------------------------------------------------------
    # Gather cache data
    # -----------------------------------------------------------------------
    price_data: list[dict] | None = await cache.get("price:NVDA")
    options_data: list[dict] | None = await cache.get("options:NVDA")
    sentiment_data: list[dict] | None = await cache.get("sentiment:NVDA")
    surprises_data: list[dict] | None = await cache.get("earnings:surprises:NVDA")

    any_data_available = any(
        d is not None for d in [price_data, options_data, sentiment_data, surprises_data]
    )

    if not any_data_available:
        logger.warning("No NVDA data available in cache for predictions endpoint")
        raise HTTPException(
            status_code=503,
            detail="Prediction data temporarily unavailable",
        )

    signals: list[dict[str, str]] = []

    # -----------------------------------------------------------------------
    # Signal 1: Price action
    # -----------------------------------------------------------------------
    if price_data:
        try:
            _build_price_signal(price_data, signals)
        except Exception as exc:
            logger.error("Price signal generation failed: %s", exc)

    # -----------------------------------------------------------------------
    # Signal 2: Options positioning (GEX + unusual activity)
    # -----------------------------------------------------------------------
    if options_data:
        try:
            await _build_options_signals(options_data, price_data, signals)
        except Exception as exc:
            logger.error("Options signal generation failed: %s", exc)

    # -----------------------------------------------------------------------
    # Signal 3: Sentiment
    # -----------------------------------------------------------------------
    if sentiment_data:
        try:
            await _build_sentiment_signal(sentiment_data, signals)
        except Exception as exc:
            logger.error("Sentiment signal generation failed: %s", exc)

    # -----------------------------------------------------------------------
    # Signal 4: Earnings history
    # -----------------------------------------------------------------------
    if surprises_data:
        try:
            _build_earnings_signal(surprises_data, signals)
        except Exception as exc:
            logger.error("Earnings history signal generation failed: %s", exc)

    # -----------------------------------------------------------------------
    # Synthesise outlook
    # -----------------------------------------------------------------------
    bullish_count = sum(1 for s in signals if s["direction"] == "bullish")
    bearish_count = sum(1 for s in signals if s["direction"] == "bearish")
    total_signals = len(signals)

    if bullish_count > bearish_count:
        outlook = "Bullish"
    elif bearish_count > bullish_count:
        outlook = "Bearish"
    else:
        outlook = "Neutral"

    # Confidence
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
        outlook,
        confidence,
        bullish_count,
        bearish_count,
        total_signals,
    )

    return {
        "outlook": outlook,
        "confidence": confidence,
        "signals": signals,
        "last_updated": last_updated,
    }


# ---------------------------------------------------------------------------
# Internal signal builders
# ---------------------------------------------------------------------------


def _build_price_signal(
    price_data: list[dict],
    signals: list[dict[str, str]],
) -> None:
    """
    Append a price-action signal based on changesPercentage.

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

    raw_change = quote.get("changesPercentage")
    if raw_change is None:
        logger.debug("changesPercentage missing from price data — skipping price signal")
        return

    try:
        change_pct = float(raw_change)
    except (TypeError, ValueError):
        logger.warning(
            "Cannot cast changesPercentage to float: %r — skipping price signal",
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
        logger.debug("Price signal: neutral (%.2f%%) — no signal appended", change_pct)


async def _build_options_signals(
    options_data: list[dict],
    price_data: list[dict] | None,
    signals: list[dict[str, str]],
) -> None:
    """
    Append GEX and unusual-activity signals derived from the options chain.

    Requires a valid spot price extracted from price_data (or a fallback of 0.0
    which will cause calculate_gex to return an empty result gracefully).
    """
    # Lazily import engines to keep module-level imports clean
    from backend.engines.gex_engine import calculate_gex
    from backend.engines.unusual_activity import scan_unusual_activity

    # Extract current spot price for GEX calculation
    current_price: float = 0.0
    if price_data and isinstance(price_data, list) and isinstance(price_data[0], dict):
        raw_price = price_data[0].get("price")
        if raw_price is not None:
            try:
                current_price = float(raw_price)
            except (TypeError, ValueError):
                logger.warning(
                    "Cannot cast price to float: %r — GEX will use 0.0", raw_price
                )

    # GEX signal
    try:
        gex_result = await calculate_gex(options_data, current_price)
        if gex_result.total_gex > GEX_BULLISH_THRESHOLD:
            gex_billions = gex_result.total_gex / 1_000_000_000
            signals.append(
                {
                    "factor": "GEX Positioning",
                    "direction": "bullish",
                    "detail": (
                        f"Positive net gamma (${gex_billions:.1f}B)"
                        " — dealer hedging supports price"
                    ),
                }
            )
            logger.debug("GEX signal: bullish (total_gex=%.4e)", gex_result.total_gex)
        else:
            logger.debug(
                "GEX signal: not bullish (total_gex=%.4e) — no signal appended",
                gex_result.total_gex,
            )
    except Exception as exc:
        logger.error("calculate_gex raised during predictions: %s", exc)

    # Unusual activity / put-call ratio signal
    try:
        ua_result = await scan_unusual_activity(options_data)
        if ua_result.put_call_ratio_unusual > PCR_BEARISH_THRESHOLD:
            signals.append(
                {
                    "factor": "Options Flow",
                    "direction": "bearish",
                    "detail": (
                        f"Elevated put/call ratio ({ua_result.put_call_ratio_unusual:.2f})"
                        " in unusual activity"
                    ),
                }
            )
            logger.debug(
                "Unusual activity signal: bearish (pcr=%.4f)",
                ua_result.put_call_ratio_unusual,
            )
        else:
            logger.debug(
                "Unusual activity signal: not bearish (pcr=%.4f) — no signal appended",
                ua_result.put_call_ratio_unusual,
            )
    except Exception as exc:
        logger.error("scan_unusual_activity raised during predictions: %s", exc)


async def _build_sentiment_signal(
    sentiment_data: list[dict],
    signals: list[dict[str, str]],
) -> None:
    """
    Append a sentiment signal based on the composite sentiment score.
    """
    from backend.engines.sentiment_engine import process_sentiment

    try:
        sentiment_result = await process_sentiment(sentiment_data)
        score = sentiment_result.current_score
        direction_label = sentiment_result.roc_direction  # accelerating/stable/decelerating

        if score > SENTIMENT_BULLISH_THRESHOLD:
            signals.append(
                {
                    "factor": "Sentiment",
                    "direction": "bullish",
                    "detail": f"Score +{score:.0f}, {direction_label}",
                }
            )
            logger.debug("Sentiment signal: bullish (score=%.1f)", score)
        elif score < SENTIMENT_BEARISH_THRESHOLD:
            signals.append(
                {
                    "factor": "Sentiment",
                    "direction": "bearish",
                    "detail": f"Score {score:.0f}, {direction_label}",
                }
            )
            logger.debug("Sentiment signal: bearish (score=%.1f)", score)
        else:
            logger.debug(
                "Sentiment signal: neutral (score=%.1f) — no signal appended", score
            )
    except Exception as exc:
        logger.error("process_sentiment raised during predictions: %s", exc)


def _build_earnings_signal(
    surprises_data: list[dict],
    signals: list[dict[str, str]],
) -> None:
    """
    Append an earnings-history signal based on the beat rate over the last four quarters.

    FMP earnings surprise records contain:
      - "actualEarningResult": actual EPS
      - "estimatedEarning": analyst consensus EPS

    A "beat" is when actualEarningResult > estimatedEarning.
    """
    if not surprises_data:
        return

    # Take only the most recent EARNINGS_LOOKBACK quarters (list is newest-first from FMP)
    recent = surprises_data[:EARNINGS_LOOKBACK]

    if not recent:
        logger.debug("Surprises data empty after slicing — skipping earnings signal")
        return

    beats = 0
    total_valid = 0

    for record in recent:
        if not isinstance(record, dict):
            continue

        actual_raw = record.get("actualEarningResult")
        estimated_raw = record.get("estimatedEarning")

        if actual_raw is None or estimated_raw is None:
            logger.debug(
                "Skipping earnings record with missing fields: %r", record
            )
            continue

        try:
            actual = float(actual_raw)
            estimated = float(estimated_raw)
        except (TypeError, ValueError):
            logger.warning(
                "Cannot cast earnings values to float: actual=%r estimated=%r",
                actual_raw,
                estimated_raw,
            )
            continue

        total_valid += 1
        if actual > estimated:
            beats += 1

    if total_valid == 0:
        logger.debug("No valid earnings records — skipping earnings signal")
        return

    beat_ratio = beats / total_valid
    logger.debug(
        "Earnings history: %d beats out of %d valid records (ratio=%.2f)",
        beats, total_valid, beat_ratio,
    )

    if beat_ratio > EARNINGS_BEAT_RATIO:
        signals.append(
            {
                "factor": "Earnings History",
                "direction": "bullish",
                "detail": (
                    f"Beat estimates {beats}/{total_valid} recent quarters"
                ),
            }
        )
        logger.debug("Earnings signal: bullish (beat_ratio=%.2f)", beat_ratio)
    else:
        logger.debug(
            "Earnings signal: not bullish (beat_ratio=%.2f) — no signal appended",
            beat_ratio,
        )
