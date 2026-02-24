"""
Hyperscaler route module for the NVDA Earnings War Room.

Provides two endpoints:
  GET /api/hyperscaler/capex       — CapEx analysis for MSFT, AMZN, GOOGL, META
  GET /api/hyperscaler/transcripts — AI keyword analysis of earnings call transcripts
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.cache import cache
from backend.engines.capex_engine import calculate_capex
from backend.engines.transcript_nlp import analyze_transcripts

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HYPERSCALER_TICKERS: dict[str, str] = {
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
}

# Quarters to fetch per ticker for transcript analysis (year, quarter)
TRANSCRIPT_QUARTERS: list[tuple[int, int]] = [
    (2025, 4),
    (2025, 3),
    (2025, 2),
    (2025, 1),
]


# ---------------------------------------------------------------------------
# GET /capex
# ---------------------------------------------------------------------------

@router.get("/capex")
async def get_hyperscaler_capex(request: Request) -> dict[str, Any]:
    """
    Return CapEx analysis for all four hyperscaler companies.

    Data is sourced from the in-memory cache (populated by the scheduler every
    86400 s).  On a cache miss, the FMP client is called directly as a fallback.
    The engine handles missing data gracefully — partial results are always
    returned rather than a 503.
    """
    client = request.app.state.fmp_client
    companies_data: dict[str, dict] = {}

    for ticker, name in HYPERSCALER_TICKERS.items():
        # --- Cash flow ---
        cashflow: list[dict] | None = await cache.get(f"hyperscaler:cashflow:{ticker}")
        if cashflow is None:
            logger.info(
                "[%s] Cash flow not in cache — fetching from FMP", ticker
            )
            try:
                cashflow = await client.get_cash_flow_statement(
                    ticker, period="quarter", limit=8
                )
            except Exception as exc:
                logger.error(
                    "[%s] FMP cash flow fetch failed: %s", ticker, exc
                )
                cashflow = None

        # --- Income statement ---
        income: list[dict] | None = await cache.get(f"hyperscaler:income:{ticker}")
        if income is None:
            logger.info(
                "[%s] Income statement not in cache — fetching from FMP", ticker
            )
            try:
                income = await client.get_income_statement(
                    ticker, period="quarter", limit=8
                )
            except Exception as exc:
                logger.error(
                    "[%s] FMP income statement fetch failed: %s", ticker, exc
                )
                income = None

        companies_data[ticker] = {
            "cashflow": cashflow or [],
            "income": income or [],
            "name": name,
        }

    logger.info(
        "Calling calculate_capex with %d companies", len(companies_data)
    )
    try:
        result = await calculate_capex(companies_data)
    except Exception as exc:
        logger.error("calculate_capex raised an unexpected error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="CapEx engine error — please try again later",
        ) from exc

    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /transcripts
# ---------------------------------------------------------------------------

@router.get("/transcripts")
async def get_hyperscaler_transcripts(request: Request) -> dict[str, Any]:
    """
    Return AI keyword analysis of earnings call transcripts.

    Fetches the last four quarters for MSFT, AMZN, GOOGL, META, and NVDA via
    the FMP client.  Non-empty transcript responses are included in the NLP
    analysis.  Returns HTTP 503 only when the complete transcript list is empty
    after all fetch attempts.
    """
    client = request.app.state.fmp_client

    # Include NVDA alongside the standard hyperscaler tickers
    all_tickers: dict[str, str] = {**HYPERSCALER_TICKERS, "NVDA": "NVIDIA"}

    transcripts_list: list[dict] = []

    for ticker in all_tickers:
        for year, quarter in TRANSCRIPT_QUARTERS:
            try:
                result: list[dict] | None = await client.get_earning_call_transcript(
                    ticker, year=year, quarter=quarter
                )
            except Exception as exc:
                logger.error(
                    "[%s Q%d %d] Transcript fetch raised: %s", ticker, quarter, year, exc
                )
                continue

            if not result:
                logger.debug(
                    "[%s Q%d %d] Empty or None transcript response — skipping",
                    ticker, quarter, year,
                )
                continue

            # FMP returns a list; take the first element
            first = result[0] if isinstance(result, list) else result
            if not isinstance(first, dict):
                logger.warning(
                    "[%s Q%d %d] Unexpected transcript element type: %s",
                    ticker, quarter, year, type(first).__name__,
                )
                continue

            content = first.get("content")
            if not content:
                logger.warning(
                    "[%s Q%d %d] Transcript element missing 'content' field — skipping",
                    ticker, quarter, year,
                )
                continue

            transcripts_list.append(
                {
                    "symbol": ticker,
                    "quarter": quarter,
                    "year": year,
                    "content": content,
                }
            )
            logger.debug(
                "[%s Q%d %d] Transcript collected (%d chars)",
                ticker, quarter, year, len(content),
            )

    if not transcripts_list:
        logger.warning(
            "No transcripts collected for any ticker/quarter combination"
        )
        raise HTTPException(
            status_code=503,
            detail="Transcript data temporarily unavailable",
        )

    logger.info(
        "Calling analyze_transcripts with %d transcripts", len(transcripts_list)
    )
    try:
        result = await analyze_transcripts(transcripts_list)
    except Exception as exc:
        logger.error("analyze_transcripts raised an unexpected error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Transcript NLP engine error — please try again later",
        ) from exc

    return result.model_dump()
