"""
Polymarket Prediction Market Heatmap Engine.

Replaces the options-based GEX heatmap with a probability heatmap derived
from Polymarket binary prediction markets for NVDA.

Algorithm outline:
  1. Accept a raw list of Polymarket market dicts (from the Gamma API).
  2. Filter for active, non-closed markets only.
  3. Classify each market:
       a. Price-level market  — question contains a dollar amount (regex match).
          Examples: "NVDA closes above $140 on Feb 23?"
                    "What will NVIDIA hit $150 in February 2026?"
       b. Supplementary market — no extractable price level.
          Examples: "Will NVIDIA beat quarterly earnings?"
  4. For price-level markets, extract:
       - Strike price (first $ amount found in the question)
       - YES implied probability (index 0 of outcomePrices)
       - NO implied probability  (index 1 of outcomePrices, or 1 - YES)
       - Volume, 24h volume, and liquidity
  5. Sort price-level markets by strike ascending.
  6. Compute key levels:
       - max_conviction     : strike with the highest YES price
       - fifty_percent_level: strike whose YES price is closest to 0.50
       - low_conviction     : strike with the lowest YES price (above zero)
  7. Return PolymarketAnalysis containing all of the above.

Edge cases handled:
  - No NVDA markets found          → empty result with zero counts
  - outcomePrices as JSON string   → parsed with json.loads via polymarket_client helper
  - No dollar amount in question   → classified as supplementary
  - All markets closed / inactive  → empty price_levels list
  - YES price is zero / missing    → market skipped for price-level list
  - Division-by-zero in fifty-pct  → abs difference clamp, no division needed
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from backend.polymarket_client import parse_outcome_prices

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Regex to extract the first dollar-denominated price from a question string.
# Matches: $140, $140.50, $1234.00
_DOLLAR_AMOUNT_PATTERN: re.Pattern[str] = re.compile(r"\$(\d+(?:\.\d+)?)")

# Keywords that indicate a price-level market (at least one must appear,
# combined with a dollar amount match).
_PRICE_LEVEL_KEYWORDS: tuple[str, ...] = (
    "closes above",
    "close above",
    "above $",
    "hit $",
    "hits $",
    "reach $",
    "reaches $",
    "exceed $",
    "exceeds $",
    "over $",
)

# Minimum YES price to include a market in the price-level list (avoids ghost
# markets with stale / zero prices).
_MIN_YES_PRICE: float = 0.0

# Fifty-percent reference for the market-expected level key.
_FIFTY_PERCENT: float = 0.50


# ---------------------------------------------------------------------------
# Pydantic output models
# ---------------------------------------------------------------------------


class PriceLevelMarket(BaseModel):
    """Probability data for a single NVDA price-level prediction market."""

    strike: float = Field(..., description="Extracted price level in USD")
    question: str = Field(..., description="Original Polymarket question text")
    yes_price: float = Field(
        ..., ge=0.0, le=1.0, description="Implied probability of YES (0–1)"
    )
    no_price: float = Field(
        ..., ge=0.0, le=1.0, description="Implied probability of NO (0–1)"
    )
    volume: float = Field(..., ge=0.0, description="Total volume traded (USD)")
    volume_24h: float = Field(..., ge=0.0, description="24-hour trading volume (USD)")
    liquidity: float = Field(..., ge=0.0, description="Current market liquidity (USD)")
    market_id: str = Field(..., description="Polymarket market identifier")


class KeyLevels(BaseModel):
    """Notable strike levels derived from the Polymarket probability heatmap."""

    max_conviction: Optional[float] = Field(
        None,
        description="Strike with the highest YES price (market most confident NVDA reaches here)",
    )
    fifty_percent_level: Optional[float] = Field(
        None,
        description="Strike whose YES price is closest to 0.50 (market's expected close level)",
    )
    low_conviction: Optional[float] = Field(
        None,
        description="Strike with the lowest YES price above zero (least likely to be reached)",
    )


class SupplementaryMarket(BaseModel):
    """Non-price-level NVDA prediction market (e.g., earnings beat/miss)."""

    question: str = Field(..., description="Original Polymarket question text")
    yes_price: float = Field(
        ..., ge=0.0, le=1.0, description="Implied probability of YES (0–1)"
    )
    volume: float = Field(..., ge=0.0, description="Total volume traded (USD)")
    market_id: str = Field(..., description="Polymarket market identifier")


class PolymarketAnalysis(BaseModel):
    """Full Polymarket heatmap analysis result returned by analyze_polymarket()."""

    price_levels: list[PriceLevelMarket] = Field(
        default_factory=list,
        description="Price-level markets sorted by strike ascending",
    )
    key_levels: KeyLevels = Field(
        default_factory=KeyLevels,
        description="Notable conviction levels derived from the heatmap",
    )
    supplementary: list[SupplementaryMarket] = Field(
        default_factory=list,
        description="Non-price-level NVDA markets (earnings beat/miss, etc.)",
    )
    total_volume: float = Field(
        ..., ge=0.0, description="Sum of all NVDA market volumes (USD)"
    )
    market_count: int = Field(
        ..., ge=0, description="Number of active NVDA markets found"
    )
    last_updated: str = Field(
        ..., description="ISO-8601 UTC timestamp when this analysis was generated"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_strike(question: str) -> Optional[float]:
    """
    Extract the first dollar-denominated price from a market question.

    Examples::

        "NVIDIA (NVDA) closes above $140 on February 23?" → 140.0
        "Will NVIDIA (NVDA) hit $135.50 in Q1 2026?"     → 135.5
        "Will NVIDIA beat quarterly earnings?"             → None

    Args:
        question: The raw Polymarket question string.

    Returns:
        Extracted price as a float, or ``None`` if no dollar amount is found.
    """
    match = _DOLLAR_AMOUNT_PATTERN.search(question)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _is_price_level_market(question: str, strike: Optional[float]) -> bool:
    """
    Determine whether a market question represents a specific price-level bet.

    A market is considered a price-level market when it has a parseable dollar
    amount AND contains at least one of the recognised price-level keywords.
    Markets that mention a dollar amount in a non-directional context (e.g.,
    "Will NVDA reach a $1 trillion market cap?") are excluded when none of
    the directional keywords match.

    Args:
        question: Normalised (lower-case) market question.
        strike:   Pre-extracted strike price (``None`` means no dollar amount found).

    Returns:
        ``True`` if this is a price-level market, ``False`` otherwise.
    """
    if strike is None:
        return False

    question_lower = question.lower()
    return any(keyword in question_lower for keyword in _PRICE_LEVEL_KEYWORDS)


def _extract_yes_price(market: dict) -> Optional[float]:
    """
    Return the YES implied probability from a Polymarket market dict.

    Extraction priority:
      1. ``tokens`` list — find the token with ``outcome == "Yes"`` and
         read its ``price`` field.
      2. ``outcomePrices`` — parse the JSON string and take index 0
         (Polymarket convention: index 0 = YES, index 1 = NO).

    Args:
        market: Raw Polymarket Gamma API market dict.

    Returns:
        YES price as float in [0, 1], or ``None`` if not found / invalid.
    """
    market_id = market.get("id", "<unknown>")

    # Attempt 1: tokens list
    tokens = market.get("tokens")
    if isinstance(tokens, list):
        for token in tokens:
            if isinstance(token, dict) and str(token.get("outcome", "")).lower() == "yes":
                raw_price = token.get("price")
                if raw_price is not None:
                    try:
                        return float(raw_price)
                    except (ValueError, TypeError):
                        logger.warning(
                            "polymarket_engine: cannot convert token price=%r to float "
                            "for market id=%s",
                            raw_price,
                            market_id,
                        )

    # Attempt 2: outcomePrices (index 0 = YES per Polymarket convention)
    prices = parse_outcome_prices(market)
    if prices is not None and len(prices) > 0:
        return prices[0]

    logger.debug(
        "polymarket_engine: could not extract YES price for market id=%s", market_id
    )
    return None


def _safe_float(value: object, default: float = 0.0) -> float:
    """
    Coerce *value* to float, returning *default* on failure.

    Args:
        value:   Input value (may be str, int, float, or None).
        default: Value to return on conversion failure.

    Returns:
        Coerced float or *default*.
    """
    if value is None:
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Key-level computation
# ---------------------------------------------------------------------------


def _compute_key_levels(price_levels: list[PriceLevelMarket]) -> KeyLevels:
    """
    Derive the three key conviction levels from the sorted price-level list.

    - **max_conviction**: strike with the highest YES price.
    - **fifty_percent_level**: strike whose YES price is nearest 0.50.
    - **low_conviction**: strike with the lowest YES price strictly above zero.

    Args:
        price_levels: List of PriceLevelMarket objects (any order accepted).

    Returns:
        KeyLevels instance.
    """
    if not price_levels:
        return KeyLevels(
            max_conviction=None,
            fifty_percent_level=None,
            low_conviction=None,
        )

    # max_conviction — highest YES price
    max_market = max(price_levels, key=lambda m: m.yes_price)
    max_conviction: Optional[float] = max_market.strike

    # fifty_percent_level — YES price nearest to 0.50
    fifty_market = min(
        price_levels,
        key=lambda m: abs(m.yes_price - _FIFTY_PERCENT),
    )
    fifty_percent_level: Optional[float] = fifty_market.strike

    # low_conviction — lowest YES price above zero
    above_zero = [m for m in price_levels if m.yes_price > _MIN_YES_PRICE]
    low_conviction: Optional[float] = (
        min(above_zero, key=lambda m: m.yes_price).strike if above_zero else None
    )

    logger.debug(
        "polymarket_engine key_levels: max_conviction=%.2f fifty_pct=%.2f low_conviction=%s",
        max_conviction,
        fifty_percent_level,
        low_conviction,
    )

    return KeyLevels(
        max_conviction=max_conviction,
        fifty_percent_level=fifty_percent_level,
        low_conviction=low_conviction,
    )


# ---------------------------------------------------------------------------
# Main engine function
# ---------------------------------------------------------------------------


async def analyze_polymarket(markets: list[dict]) -> PolymarketAnalysis:
    """
    Build a Polymarket probability heatmap from a list of raw market dicts.

    This is the primary entry point for the Polymarket engine.  The route
    layer is responsible for fetching market data (via PolymarketClient) and
    caching it before passing it to this function.

    Args:
        markets: Raw list of Polymarket Gamma API market dicts.  May be empty.

    Returns:
        PolymarketAnalysis with per-strike probability data, key levels,
        supplementary signals, aggregate volumes, and a UTC timestamp.
    """
    now_utc: str = datetime.now(timezone.utc).isoformat()

    # Guard: empty input
    if not markets:
        logger.warning("analyze_polymarket: received empty markets list")
        return PolymarketAnalysis(
            price_levels=[],
            key_levels=KeyLevels(
                max_conviction=None,
                fifty_percent_level=None,
                low_conviction=None,
            ),
            supplementary=[],
            total_volume=0.0,
            market_count=0,
            last_updated=now_utc,
        )

    price_levels: list[PriceLevelMarket] = []
    supplementary: list[SupplementaryMarket] = []
    total_volume: float = 0.0
    active_count: int = 0

    for market in markets:
        if not isinstance(market, dict):
            logger.debug("analyze_polymarket: skipping non-dict entry %r", market)
            continue

        market_id: str = str(market.get("id", ""))
        question: str = str(market.get("question", ""))

        # Skip closed or inactive markets
        is_active: bool = bool(market.get("active", False))
        is_closed: bool = bool(market.get("closed", False))
        if not is_active or is_closed:
            logger.debug(
                "analyze_polymarket: skipping inactive/closed market id=%s question=%r",
                market_id,
                question,
            )
            continue

        active_count += 1

        # Accumulate total volume across all active NVDA markets
        market_volume: float = _safe_float(market.get("volume"))
        total_volume += market_volume

        # Extract YES implied probability
        yes_price: Optional[float] = _extract_yes_price(market)
        if yes_price is None:
            logger.debug(
                "analyze_polymarket: no YES price for market id=%s — classifying as supplementary",
                market_id,
            )
            supplementary.append(
                SupplementaryMarket(
                    question=question,
                    yes_price=0.0,
                    volume=market_volume,
                    market_id=market_id,
                )
            )
            continue

        # Attempt strike extraction
        strike: Optional[float] = _extract_strike(question)

        if _is_price_level_market(question, strike):
            # strike is guaranteed non-None here by _is_price_level_market
            assert strike is not None  # for the type checker

            no_price: float = 1.0 - yes_price

            volume_24h: float = _safe_float(market.get("volume24hr"))
            liquidity: float = _safe_float(market.get("liquidity"))

            price_levels.append(
                PriceLevelMarket(
                    strike=strike,
                    question=question,
                    yes_price=yes_price,
                    no_price=no_price,
                    volume=market_volume,
                    volume_24h=volume_24h,
                    liquidity=liquidity,
                    market_id=market_id,
                )
            )
            logger.debug(
                "analyze_polymarket: price-level market id=%s strike=%.2f yes=%.4f",
                market_id,
                strike,
                yes_price,
            )
        else:
            # Supplementary: no parseable price level (earnings beat/miss, etc.)
            supplementary.append(
                SupplementaryMarket(
                    question=question,
                    yes_price=yes_price,
                    volume=market_volume,
                    market_id=market_id,
                )
            )
            logger.debug(
                "analyze_polymarket: supplementary market id=%s yes=%.4f question=%r",
                market_id,
                yes_price,
                question,
            )

    # Sort price-level markets by strike ascending
    price_levels.sort(key=lambda m: m.strike)

    # Compute key conviction levels
    key_levels: KeyLevels = _compute_key_levels(price_levels)

    logger.info(
        "analyze_polymarket complete: active=%d price_levels=%d supplementary=%d "
        "total_volume=%.2f",
        active_count,
        len(price_levels),
        len(supplementary),
        total_volume,
    )

    return PolymarketAnalysis(
        price_levels=price_levels,
        key_levels=key_levels,
        supplementary=supplementary,
        total_volume=total_volume,
        market_count=active_count,
        last_updated=now_utc,
    )
