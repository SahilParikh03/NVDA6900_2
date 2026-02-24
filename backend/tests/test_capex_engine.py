"""
Tests for backend.engines.capex_engine.

All tests use synthetic fixture data — no live FMP calls.

Run with:
    pytest backend/tests/test_capex_engine.py -v
"""

import pytest

from backend.engines.capex_engine import (
    CapexResult,
    calculate_capex,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _cashflow(
    date: str,
    symbol: str,
    period: str,
    calendar_year: str,
    capex: float,
) -> dict:
    """Return a minimal FMP cash flow statement record."""
    return {
        "date": date,
        "symbol": symbol,
        "period": period,
        "calendarYear": calendar_year,
        "capitalExpenditure": capex,  # negative as per FMP convention
    }


def _income(date: str, symbol: str, revenue: float) -> dict:
    """Return a minimal FMP income statement record."""
    return {
        "date": date,
        "symbol": symbol,
        "revenue": revenue,
    }


# Realistic multi-quarter MSFT fixture (CapEx increasing QoQ)
MSFT_CASHFLOW = [
    _cashflow("2025-03-31", "MSFT", "Q3", "2025", -13_000_000_000),
    _cashflow("2025-06-30", "MSFT", "Q4", "2025", -14_000_000_000),
    _cashflow("2025-09-30", "MSFT", "Q1", "2026", -14_200_000_000),
]
MSFT_INCOME = [
    _income("2025-03-31", "MSFT", 61_000_000_000),
    _income("2025-06-30", "MSFT", 64_000_000_000),
    _income("2025-09-30", "MSFT", 65_600_000_000),
]

# AMZN — CapEx decreasing in latest quarter
AMZN_CASHFLOW = [
    _cashflow("2025-06-30", "AMZN", "Q2", "2025", -25_000_000_000),
    _cashflow("2025-09-30", "AMZN", "Q3", "2025", -22_000_000_000),
]
AMZN_INCOME = [
    _income("2025-06-30", "AMZN", 150_000_000_000),
    _income("2025-09-30", "AMZN", 158_000_000_000),
]

# GOOGL — only one quarter available
GOOGL_CASHFLOW = [
    _cashflow("2025-09-30", "GOOGL", "Q3", "2025", -13_000_000_000),
]
GOOGL_INCOME = [
    _income("2025-09-30", "GOOGL", 88_000_000_000),
]

# META — CapEx increasing QoQ
META_CASHFLOW = [
    _cashflow("2025-06-30", "META", "Q2", "2025", -8_000_000_000),
    _cashflow("2025-09-30", "META", "Q3", "2025", -10_000_000_000),
]
META_INCOME = [
    _income("2025-06-30", "META", 42_000_000_000),
    _income("2025-09-30", "META", 45_000_000_000),
]


def _full_companies_data() -> dict[str, dict]:
    return {
        "MSFT": {"cashflow": MSFT_CASHFLOW, "income": MSFT_INCOME, "name": "Microsoft"},
        "AMZN": {"cashflow": AMZN_CASHFLOW, "income": AMZN_INCOME, "name": "Amazon"},
        "GOOGL": {"cashflow": GOOGL_CASHFLOW, "income": GOOGL_INCOME, "name": "Alphabet"},
        "META": {"cashflow": META_CASHFLOW, "income": META_INCOME, "name": "Meta"},
    }


# ---------------------------------------------------------------------------
# Test 1 — Basic happy-path: correct types and schema
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_result_schema() -> None:
    """calculate_capex must return a valid CapexResult with correct structure."""
    result = await calculate_capex(_full_companies_data())

    assert isinstance(result, CapexResult)
    assert isinstance(result.companies, list)
    assert isinstance(result.aggregate_trend, str)
    assert isinstance(result.last_updated, str)
    # ISO-8601 timestamp sanity check
    assert "T" in result.last_updated


# ---------------------------------------------------------------------------
# Test 2 — Correct number of companies in output
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_company_count() -> None:
    """Result must contain one CapexCompany entry per symbol provided."""
    result = await calculate_capex(_full_companies_data())
    symbols = {c.symbol for c in result.companies}
    assert symbols == {"MSFT", "AMZN", "GOOGL", "META"}


# ---------------------------------------------------------------------------
# Test 3 — CapEx is always positive (abs applied correctly)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_capex_always_positive() -> None:
    """Raw negative FMP capitalExpenditure must be stored as positive in output."""
    result = await calculate_capex(_full_companies_data())
    for company in result.companies:
        for quarter in company.quarters:
            assert quarter.capex >= 0.0, (
                f"{company.symbol} has negative capex: {quarter.capex}"
            )


# ---------------------------------------------------------------------------
# Test 4 — capex_to_revenue_ratio calculation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_capex_to_revenue_ratio() -> None:
    """capex_to_revenue must equal abs(capex) / revenue for each quarter."""
    result = await calculate_capex(_full_companies_data())
    msft = next(c for c in result.companies if c.symbol == "MSFT")

    for q in msft.quarters:
        expected = q.capex / q.revenue
        assert abs(q.capex_to_revenue - expected) < 1e-9, (
            f"Ratio mismatch for {q.period}: expected {expected}, got {q.capex_to_revenue}"
        )


# ---------------------------------------------------------------------------
# Test 5 — QoQ growth on first quarter is 0.0
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_first_quarter_qoq_growth_is_zero() -> None:
    """The earliest quarter for each company must have capex_qoq_growth == 0.0."""
    result = await calculate_capex(_full_companies_data())
    for company in result.companies:
        if company.quarters:
            assert company.quarters[0].capex_qoq_growth == 0.0, (
                f"{company.symbol} first quarter QoQ growth should be 0.0, "
                f"got {company.quarters[0].capex_qoq_growth}"
            )


# ---------------------------------------------------------------------------
# Test 6 — QoQ growth calculation accuracy
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_qoq_growth_accuracy() -> None:
    """QoQ growth must equal (current - previous) / abs(previous)."""
    result = await calculate_capex(_full_companies_data())
    msft = next(c for c in result.companies if c.symbol == "MSFT")

    # MSFT quarters sorted ascending: Q3 2025, Q4 2025, Q1 2026
    assert len(msft.quarters) == 3

    q3 = msft.quarters[0]  # 13B
    q4 = msft.quarters[1]  # 14B
    q1 = msft.quarters[2]  # 14.2B

    expected_q4_growth = (14_000_000_000 - 13_000_000_000) / 13_000_000_000
    expected_q1_growth = (14_200_000_000 - 14_000_000_000) / 14_000_000_000

    assert q3.capex_qoq_growth == 0.0
    assert abs(q4.capex_qoq_growth - expected_q4_growth) < 1e-9
    assert abs(q1.capex_qoq_growth - expected_q1_growth) < 1e-9


# ---------------------------------------------------------------------------
# Test 7 — Only one quarter: QoQ growth must be 0.0 and no crash
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_quarter_company() -> None:
    """A company with only one quarter must produce qoq_growth=0.0 without errors."""
    result = await calculate_capex(_full_companies_data())
    googl = next(c for c in result.companies if c.symbol == "GOOGL")

    assert len(googl.quarters) == 1
    assert googl.quarters[0].capex_qoq_growth == 0.0


# ---------------------------------------------------------------------------
# Test 8 — Empty companies_data returns empty result
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_companies_data() -> None:
    """An empty companies_data dict must return a CapexResult with no companies."""
    result = await calculate_capex({})

    assert result.companies == []
    assert isinstance(result.aggregate_trend, str)


# ---------------------------------------------------------------------------
# Test 9 — Missing capitalExpenditure field skips the quarter
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_capex_field_skips_quarter() -> None:
    """Quarters with missing capitalExpenditure must be omitted from the output."""
    companies_data = {
        "MSFT": {
            "cashflow": [
                # Valid quarter
                _cashflow("2025-09-30", "MSFT", "Q1", "2026", -14_200_000_000),
                # Quarter missing capitalExpenditure entirely
                {
                    "date": "2025-06-30",
                    "symbol": "MSFT",
                    "period": "Q4",
                    "calendarYear": "2025",
                    # no capitalExpenditure key
                },
            ],
            "income": [
                _income("2025-09-30", "MSFT", 65_600_000_000),
                _income("2025-06-30", "MSFT", 64_000_000_000),
            ],
            "name": "Microsoft",
        }
    }

    result = await calculate_capex(companies_data)
    msft = next(c for c in result.companies if c.symbol == "MSFT")
    # Only the valid quarter should appear
    assert len(msft.quarters) == 1
    assert msft.quarters[0].period == "Q1 2026"


# ---------------------------------------------------------------------------
# Test 10 — Missing revenue / zero revenue skips the quarter
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_revenue_skips_quarter() -> None:
    """
    A quarter with zero revenue must be excluded to avoid division by zero.
    A quarter with no matching income statement record must also be excluded.
    """
    companies_data = {
        "AMZN": {
            "cashflow": [
                _cashflow("2025-09-30", "AMZN", "Q3", "2025", -22_000_000_000),
                _cashflow("2025-06-30", "AMZN", "Q2", "2025", -25_000_000_000),
            ],
            "income": [
                # Q3 has zero revenue
                _income("2025-09-30", "AMZN", 0),
                # Q2 has no income record at all (will be missing from map)
            ],
            "name": "Amazon",
        }
    }

    result = await calculate_capex(companies_data)
    amzn = next(c for c in result.companies if c.symbol == "AMZN")
    assert amzn.quarters == [], (
        f"Expected no quarters when revenue is 0 or missing, got {amzn.quarters}"
    )


# ---------------------------------------------------------------------------
# Test 11 — Previous CapEx zero guards QoQ growth as 0.0
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_previous_capex_guard() -> None:
    """When previous quarter CapEx is 0, QoQ growth must be 0.0 (no division by zero)."""
    companies_data = {
        "META": {
            "cashflow": [
                # First quarter: zero CapEx (unusual but must not crash)
                {
                    "date": "2025-03-31",
                    "symbol": "META",
                    "period": "Q1",
                    "calendarYear": "2025",
                    "capitalExpenditure": 0,
                },
                _cashflow("2025-06-30", "META", "Q2", "2025", -10_000_000_000),
            ],
            "income": [
                _income("2025-03-31", "META", 36_000_000_000),
                _income("2025-06-30", "META", 42_000_000_000),
            ],
            "name": "Meta",
        }
    }

    result = await calculate_capex(companies_data)
    meta = next(c for c in result.companies if c.symbol == "META")
    assert len(meta.quarters) == 2
    # First quarter: no previous, so 0.0
    assert meta.quarters[0].capex_qoq_growth == 0.0
    # Second quarter: previous capex is 0 → must be guarded to 0.0
    assert meta.quarters[1].capex_qoq_growth == 0.0


# ---------------------------------------------------------------------------
# Test 12 — Empty cashflow list produces empty quarters, no crash
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_cashflow_list() -> None:
    """A company with no cashflow records must appear in output with empty quarters."""
    companies_data = {
        "GOOGL": {
            "cashflow": [],
            "income": [_income("2025-09-30", "GOOGL", 88_000_000_000)],
            "name": "Alphabet",
        }
    }

    result = await calculate_capex(companies_data)
    googl = next(c for c in result.companies if c.symbol == "GOOGL")
    assert googl.quarters == []


# ---------------------------------------------------------------------------
# Test 13 — aggregate_trend: majority increasing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_trend_increasing() -> None:
    """When the majority of companies have positive latest QoQ growth, trend='increasing'."""
    # MSFT +, AMZN - -> 1v1, META + -> 2 positive 1 negative → majority positive
    companies_data = {
        "MSFT": {"cashflow": MSFT_CASHFLOW, "income": MSFT_INCOME, "name": "Microsoft"},
        "AMZN": {"cashflow": AMZN_CASHFLOW, "income": AMZN_INCOME, "name": "Amazon"},
        "META": {"cashflow": META_CASHFLOW, "income": META_INCOME, "name": "Meta"},
    }
    result = await calculate_capex(companies_data)
    assert result.aggregate_trend == "increasing"


# ---------------------------------------------------------------------------
# Test 14 — aggregate_trend: all single-quarter companies → mixed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_trend_mixed_when_no_qoq_data() -> None:
    """When no company has enough quarters for QoQ, trend should be 'mixed'."""
    companies_data = {
        "GOOGL": {
            "cashflow": [_cashflow("2025-09-30", "GOOGL", "Q3", "2025", -13_000_000_000)],
            "income": [_income("2025-09-30", "GOOGL", 88_000_000_000)],
            "name": "Alphabet",
        }
    }
    result = await calculate_capex(companies_data)
    assert result.aggregate_trend == "mixed"


# ---------------------------------------------------------------------------
# Test 15 — Name fallback to HYPERSCALER_NAMES constant
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_company_name_fallback() -> None:
    """When 'name' key is absent, the engine must use the HYPERSCALER_NAMES constant."""
    companies_data = {
        "MSFT": {
            "cashflow": MSFT_CASHFLOW,
            "income": MSFT_INCOME,
            # no "name" key
        }
    }
    result = await calculate_capex(companies_data)
    msft = next(c for c in result.companies if c.symbol == "MSFT")
    assert msft.name == "Microsoft"
