"""
Tests for the GEX (Gamma Exposure) calculation engine.

All tests use mock fixture data — no live FMP calls are made.
Math is verified against independent hand calculations.
"""

import math
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from backend.engines.gex_engine import (
    GexResult,
    GexStrike,
    _bs_gamma,
    _bs_price,
    _find_gamma_flip,
    _implied_volatility_bisection,
    _time_to_expiry_years,
    calculate_gex,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_date(days: int) -> str:
    """Return an ISO date string *days* from today."""
    return (date.today() + timedelta(days=days)).isoformat()


def _past_date(days: int) -> str:
    """Return an ISO date string *days* in the past."""
    return (date.today() - timedelta(days=days)).isoformat()


def norm_pdf(x: float) -> float:
    """Standard normal PDF (stdlib only — no scipy dependency in helpers)."""
    return math.exp(-0.5 * x**2) / math.sqrt(2 * math.pi)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


CURRENT_PRICE = 950.0
RISK_FREE_RATE = 0.045


@pytest.fixture
def basic_chain() -> list[dict[str, Any]]:
    """
    Five contracts across two strikes (K=950 and K=980) with one expiration
    each.  Provides known, hand-verifiable inputs.

    K=950:
      Call: OI=5000, sigma=0.55, T≈30/365
      Put:  OI=3000, sigma=0.55, T≈30/365

    K=980:
      Call: OI=6000, sigma=0.50, T≈30/365

    Expected (pre-computed):
      K=950  call_gex ≈ +1.196e+09
      K=950  put_gex  ≈ -7.173e+08
      K=950  net_gex  ≈ +4.782e+08

      K=980  call_gex ≈ +1.575e+09
      K=980  net_gex  ≈ +1.575e+09 (no puts)
    """
    expiry_30 = _future_date(30)
    return [
        {
            "symbol": "NVDA",
            "strike": 950.0,
            "expirationDate": expiry_30,
            "type": "call",
            "openInterest": 5000,
            "impliedVolatility": 0.55,
            "lastPrice": 35.00,
            "bid": 34.50,
            "ask": 35.50,
        },
        {
            "symbol": "NVDA",
            "strike": 950.0,
            "expirationDate": expiry_30,
            "type": "put",
            "openInterest": 3000,
            "impliedVolatility": 0.55,
            "lastPrice": 30.00,
            "bid": 29.50,
            "ask": 30.50,
        },
        {
            "symbol": "NVDA",
            "strike": 980.0,
            "expirationDate": expiry_30,
            "type": "call",
            "openInterest": 6000,
            "impliedVolatility": 0.50,
            "lastPrice": 20.00,
            "bid": 19.50,
            "ask": 20.50,
        },
    ]


@pytest.fixture
def gamma_flip_chain() -> list[dict[str, Any]]:
    """
    Chain designed to produce a gamma flip between K=900 and K=1000.

    K=900:  put-only  → net GEX is negative
    K=1000: call-only → net GEX is positive

    Expected gamma flip = 1000.0
    """
    expiry_45 = _future_date(45)
    return [
        {
            "strike": 900.0,
            "expirationDate": expiry_45,
            "type": "put",
            "openInterest": 5000,
            "impliedVolatility": 0.65,
            "lastPrice": 10.00,
            "bid": 9.50,
            "ask": 10.50,
        },
        {
            "strike": 1000.0,
            "expirationDate": expiry_45,
            "type": "call",
            "openInterest": 8000,
            "impliedVolatility": 0.45,
            "lastPrice": 15.00,
            "bid": 14.50,
            "ask": 15.50,
        },
    ]


@pytest.fixture
def all_puts_chain() -> list[dict[str, Any]]:
    """
    Chain with only put contracts.  Every net GEX value must be negative.
    """
    expiry_60 = _future_date(60)
    return [
        {
            "strike": 920.0,
            "expirationDate": expiry_60,
            "type": "put",
            "openInterest": 4000,
            "impliedVolatility": 0.60,
            "lastPrice": 25.00,
            "bid": 24.50,
            "ask": 25.50,
        },
        {
            "strike": 940.0,
            "expirationDate": expiry_60,
            "type": "put",
            "openInterest": 3500,
            "impliedVolatility": 0.58,
            "lastPrice": 28.00,
            "bid": 27.50,
            "ask": 28.50,
        },
    ]


@pytest.fixture
def multi_expiry_chain() -> list[dict[str, Any]]:
    """
    Two expirations for the same strike K=950 to verify aggregation.

    K=950 call exp30:  OI=2000, sigma=0.55
    K=950 call exp60:  OI=2000, sigma=0.55
    Together they should equal a single contract with OI=4000.
    """
    expiry_30 = _future_date(30)
    expiry_60 = _future_date(60)
    return [
        {
            "strike": 950.0,
            "expirationDate": expiry_30,
            "type": "call",
            "openInterest": 2000,
            "impliedVolatility": 0.55,
            "lastPrice": 35.00,
            "bid": 34.50,
            "ask": 35.50,
        },
        {
            "strike": 950.0,
            "expirationDate": expiry_60,
            "type": "call",
            "openInterest": 2000,
            "impliedVolatility": 0.55,
            "lastPrice": 37.00,
            "bid": 36.50,
            "ask": 37.50,
        },
    ]


# ---------------------------------------------------------------------------
# Helper to pin the settings risk_free_rate in all async tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def pin_risk_free_rate():
    """Ensure every test runs with a stable risk_free_rate of 0.045."""
    with patch("backend.engines.gex_engine.settings") as mock_settings:
        mock_settings.risk_free_rate = RISK_FREE_RATE
        yield mock_settings


# ---------------------------------------------------------------------------
# Test 1: Basic GEX calculation with known inputs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_basic_gex_known_inputs(basic_chain: list[dict[str, Any]]) -> None:
    """
    Verify that calculate_gex produces values within 1 % of hand-computed
    figures for a small, well-defined fixture.

    Manually computed expected values (T = 30/365, S = 950, r = 0.045):
      K=950  sigma=0.55
        sigma_sqrt_T = 0.55 * sqrt(30/365) ≈ 0.15762
        d1 ≈ 0.10230
        gamma ≈ 2.64934e-03
        call_gex = gamma * 5000 * 100 * 950² ≈ 1.1955e+09
        put_gex  = -(gamma * 3000 * 100 * 950²) ≈ -7.1731e+08
        net_gex  ≈ 4.782e+08

      K=980  sigma=0.50
        net_gex ≈ 1.5751e+09
    """
    result = await calculate_gex(basic_chain, CURRENT_PRICE)

    assert isinstance(result, GexResult)
    assert result.current_price == CURRENT_PRICE
    assert len(result.strikes) == 2

    by_strike = {row.strike: row for row in result.strikes}

    # --- K=950 ---
    row_950 = by_strike[950.0]
    expected_call_950 = 1.1955e9
    expected_put_950 = -7.1731e8
    expected_net_950 = expected_call_950 + expected_put_950

    assert row_950.call_gex == pytest.approx(expected_call_950, rel=0.01), (
        f"K=950 call_gex mismatch: {row_950.call_gex:.4e}"
    )
    assert row_950.put_gex == pytest.approx(expected_put_950, rel=0.01), (
        f"K=950 put_gex mismatch: {row_950.put_gex:.4e}"
    )
    assert row_950.net_gex == pytest.approx(expected_net_950, rel=0.01), (
        f"K=950 net_gex mismatch: {row_950.net_gex:.4e}"
    )

    # --- K=980 ---
    row_980 = by_strike[980.0]
    expected_call_980 = 1.5751e9
    assert row_980.call_gex == pytest.approx(expected_call_980, rel=0.01), (
        f"K=980 call_gex mismatch: {row_980.call_gex:.4e}"
    )
    assert row_980.put_gex == pytest.approx(0.0, abs=1.0), (
        "K=980 should have no put GEX"
    )

    # total_gex = sum of all net values
    expected_total = expected_net_950 + row_980.net_gex
    assert result.total_gex == pytest.approx(expected_total, rel=0.01)

    # last_updated should be a non-empty string
    assert result.last_updated


# ---------------------------------------------------------------------------
# Test 2: Gamma flip detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gamma_flip_detection(gamma_flip_chain: list[dict[str, Any]]) -> None:
    """
    Gamma flip must be identified as K=1000 because:
      - K=900 is all-puts → net GEX is negative
      - K=1000 is all-calls → net GEX is positive
    The flip is the first positive strike after at least one negative strike.
    """
    result = await calculate_gex(gamma_flip_chain, CURRENT_PRICE)

    assert result.gamma_flip == 1000.0, (
        f"Expected gamma_flip=1000.0, got {result.gamma_flip}"
    )
    assert result.key_levels.gamma_flip == 1000.0

    # Verify the sign pattern
    by_strike = {row.strike: row for row in result.strikes}
    assert by_strike[900.0].net_gex < 0, "K=900 should have negative net GEX"
    assert by_strike[1000.0].net_gex > 0, "K=1000 should have positive net GEX"


# ---------------------------------------------------------------------------
# Test 3: Expired options are skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_options_skipped() -> None:
    """Contracts with T <= 0 must be excluded from GEX calculation."""
    chain: list[dict[str, Any]] = [
        {
            "strike": 950.0,
            "expirationDate": _past_date(1),  # expired yesterday
            "type": "call",
            "openInterest": 5000,
            "impliedVolatility": 0.55,
            "lastPrice": 5.00,
            "bid": 4.50,
            "ask": 5.50,
        },
        {
            "strike": 950.0,
            "expirationDate": _past_date(30),  # expired 30 days ago
            "type": "put",
            "openInterest": 3000,
            "impliedVolatility": 0.55,
            "lastPrice": 3.00,
            "bid": 2.50,
            "ask": 3.50,
        },
    ]

    result = await calculate_gex(chain, CURRENT_PRICE)

    assert len(result.strikes) == 0, (
        "Expired contracts should produce no strike rows"
    )
    assert result.total_gex == pytest.approx(0.0)
    assert result.gamma_flip is None


# ---------------------------------------------------------------------------
# Test 4: Zero OI contracts are skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_oi_skipped() -> None:
    """Contracts with openInterest=0 must be excluded."""
    chain: list[dict[str, Any]] = [
        {
            "strike": 950.0,
            "expirationDate": _future_date(30),
            "type": "call",
            "openInterest": 0,        # zero OI — must be skipped
            "impliedVolatility": 0.55,
            "lastPrice": 35.00,
            "bid": 34.50,
            "ask": 35.50,
        },
        {
            "strike": 960.0,
            "expirationDate": _future_date(30),
            "type": "call",
            "openInterest": 1000,     # valid — must be included
            "impliedVolatility": 0.52,
            "lastPrice": 28.00,
            "bid": 27.50,
            "ask": 28.50,
        },
    ]

    result = await calculate_gex(chain, CURRENT_PRICE)

    strikes_present = {row.strike for row in result.strikes}
    assert 950.0 not in strikes_present, "Zero-OI contract at K=950 must be excluded"
    assert 960.0 in strikes_present, "Valid K=960 contract must be included"
    assert len(result.strikes) == 1


# ---------------------------------------------------------------------------
# Test 5: Missing / zero IV triggers bisection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_iv_triggers_bisection() -> None:
    """
    When impliedVolatility is missing or zero the engine must recover IV via
    bisection and still produce a non-zero GEX value.
    """
    expiry = _future_date(30)
    chain: list[dict[str, Any]] = [
        {
            "strike": 950.0,
            "expirationDate": expiry,
            "type": "call",
            "openInterest": 5000,
            "impliedVolatility": 0,   # zero — triggers bisection
            "lastPrice": 35.50,       # realistic mid-price so bisection converges
            "bid": 35.00,
            "ask": 36.00,
        },
        {
            "strike": 960.0,
            "expirationDate": expiry,
            "type": "call",
            "openInterest": 4000,
            # impliedVolatility key absent entirely — triggers bisection
            "lastPrice": 28.50,
            "bid": 28.00,
            "ask": 29.00,
        },
    ]

    result = await calculate_gex(chain, CURRENT_PRICE)

    # Both contracts should produce valid GEX rows because bisection converges
    assert len(result.strikes) >= 1, (
        "At least one contract should succeed via bisection"
    )
    for row in result.strikes:
        assert row.call_gex > 0, (
            f"Strike {row.strike}: expected positive call_gex, got {row.call_gex}"
        )


# ---------------------------------------------------------------------------
# Test 6: All puts — every net GEX must be negative
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_puts_all_negative_gex(all_puts_chain: list[dict[str, Any]]) -> None:
    """
    When the chain contains only put contracts every net GEX must be < 0 and
    the total GEX must be < 0.
    """
    result = await calculate_gex(all_puts_chain, CURRENT_PRICE)

    assert len(result.strikes) == 2

    for row in result.strikes:
        assert row.call_gex == pytest.approx(0.0, abs=1.0), (
            f"Strike {row.strike}: expected call_gex≈0, got {row.call_gex}"
        )
        assert row.put_gex < 0, (
            f"Strike {row.strike}: put_gex should be negative, got {row.put_gex}"
        )
        assert row.net_gex < 0, (
            f"Strike {row.strike}: net_gex should be negative, got {row.net_gex}"
        )

    assert result.total_gex < 0, "Total GEX should be negative for all-puts chain"
    assert result.gamma_flip is None, "No gamma flip expected in all-puts scenario"


# ---------------------------------------------------------------------------
# Test 7: Empty options chain returns sensible defaults
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_chain_returns_defaults() -> None:
    """An empty chain must return a GexResult with zeros/None — no exception."""
    result = await calculate_gex([], CURRENT_PRICE)

    assert isinstance(result, GexResult)
    assert result.current_price == CURRENT_PRICE
    assert result.total_gex == pytest.approx(0.0)
    assert result.strikes == []
    assert result.gamma_flip is None
    assert result.key_levels.max_positive_gex is None
    assert result.key_levels.max_negative_gex is None
    assert result.key_levels.gamma_flip is None
    assert result.last_updated  # non-empty timestamp


# ---------------------------------------------------------------------------
# Test 8: Key levels are correctly identified
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_key_levels_identified() -> None:
    """
    max_positive_gex should point to the strike with the highest net GEX.
    max_negative_gex should point to the strike with the most negative net GEX.
    """
    expiry = _future_date(30)
    # K=900 pure puts → large negative GEX
    # K=950 mixed    → small positive GEX
    # K=980 pure calls → large positive GEX
    chain: list[dict[str, Any]] = [
        {
            "strike": 900.0,
            "expirationDate": expiry,
            "type": "put",
            "openInterest": 8000,
            "impliedVolatility": 0.65,
            "lastPrice": 10.00,
            "bid": 9.50,
            "ask": 10.50,
        },
        {
            "strike": 950.0,
            "expirationDate": expiry,
            "type": "call",
            "openInterest": 500,
            "impliedVolatility": 0.55,
            "lastPrice": 35.00,
            "bid": 34.50,
            "ask": 35.50,
        },
        {
            "strike": 950.0,
            "expirationDate": expiry,
            "type": "put",
            "openInterest": 400,
            "impliedVolatility": 0.55,
            "lastPrice": 30.00,
            "bid": 29.50,
            "ask": 30.50,
        },
        {
            "strike": 980.0,
            "expirationDate": expiry,
            "type": "call",
            "openInterest": 10000,
            "impliedVolatility": 0.50,
            "lastPrice": 20.00,
            "bid": 19.50,
            "ask": 20.50,
        },
    ]

    result = await calculate_gex(chain, CURRENT_PRICE)

    # max_positive_gex should be 980 (largest call OI)
    assert result.key_levels.max_positive_gex == 980.0, (
        f"Expected max_positive_gex=980.0, got {result.key_levels.max_positive_gex}"
    )
    # max_negative_gex should be 900 (large put OI, no calls)
    assert result.key_levels.max_negative_gex == 900.0, (
        f"Expected max_negative_gex=900.0, got {result.key_levels.max_negative_gex}"
    )


# ---------------------------------------------------------------------------
# Test 9: Multiple expirations aggregate correctly for the same strike
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_expirations_aggregate(
    multi_expiry_chain: list[dict[str, Any]],
) -> None:
    """
    Two call contracts at the same strike K=950 with different expirations
    must be summed into a single GexStrike row.

    The combined call_gex must be strictly greater than either single-expiry
    contribution (both are positive).
    """
    # Single expiry baseline: K=950, OI=2000, sigma=0.55
    expiry_30 = _future_date(30)
    single_contract: list[dict[str, Any]] = [
        {
            "strike": 950.0,
            "expirationDate": expiry_30,
            "type": "call",
            "openInterest": 2000,
            "impliedVolatility": 0.55,
            "lastPrice": 35.00,
            "bid": 34.50,
            "ask": 35.50,
        }
    ]

    result_single = await calculate_gex(single_contract, CURRENT_PRICE)
    result_multi = await calculate_gex(multi_expiry_chain, CURRENT_PRICE)

    # Both results should have exactly one strike row at K=950
    assert len(result_single.strikes) == 1
    assert len(result_multi.strikes) == 1
    assert result_multi.strikes[0].strike == 950.0

    single_gex = result_single.strikes[0].call_gex
    multi_gex = result_multi.strikes[0].call_gex

    # Two expirations must contribute more than one
    assert multi_gex > single_gex, (
        f"Aggregated GEX ({multi_gex:.4e}) should exceed single-expiry GEX ({single_gex:.4e})"
    )


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------


class TestBsGamma:
    """Unit tests for the _bs_gamma helper."""

    def test_gamma_is_positive(self) -> None:
        """Gamma should always be non-negative."""
        g = _bs_gamma(S=950, K=950, r=0.045, sigma=0.55, T=30 / 365)
        assert g > 0

    def test_gamma_atm_exceeds_otm(self) -> None:
        """ATM gamma > OTM gamma for same tenor and vol."""
        g_atm = _bs_gamma(S=950, K=950, r=0.045, sigma=0.55, T=30 / 365)
        g_otm = _bs_gamma(S=950, K=1050, r=0.045, sigma=0.55, T=30 / 365)
        assert g_atm > g_otm

    def test_gamma_zero_on_tiny_sigma_sqrt_t(self) -> None:
        """Gamma returns 0 when sigma*sqrt(T) is below the guard threshold."""
        # Extremely short T with realistic sigma still triggers the guard
        g = _bs_gamma(S=950, K=950, r=0.045, sigma=1e-6, T=1e-12)
        assert g == 0.0


class TestBsPrice:
    """Unit tests for Black-Scholes pricing used in IV bisection."""

    def test_call_price_positive(self) -> None:
        price = _bs_price(S=950, K=950, r=0.045, sigma=0.55, T=30 / 365, option_type="call")
        assert price > 0

    def test_put_price_positive(self) -> None:
        price = _bs_price(S=950, K=950, r=0.045, sigma=0.55, T=30 / 365, option_type="put")
        assert price > 0

    def test_put_call_parity(self) -> None:
        """C - P ≈ S - K*exp(-rT) (put-call parity)."""
        S, K, r, sigma, T = 950.0, 950.0, 0.045, 0.55, 30 / 365.0
        call = _bs_price(S, K, r, sigma, T, "call")
        put = _bs_price(S, K, r, sigma, T, "put")
        parity_lhs = call - put
        parity_rhs = S - K * math.exp(-r * T)
        assert parity_lhs == pytest.approx(parity_rhs, abs=1e-6)

    def test_deep_itm_call_near_intrinsic(self) -> None:
        """Deep ITM call price should be close to its intrinsic value."""
        S, K, r, sigma, T = 950.0, 500.0, 0.045, 0.55, 30 / 365.0
        price = _bs_price(S, K, r, sigma, T, "call")
        intrinsic = S - K * math.exp(-r * T)
        assert price == pytest.approx(intrinsic, rel=0.01)


class TestIVBisection:
    """Unit tests for _implied_volatility_bisection."""

    def test_round_trip(self) -> None:
        """
        Price at a known sigma, then recover sigma via bisection.
        Result should match the original sigma within bisection tolerance.
        """
        S, K, r, sigma_true, T = 950.0, 950.0, 0.045, 0.55, 30 / 365.0
        market_price = _bs_price(S, K, r, sigma_true, T, "call")
        recovered = _implied_volatility_bisection(market_price, S, K, r, T, "call")
        assert recovered is not None
        assert recovered == pytest.approx(sigma_true, abs=1e-3)

    def test_zero_market_price_returns_none(self) -> None:
        """A market price of 0 should not produce a valid IV."""
        result = _implied_volatility_bisection(0.0, 950.0, 950.0, 0.045, 30 / 365, "call")
        assert result is None

    def test_negative_market_price_returns_none(self) -> None:
        result = _implied_volatility_bisection(-5.0, 950.0, 950.0, 0.045, 30 / 365, "call")
        assert result is None

    def test_put_round_trip(self) -> None:
        """Round-trip IV recovery for a put contract."""
        S, K, r, sigma_true, T = 950.0, 970.0, 0.045, 0.48, 45 / 365.0
        market_price = _bs_price(S, K, r, sigma_true, T, "put")
        recovered = _implied_volatility_bisection(market_price, S, K, r, T, "put")
        assert recovered is not None
        assert recovered == pytest.approx(sigma_true, abs=1e-3)


class TestFindGammaFlip:
    """Unit tests for the _find_gamma_flip helper."""

    def test_basic_crossing(self) -> None:
        rows = [
            GexStrike(strike=900.0, call_gex=0.0, put_gex=-5e8, net_gex=-5e8),
            GexStrike(strike=950.0, call_gex=0.0, put_gex=-1e8, net_gex=-1e8),
            GexStrike(strike=1000.0, call_gex=2e9, put_gex=0.0, net_gex=2e9),
        ]
        assert _find_gamma_flip(rows) == 1000.0

    def test_no_crossing_all_negative(self) -> None:
        rows = [
            GexStrike(strike=900.0, call_gex=0.0, put_gex=-5e8, net_gex=-5e8),
            GexStrike(strike=950.0, call_gex=0.0, put_gex=-1e8, net_gex=-1e8),
        ]
        assert _find_gamma_flip(rows) is None

    def test_no_crossing_all_positive(self) -> None:
        rows = [
            GexStrike(strike=900.0, call_gex=5e8, put_gex=0.0, net_gex=5e8),
            GexStrike(strike=950.0, call_gex=1e9, put_gex=0.0, net_gex=1e9),
        ]
        assert _find_gamma_flip(rows) is None

    def test_empty_list(self) -> None:
        assert _find_gamma_flip([]) is None

    def test_crossing_returns_first_positive_strike(self) -> None:
        """When there are multiple positive strikes after a negative one,
        the flip must be the first positive strike."""
        rows = [
            GexStrike(strike=900.0, call_gex=0.0, put_gex=-1e9, net_gex=-1e9),
            GexStrike(strike=950.0, call_gex=5e8, put_gex=0.0, net_gex=5e8),
            GexStrike(strike=1000.0, call_gex=2e9, put_gex=0.0, net_gex=2e9),
        ]
        assert _find_gamma_flip(rows) == 950.0


class TestTimeToExpiryYears:
    """Unit tests for _time_to_expiry_years."""

    def test_future_date_positive(self) -> None:
        future = _future_date(30)
        T = _time_to_expiry_years(future)
        assert T > 0

    def test_past_date_non_positive(self) -> None:
        past = _past_date(1)
        T = _time_to_expiry_years(past)
        assert T <= 0

    def test_invalid_date_returns_zero(self) -> None:
        T = _time_to_expiry_years("not-a-date")
        assert T == 0.0

    def test_approximate_value(self) -> None:
        """30-day expiry should be close to 30/365."""
        future = _future_date(30)
        T = _time_to_expiry_years(future)
        expected = 30 / 365.0
        assert T == pytest.approx(expected, abs=2 / 365.0)
