"""
GEX (Gamma Exposure) Calculation Engine.

Computes gamma exposure across all option strikes to identify the gamma flip
level and key volatility trigger zones for NVDA options.

Algorithm outline:
  1. Filter expired contracts and zero-OI contracts.
  2. Compute implied volatility via bisection when the field is missing or zero.
  3. Apply Black-Scholes gamma to each contract and scale by OI * 100 * S².
  4. Aggregate net GEX per strike across all expirations.
  5. Detect the gamma-flip level: the strike where net GEX crosses from negative
     to positive (sorted ascending by strike).
  6. Report key levels: max-positive-GEX strike, max-negative-GEX strike, and
     the gamma-flip strike.
"""

import logging
import math
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field
from scipy.stats import norm

from backend.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Bisection search bounds for implied volatility
IV_BISECT_LOW: float = 0.01
IV_BISECT_HIGH: float = 5.0
IV_BISECT_TOLERANCE: float = 1e-4
IV_BISECT_MAX_ITER: int = 100

# Guard: skip contracts where σ√T is below this to avoid division by zero
MIN_SIGMA_SQRT_T: float = 1e-8

# Multiplier applied per contract (each contract = 100 shares)
CONTRACT_MULTIPLIER: int = 100


# ---------------------------------------------------------------------------
# Pydantic output models
# ---------------------------------------------------------------------------


class GexStrike(BaseModel):
    """Net GEX components for a single strike price."""

    strike: float = Field(..., description="Strike price in USD")
    call_gex: float = Field(..., description="Aggregate call GEX at this strike")
    put_gex: float = Field(..., description="Aggregate put GEX at this strike (negative)")
    net_gex: float = Field(..., description="Net GEX at this strike (call_gex + put_gex)")


class GexKeyLevels(BaseModel):
    """Notable strike levels derived from the GEX profile."""

    max_positive_gex: Optional[float] = Field(
        None, description="Strike with the highest positive net GEX"
    )
    max_negative_gex: Optional[float] = Field(
        None, description="Strike with the most negative net GEX"
    )
    gamma_flip: Optional[float] = Field(
        None, description="Strike where net GEX crosses from negative to positive"
    )


class GexResult(BaseModel):
    """Full GEX calculation result returned by calculate_gex()."""

    current_price: float = Field(..., description="Current NVDA spot price")
    gamma_flip: Optional[float] = Field(
        None, description="Gamma flip strike price (first zero-crossing, ascending)"
    )
    total_gex: float = Field(..., description="Sum of all net GEX values across all strikes")
    strikes: list[GexStrike] = Field(default_factory=list, description="Per-strike GEX data")
    key_levels: GexKeyLevels = Field(
        default_factory=GexKeyLevels, description="Notable GEX levels"
    )
    last_updated: str = Field(
        ..., description="ISO-8601 UTC timestamp of when this result was generated"
    )


# ---------------------------------------------------------------------------
# Black-Scholes helpers
# ---------------------------------------------------------------------------


def _bs_d1(S: float, K: float, r: float, sigma: float, T: float) -> float:
    """Compute d1 component of the Black-Scholes formula."""
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))


def _bs_price(
    S: float, K: float, r: float, sigma: float, T: float, option_type: str
) -> float:
    """
    Black-Scholes theoretical price for a European call or put.

    Args:
        S:           Current spot price.
        K:           Strike price.
        r:           Risk-free rate (annualised, continuously compounded).
        sigma:       Implied volatility (annualised).
        T:           Time to expiration in years (must be > 0).
        option_type: "call" or "put" (case-insensitive).

    Returns:
        Theoretical option price.
    """
    d1 = _bs_d1(S, K, r, sigma, T)
    d2 = d1 - sigma * math.sqrt(T)
    discount = math.exp(-r * T)

    if option_type.lower() == "call":
        return S * norm.cdf(d1) - K * discount * norm.cdf(d2)
    else:
        return K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)


def _bs_gamma(S: float, K: float, r: float, sigma: float, T: float) -> float:
    """
    Black-Scholes gamma (identical for calls and puts).

    Gamma = N'(d1) / (S * sigma * sqrt(T))

    Returns:
        Gamma value (always non-negative).
    """
    sigma_sqrt_t = sigma * math.sqrt(T)
    if sigma_sqrt_t < MIN_SIGMA_SQRT_T:
        return 0.0

    d1 = _bs_d1(S, K, r, sigma, T)
    return float(norm.pdf(d1)) / (S * sigma_sqrt_t)


# ---------------------------------------------------------------------------
# IV bisection
# ---------------------------------------------------------------------------


def _implied_volatility_bisection(
    market_price: float,
    S: float,
    K: float,
    r: float,
    T: float,
    option_type: str,
) -> Optional[float]:
    """
    Recover implied volatility via bisection search.

    Searches the interval [IV_BISECT_LOW, IV_BISECT_HIGH] for a sigma that
    makes the Black-Scholes price equal to *market_price* within
    IV_BISECT_TOLERANCE.

    Args:
        market_price: Observed market price (mid-price preferred).
        S:            Spot price.
        K:            Strike price.
        r:            Risk-free rate.
        T:            Time to expiration in years (must be > 0).
        option_type:  "call" or "put".

    Returns:
        Implied volatility, or None if bisection did not converge.
    """
    if market_price <= 0:
        logger.debug("IV bisection skipped: market_price=%.4f <= 0", market_price)
        return None

    # Intrinsic value check — market price must exceed intrinsic to have a valid IV
    discount = math.exp(-r * T)
    if option_type.lower() == "call":
        intrinsic = max(S - K * discount, 0.0)
    else:
        intrinsic = max(K * discount - S, 0.0)

    if market_price < intrinsic - IV_BISECT_TOLERANCE:
        logger.debug(
            "IV bisection skipped: market_price=%.4f below intrinsic=%.4f",
            market_price,
            intrinsic,
        )
        return None

    low, high = IV_BISECT_LOW, IV_BISECT_HIGH

    price_low = _bs_price(S, K, r, low, T, option_type)
    price_high = _bs_price(S, K, r, high, T, option_type)

    # If market price is outside the achievable range, bail out
    if market_price < price_low - IV_BISECT_TOLERANCE:
        logger.debug("IV bisection skipped: market_price below BS price at sigma_low")
        return None
    if market_price > price_high + IV_BISECT_TOLERANCE:
        logger.debug("IV bisection skipped: market_price above BS price at sigma_high")
        return None

    for iteration in range(IV_BISECT_MAX_ITER):
        mid = (low + high) / 2.0
        price_mid = _bs_price(S, K, r, mid, T, option_type)
        error = price_mid - market_price

        if abs(error) < IV_BISECT_TOLERANCE:
            logger.debug(
                "IV bisection converged: sigma=%.6f after %d iterations", mid, iteration + 1
            )
            return mid

        # Bisection: BS price is monotonically increasing in sigma
        if error < 0:
            low = mid
        else:
            high = mid

    logger.warning(
        "IV bisection did not converge after %d iterations for K=%.2f type=%s",
        IV_BISECT_MAX_ITER,
        K,
        option_type,
    )
    return None


# ---------------------------------------------------------------------------
# Time-to-expiration helper
# ---------------------------------------------------------------------------


def _time_to_expiry_years(expiration_date_str: str) -> float:
    """
    Calculate time remaining until expiration in years from today (UTC).

    Args:
        expiration_date_str: ISO date string such as "2026-03-21".

    Returns:
        Fractional years remaining. Negative or zero means expired.
    """
    today = date.today()
    try:
        expiry = date.fromisoformat(expiration_date_str)
    except (ValueError, TypeError):
        logger.warning("Unparseable expiration date: %r — skipping", expiration_date_str)
        return 0.0

    delta_days = (expiry - today).days
    return delta_days / 365.0


# ---------------------------------------------------------------------------
# Market price extraction helper
# ---------------------------------------------------------------------------


def _extract_market_price(contract: dict) -> Optional[float]:
    """
    Return the best available market price for a contract.

    Preference order:
      1. Mid-price from bid/ask (if both are positive)
      2. lastPrice (if positive)

    Returns None if no usable price is found.
    """
    bid = contract.get("bid")
    ask = contract.get("ask")

    if (
        bid is not None
        and ask is not None
        and isinstance(bid, (int, float))
        and isinstance(ask, (int, float))
        and bid > 0
        and ask > 0
    ):
        return (float(bid) + float(ask)) / 2.0

    last = contract.get("lastPrice")
    if last is not None and isinstance(last, (int, float)) and last > 0:
        return float(last)

    return None


# ---------------------------------------------------------------------------
# Main engine function
# ---------------------------------------------------------------------------


async def calculate_gex(
    options_chain: list[dict],
    current_price: float,
) -> GexResult:
    """
    Calculate Gamma Exposure across all option strikes.

    This is the primary entry point for the GEX engine.  The route layer is
    responsible for reading data from the cache and passing it here.

    Args:
        options_chain: Raw list of option contract dicts (FMP format).
        current_price: Current NVDA spot price.

    Returns:
        GexResult with per-strike breakdown, gamma flip, key levels, and
        aggregate total GEX.
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    if not options_chain or current_price <= 0:
        logger.warning(
            "calculate_gex called with empty chain or invalid price=%.2f", current_price
        )
        return GexResult(
            current_price=current_price,
            gamma_flip=None,
            total_gex=0.0,
            strikes=[],
            key_levels=GexKeyLevels(
                max_positive_gex=None,
                max_negative_gex=None,
                gamma_flip=None,
            ),
            last_updated=now_utc,
        )

    r = settings.risk_free_rate
    S = current_price

    # Accumulate GEX per strike: strike -> {"call": float, "put": float}
    strike_gex: dict[float, dict[str, float]] = {}

    for contract in options_chain:
        strike_raw = contract.get("strike")
        oi_raw = contract.get("openInterest")
        expiry_str = contract.get("expirationDate", "")
        option_type: str = str(contract.get("type", "")).lower()

        # Validate required fields
        if strike_raw is None or oi_raw is None or option_type not in ("call", "put"):
            logger.debug("Skipping contract with missing required fields: %r", contract)
            continue

        K = float(strike_raw)
        oi = int(oi_raw)

        # Skip zero open interest
        if oi == 0:
            logger.debug("Skipping zero-OI contract: K=%.2f type=%s", K, option_type)
            continue

        # Skip expired contracts
        T = _time_to_expiry_years(expiry_str)
        if T <= 0:
            logger.debug(
                "Skipping expired contract: K=%.2f expiry=%s T=%.4f",
                K,
                expiry_str,
                T,
            )
            continue

        # Resolve implied volatility
        iv_raw = contract.get("impliedVolatility")
        sigma: Optional[float] = None

        if iv_raw is not None and isinstance(iv_raw, (int, float)) and float(iv_raw) > 0:
            sigma = float(iv_raw)
        else:
            logger.debug(
                "IV missing/zero for K=%.2f %s — attempting bisection", K, option_type
            )
            market_price = _extract_market_price(contract)
            if market_price is not None:
                sigma = _implied_volatility_bisection(market_price, S, K, r, T, option_type)
            else:
                logger.debug(
                    "No usable market price for IV bisection: K=%.2f %s — skipping",
                    K,
                    option_type,
                )

        if sigma is None or sigma <= 0:
            logger.debug("No valid IV for K=%.2f %s — skipping", K, option_type)
            continue

        # Guard against division by zero in gamma calculation
        sigma_sqrt_t = sigma * math.sqrt(T)
        if sigma_sqrt_t < MIN_SIGMA_SQRT_T:
            logger.debug(
                "sigma*sqrt(T)=%.2e too small for K=%.2f %s — skipping",
                sigma_sqrt_t,
                K,
                option_type,
            )
            continue

        # Black-Scholes gamma (always positive)
        gamma = _bs_gamma(S, K, r, sigma, T)

        # GEX formula: Gamma * OI * 100 * S²  (negative for puts)
        gex_magnitude = gamma * oi * CONTRACT_MULTIPLIER * (S ** 2)

        if K not in strike_gex:
            strike_gex[K] = {"call": 0.0, "put": 0.0}

        if option_type == "call":
            strike_gex[K]["call"] += gex_magnitude
        else:
            strike_gex[K]["put"] += -gex_magnitude  # puts are negative

        logger.debug(
            "Processed K=%.2f %s: gamma=%.6e oi=%d gex=%.4e",
            K,
            option_type,
            gamma,
            oi,
            gex_magnitude,
        )

    # Build sorted per-strike list
    sorted_strikes = sorted(strike_gex.keys())
    strike_rows: list[GexStrike] = []

    for K in sorted_strikes:
        call_gex = strike_gex[K]["call"]
        put_gex = strike_gex[K]["put"]
        net_gex = call_gex + put_gex
        strike_rows.append(
            GexStrike(strike=K, call_gex=call_gex, put_gex=put_gex, net_gex=net_gex)
        )

    total_gex = sum(row.net_gex for row in strike_rows)

    # Detect gamma flip: first strike where net GEX crosses from negative to positive
    gamma_flip: Optional[float] = _find_gamma_flip(strike_rows)

    # Key levels
    key_levels = _compute_key_levels(strike_rows, gamma_flip)

    logger.info(
        "GEX calculation complete: strikes=%d total_gex=%.4e gamma_flip=%s",
        len(strike_rows),
        total_gex,
        gamma_flip,
    )

    return GexResult(
        current_price=S,
        gamma_flip=gamma_flip,
        total_gex=total_gex,
        strikes=strike_rows,
        key_levels=key_levels,
        last_updated=now_utc,
    )


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------


def _find_gamma_flip(strike_rows: list[GexStrike]) -> Optional[float]:
    """
    Find the gamma flip: the first strike (ascending) where net GEX crosses
    from negative to positive.

    The flip strike is the *higher* of the two strikes that straddle the
    zero crossing (i.e., the first strike with a positive net GEX following
    at least one negative net GEX).

    Args:
        strike_rows: List of GexStrike objects sorted by strike ascending.

    Returns:
        The gamma-flip strike, or None if no crossing exists.
    """
    prev_negative = False

    for row in strike_rows:
        if row.net_gex < 0:
            prev_negative = True
        elif row.net_gex > 0 and prev_negative:
            return row.strike

    return None


def _compute_key_levels(
    strike_rows: list[GexStrike],
    gamma_flip: Optional[float],
) -> GexKeyLevels:
    """
    Compute key levels: max positive GEX strike and max negative GEX strike.

    Args:
        strike_rows: Sorted per-strike GEX data.
        gamma_flip:  Pre-computed gamma flip level (may be None).

    Returns:
        GexKeyLevels instance.
    """
    if not strike_rows:
        return GexKeyLevels(
            max_positive_gex=None,
            max_negative_gex=None,
            gamma_flip=gamma_flip,
        )

    positive_rows = [r for r in strike_rows if r.net_gex > 0]
    negative_rows = [r for r in strike_rows if r.net_gex < 0]

    max_positive_strike: Optional[float] = (
        max(positive_rows, key=lambda r: r.net_gex).strike if positive_rows else None
    )
    max_negative_strike: Optional[float] = (
        min(negative_rows, key=lambda r: r.net_gex).strike if negative_rows else None
    )

    return GexKeyLevels(
        max_positive_gex=max_positive_strike,
        max_negative_gex=max_negative_strike,
        gamma_flip=gamma_flip,
    )
