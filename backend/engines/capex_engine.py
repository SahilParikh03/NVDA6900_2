"""
CapEx Engine — tracks capital expenditure trends for NVDA's hyperscaler customers.

Accepts raw FMP cash flow and income statement data for MSFT, AMZN, GOOGL,
and META, then produces per-company quarterly CapEx metrics plus an aggregate
demand trend indicator for NVDA GPU demand inference.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HYPERSCALER_NAMES: dict[str, str] = {
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
}

# Trend labels
TREND_INCREASING = "increasing"
TREND_DECREASING = "decreasing"
TREND_MIXED = "mixed"
TREND_STABLE = "stable"


# ---------------------------------------------------------------------------
# Output models (Pydantic v2)
# ---------------------------------------------------------------------------


class CapexQuarter(BaseModel):
    """CapEx metrics for a single company quarter."""

    period: str = Field(description="Quarter label, e.g. 'Q1 2026'")
    capex: float = Field(description="Absolute CapEx in dollars (always positive)")
    revenue: float = Field(description="Revenue in dollars")
    capex_to_revenue: float = Field(description="CapEx as a fraction of revenue")
    capex_qoq_growth: float = Field(
        description="Quarter-over-quarter CapEx growth rate (0.0 when unavailable)"
    )


class CapexCompany(BaseModel):
    """Per-company CapEx data across all available quarters."""

    symbol: str
    name: str
    quarters: list[CapexQuarter] = Field(default_factory=list)


class CapexResult(BaseModel):
    """Top-level output of the CapEx engine."""

    companies: list[CapexCompany] = Field(default_factory=list)
    aggregate_trend: str = Field(
        description=(
            "'increasing' if majority of companies show positive QoQ CapEx growth, "
            "'decreasing' if majority negative, 'mixed' otherwise"
        )
    )
    last_updated: str = Field(description="ISO-8601 UTC timestamp")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _period_label(period: str, calendar_year: str) -> str:
    """Return a human-readable quarter label, e.g. 'Q1 2026'."""
    return f"{period} {calendar_year}".strip()


def _build_revenue_map(income_records: list[dict]) -> dict[str, float]:
    """
    Build a mapping of date string → revenue from income statement records.

    Skips records where revenue is missing, None, or zero.
    """
    revenue_map: dict[str, float] = {}
    for record in income_records:
        date = record.get("date")
        revenue = record.get("revenue")
        if not date:
            continue
        if revenue is None:
            logger.debug("Skipping income record with missing revenue (date=%s)", date)
            continue
        try:
            rev_float = float(revenue)
        except (TypeError, ValueError):
            logger.warning(
                "Cannot convert revenue to float for date=%s value=%r", date, revenue
            )
            continue
        if rev_float == 0.0:
            logger.debug("Skipping income record with zero revenue (date=%s)", date)
            continue
        revenue_map[date] = rev_float
    return revenue_map


def _process_company(
    symbol: str,
    name: str,
    cashflow_records: list[dict],
    income_records: list[dict],
) -> CapexCompany:
    """
    Process a single company's raw FMP data into a CapexCompany result.

    Quarters are sorted ascending by date so QoQ calculation is straightforward.
    """
    revenue_map = _build_revenue_map(income_records)

    # Collect valid (date, capex, revenue) tuples sorted oldest → newest
    valid_quarters: list[tuple[str, str, str, float, float]] = []
    # (date, period, calendar_year, capex_abs, revenue)

    for record in cashflow_records:
        date = record.get("date")
        if not date:
            logger.debug("[%s] Skipping cashflow record with missing date", symbol)
            continue

        raw_capex = record.get("capitalExpenditure")
        if raw_capex is None:
            logger.debug(
                "[%s] Skipping date=%s — capitalExpenditure is missing/None",
                symbol,
                date,
            )
            continue

        try:
            capex_abs = abs(float(raw_capex))
        except (TypeError, ValueError):
            logger.warning(
                "[%s] Cannot convert capitalExpenditure to float for date=%s value=%r",
                symbol,
                date,
                raw_capex,
            )
            continue

        revenue = revenue_map.get(date)
        if revenue is None:
            logger.debug(
                "[%s] Skipping date=%s — no matching revenue in income statement",
                symbol,
                date,
            )
            continue

        period = record.get("period", "")
        calendar_year = record.get("calendarYear", "")
        valid_quarters.append((date, period, calendar_year, capex_abs, revenue))

    # Sort ascending by date string (ISO-8601 dates sort lexicographically)
    valid_quarters.sort(key=lambda x: x[0])

    quarters: list[CapexQuarter] = []
    for idx, (date, period, calendar_year, capex_abs, revenue) in enumerate(
        valid_quarters
    ):
        capex_to_revenue = capex_abs / revenue

        if idx == 0:
            capex_qoq_growth = 0.0
        else:
            prev_capex = valid_quarters[idx - 1][3]
            if prev_capex == 0.0:
                capex_qoq_growth = 0.0
                logger.debug(
                    "[%s] Previous CapEx is zero for date=%s; setting QoQ growth to 0.0",
                    symbol,
                    date,
                )
            else:
                capex_qoq_growth = (capex_abs - prev_capex) / abs(prev_capex)

        quarters.append(
            CapexQuarter(
                period=_period_label(period, calendar_year),
                capex=capex_abs,
                revenue=revenue,
                capex_to_revenue=capex_to_revenue,
                capex_qoq_growth=capex_qoq_growth,
            )
        )
        logger.debug(
            "[%s] date=%s capex=%.2f revenue=%.2f ratio=%.4f qoq=%.4f",
            symbol,
            date,
            capex_abs,
            revenue,
            capex_to_revenue,
            capex_qoq_growth,
        )

    return CapexCompany(symbol=symbol, name=name, quarters=quarters)


def _determine_aggregate_trend(companies: list[CapexCompany]) -> str:
    """
    Majority-vote across companies using their latest available QoQ growth figure.

    Returns "increasing", "decreasing", or "mixed".
    Only companies with at least 2 quarters (so QoQ is meaningful) are counted.
    """
    positive_count = 0
    negative_count = 0

    for company in companies:
        # Need at least 2 quarters for a meaningful QoQ signal
        if len(company.quarters) < 2:
            logger.debug(
                "[%s] Skipped in trend vote — fewer than 2 quarters", company.symbol
            )
            continue
        latest_growth = company.quarters[-1].capex_qoq_growth
        if latest_growth > 0.0:
            positive_count += 1
        elif latest_growth < 0.0:
            negative_count += 1
        # exactly 0.0 (flat QoQ, including guarded zero-prev case) counts for neither

    total_voting = positive_count + negative_count
    if total_voting == 0:
        return TREND_MIXED

    majority = total_voting / 2  # strict majority requires > half
    if positive_count > majority:
        return TREND_INCREASING
    if negative_count > majority:
        return TREND_DECREASING
    return TREND_MIXED


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def calculate_capex(
    companies_data: dict[str, dict],
) -> CapexResult:
    """
    Calculate CapEx metrics for all provided hyperscaler companies.

    Parameters
    ----------
    companies_data:
        Keyed by ticker symbol.  Each value must contain:
            - "cashflow": list[dict] — FMP cash flow statement records
            - "income":   list[dict] — FMP income statement records
            - "name":     str        — Company display name (optional; falls back to
                                       HYPERSCALER_NAMES or the symbol itself)

    Returns
    -------
    CapexResult
        Populated result with per-company quarters and an aggregate demand trend.
    """
    if not companies_data:
        logger.info("calculate_capex called with empty companies_data — returning empty result")
        return CapexResult(
            companies=[],
            aggregate_trend=TREND_MIXED,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    companies: list[CapexCompany] = []

    for symbol, data in companies_data.items():
        name = (
            data.get("name")
            or HYPERSCALER_NAMES.get(symbol)
            or symbol
        )
        cashflow_records: list[dict] = data.get("cashflow") or []
        income_records: list[dict] = data.get("income") or []

        logger.info(
            "[%s] Processing %d cashflow + %d income records",
            symbol,
            len(cashflow_records),
            len(income_records),
        )

        company_result = _process_company(symbol, name, cashflow_records, income_records)
        companies.append(company_result)

    aggregate_trend = _determine_aggregate_trend(companies)
    logger.info("Aggregate hyperscaler CapEx trend: %s", aggregate_trend)

    return CapexResult(
        companies=companies,
        aggregate_trend=aggregate_trend,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
