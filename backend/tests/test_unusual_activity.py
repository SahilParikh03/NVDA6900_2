"""
Tests for backend.engines.unusual_activity.scan_unusual_activity.

All tests use mock fixture data — no live FMP calls are made.

Run with:
    pytest backend/tests/test_unusual_activity.py -v
"""

import pytest

from backend.engines.unusual_activity import (
    MAX_UNUSUAL_RESULTS,
    MIN_VOLUME_FILTER,
    VOL_OI_RATIO_THRESHOLD,
    UnusualActivityResult,
    scan_unusual_activity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_contract(
    strike: float = 960.0,
    expiration: str = "2026-03-07",
    contract_type: str = "call",
    open_interest: int = 3200,
    volume: int = 15420,
    implied_volatility: float = 0.65,
    last_price: float = 12.50,
) -> dict:
    """Return a minimal FMP-style options contract dict."""
    return {
        "symbol": "NVDA",
        "strike": strike,
        "expirationDate": expiration,
        "type": contract_type,
        "openInterest": open_interest,
        "volume": volume,
        "impliedVolatility": implied_volatility,
        "lastPrice": last_price,
        "bid": last_price - 0.5,
        "ask": last_price + 0.5,
    }


TYPICAL_CHAIN: list[dict] = [
    # Unusual: ratio = 15420/3200 = 4.82, volume > 1000
    _make_contract(strike=960.0, contract_type="call", open_interest=3200, volume=15420),
    # Unusual: ratio = 8000/2000 = 4.0, volume > 1000
    _make_contract(strike=950.0, contract_type="put", open_interest=2000, volume=8000),
    # Not unusual: ratio = 1500/1000 = 1.5 (below threshold)
    _make_contract(strike=940.0, contract_type="call", open_interest=1000, volume=1500),
    # Not unusual: ratio = 5.0 but volume < 1000
    _make_contract(strike=930.0, contract_type="call", open_interest=200, volume=900),
    # Not unusual: ratio = 3.0 but volume exactly at threshold boundary (volume=1000, <=1000)
    _make_contract(strike=920.0, contract_type="put", open_interest=333, volume=1000),
]


# ---------------------------------------------------------------------------
# 1. Happy-path: returns correct flagged contracts
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_happy_path_returns_unusual_contracts() -> None:
    """Contracts above both thresholds must appear in unusual_activity."""
    result: UnusualActivityResult = await scan_unusual_activity(TYPICAL_CHAIN)

    assert isinstance(result, UnusualActivityResult)
    assert result.total_unusual_contracts == 2
    assert len(result.unusual_activity) == 2


# ---------------------------------------------------------------------------
# 2. Contracts are sorted by vol_oi_ratio descending
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sorted_descending_by_ratio() -> None:
    """unusual_activity list must be sorted by vol_oi_ratio descending."""
    result: UnusualActivityResult = await scan_unusual_activity(TYPICAL_CHAIN)

    ratios = [c.vol_oi_ratio for c in result.unusual_activity]
    assert ratios == sorted(ratios, reverse=True), (
        f"Expected descending order, got {ratios}"
    )


# ---------------------------------------------------------------------------
# 3. vol_oi_ratio is computed correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_vol_oi_ratio_calculation() -> None:
    """vol_oi_ratio must equal volume / open_interest."""
    chain = [_make_contract(open_interest=3200, volume=15420)]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    contract = result.unusual_activity[0]
    expected_ratio = round(15420 / 3200, 4)
    assert contract.vol_oi_ratio == pytest.approx(expected_ratio, rel=1e-4)


# ---------------------------------------------------------------------------
# 4. Empty options chain → empty result with zero counts
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_chain_returns_empty_result() -> None:
    """An empty options chain must return an empty UnusualActivityResult."""
    result: UnusualActivityResult = await scan_unusual_activity([])

    assert result.unusual_activity == []
    assert result.total_unusual_contracts == 0
    assert result.put_call_ratio_unusual == 0.0


# ---------------------------------------------------------------------------
# 5. Zero open interest: contract is skipped (no ZeroDivisionError)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_open_interest_skipped() -> None:
    """Contracts with zero open interest must be skipped without raising."""
    chain = [
        _make_contract(open_interest=0, volume=50000),   # zero OI — skip
        _make_contract(open_interest=1000, volume=5000), # normal unusual
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    # Only the second contract qualifies
    assert result.total_unusual_contracts == 1
    assert result.unusual_activity[0].open_interest == 1000


# ---------------------------------------------------------------------------
# 6. Zero volume: contract is skipped
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_volume_skipped() -> None:
    """Contracts with zero volume must be skipped."""
    chain = [
        _make_contract(open_interest=1000, volume=0),    # zero volume — skip
        _make_contract(open_interest=1000, volume=5000), # normal unusual
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    assert result.total_unusual_contracts == 1


# ---------------------------------------------------------------------------
# 7. All contracts below threshold → empty unusual_activity list
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_all_below_threshold_returns_empty_list() -> None:
    """When no contract meets both thresholds, unusual_activity must be empty."""
    below_threshold_chain = [
        # ratio = 1.5 (below VOL_OI_RATIO_THRESHOLD of 2.0)
        _make_contract(open_interest=1000, volume=1500),
        # volume = 500 (below MIN_VOLUME_FILTER of 1000)
        _make_contract(open_interest=100, volume=500),
    ]
    result: UnusualActivityResult = await scan_unusual_activity(below_threshold_chain)

    assert result.unusual_activity == []
    assert result.total_unusual_contracts == 0
    assert result.put_call_ratio_unusual == 0.0


# ---------------------------------------------------------------------------
# 8. put_call_ratio_unusual calculated correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_put_call_ratio_correct() -> None:
    """put_call_ratio = puts / calls among flagged contracts."""
    chain = [
        # 2 calls
        _make_contract(strike=960.0, contract_type="call", open_interest=1000, volume=5000),
        _make_contract(strike=950.0, contract_type="call", open_interest=1000, volume=5000),
        # 1 put
        _make_contract(strike=940.0, contract_type="put", open_interest=1000, volume=5000),
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    # 1 put / 2 calls = 0.5
    assert result.put_call_ratio_unusual == pytest.approx(0.5, rel=1e-4)


# ---------------------------------------------------------------------------
# 9. put_call_ratio when no calls in unusual set → 0.0
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_put_call_ratio_no_calls_is_zero() -> None:
    """If all unusual contracts are puts, put_call_ratio must be 0.0 (not raise)."""
    chain = [
        _make_contract(strike=960.0, contract_type="put", open_interest=1000, volume=5000),
        _make_contract(strike=950.0, contract_type="put", open_interest=1000, volume=5000),
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    assert result.put_call_ratio_unusual == 0.0


# ---------------------------------------------------------------------------
# 10. Top-20 cap: only MAX_UNUSUAL_RESULTS entries returned
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_top_20_cap() -> None:
    """When more than 20 contracts are flagged, only the top 20 are returned."""
    large_chain = [
        _make_contract(
            strike=float(900 + i),
            open_interest=1000,
            volume=5000 + i * 10,  # incrementing volume → different ratios
        )
        for i in range(30)  # 30 unusual contracts
    ]
    result: UnusualActivityResult = await scan_unusual_activity(large_chain)

    assert result.total_unusual_contracts == 30
    assert len(result.unusual_activity) == MAX_UNUSUAL_RESULTS


# ---------------------------------------------------------------------------
# 11. contract type is uppercased in output
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_contract_type_uppercased() -> None:
    """Output contract type must be uppercase regardless of FMP input casing."""
    chain = [
        _make_contract(contract_type="call"),
        _make_contract(contract_type="PUT", strike=950.0),
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    types = {c.type for c in result.unusual_activity}
    assert all(t == t.upper() for t in types), f"Expected uppercase types, got: {types}"


# ---------------------------------------------------------------------------
# 12. last_updated is a non-empty UTC timestamp string
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_last_updated_is_utc_string() -> None:
    """last_updated must be a non-empty string ending in 'Z'."""
    result: UnusualActivityResult = await scan_unusual_activity(TYPICAL_CHAIN)

    assert isinstance(result.last_updated, str)
    assert result.last_updated.endswith("Z")
    assert len(result.last_updated) > 0


# ---------------------------------------------------------------------------
# 13. Missing optional fields default gracefully (no KeyError)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_optional_fields_default_gracefully() -> None:
    """Contracts with missing IV/lastPrice must not raise; defaults to 0.0."""
    minimal_contract = {
        "strike": 960.0,
        "expirationDate": "2026-03-07",
        "type": "call",
        "openInterest": 1000,
        "volume": 5000,
        # impliedVolatility and lastPrice deliberately omitted
    }
    result: UnusualActivityResult = await scan_unusual_activity([minimal_contract])

    assert result.total_unusual_contracts == 1
    contract = result.unusual_activity[0]
    assert contract.implied_volatility == 0.0
    assert contract.last_price == 0.0


# ---------------------------------------------------------------------------
# 14. Boundary: volume exactly at MIN_VOLUME_FILTER is NOT flagged
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_volume_at_boundary_not_flagged() -> None:
    """volume == MIN_VOLUME_FILTER (1000) does NOT satisfy volume > 1000."""
    chain = [
        _make_contract(open_interest=100, volume=MIN_VOLUME_FILTER),  # ratio=10 but volume not >1000
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    assert result.total_unusual_contracts == 0


# ---------------------------------------------------------------------------
# 15. Boundary: ratio exactly at VOL_OI_RATIO_THRESHOLD is NOT flagged
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ratio_at_boundary_not_flagged() -> None:
    """vol_oi_ratio == VOL_OI_RATIO_THRESHOLD (2.0) does NOT satisfy ratio > 2.0."""
    chain = [
        _make_contract(open_interest=1000, volume=2000),  # ratio == 2.0, not > 2.0
    ]
    result: UnusualActivityResult = await scan_unusual_activity(chain)

    assert result.total_unusual_contracts == 0
