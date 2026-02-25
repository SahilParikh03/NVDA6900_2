"""
FMP (Financial Modeling Prep) API client.

All HTTP calls to the external FMP API route through this module.
No other module in the project should make HTTP calls to FMP directly.

NOTE (2025-08+): FMP deprecated all /api/v3/ and /api/v4/ endpoints.
All active endpoints now route through https://financialmodelingprep.com/stable/.
Endpoints that are unavailable on the Starter plan or have been dropped from
the stable API keep their method signatures but return None immediately.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Retry configuration constants
_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 1.0  # seconds — doubles each retry: 1s, 2s, 4s
_REQUEST_TIMEOUT: float = 30.0  # seconds

# Fixed base for all stable endpoints — does NOT use settings.fmp_base_url
_STABLE_BASE: str = "https://financialmodelingprep.com/stable"


class FMPClient:
    """
    Async HTTP client for the Financial Modeling Prep API.

    All public methods map 1-to-1 to a specific FMP stable endpoint.
    Authentication is handled internally — callers never need to touch the
    API key.  Every method returns the parsed JSON payload on success or
    ``None`` on any failure (network error, 4xx/5xx, exhausted retries after
    429, or endpoint unavailable on current plan).

    Usage::

        client = FMPClient()
        quote = await client.get_quote("NVDA")
        await client.close()
    """

    def __init__(self) -> None:
        """Initialise the underlying ``httpx.AsyncClient`` with a fixed timeout."""
        self._api_key: str = settings.fmp_api_key
        # Kept for backward compatibility — stable URLs are fixed and do not
        # derive from this value, but removing it would break any code that
        # reads FMPClient._base_url externally.
        self._base_url: str = settings.fmp_base_url.rstrip("/")
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=httpx.Timeout(_REQUEST_TIMEOUT),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client and release any held connections."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Execute an HTTP request with exponential backoff on HTTP 429.

        The API key is appended to *params* before the request is sent and is
        never included in log output.

        Args:
            method: HTTP verb (``"GET"``, ``"POST"``, …).
            url: Fully-qualified URL for the request.
            params: Optional query parameters (API key is added automatically).

        Returns:
            Parsed JSON response body, or ``None`` on any failure.
        """
        request_params: Dict[str, Any] = dict(params) if params else {}
        request_params["apikey"] = self._api_key

        # Build a sanitised URL for logging (no API key)
        sanitised_params = {k: v for k, v in request_params.items() if k != "apikey"}
        log_url = str(httpx.URL(url, params=sanitised_params))

        for attempt in range(_MAX_RETRIES + 1):
            logger.debug("FMP request [attempt %d/%d]: %s %s", attempt + 1, _MAX_RETRIES + 1, method, log_url)
            try:
                response = await self._client.request(method, url, params=request_params)
            except httpx.TimeoutException as exc:
                logger.error(
                    "FMP request timed out: %s %s — %s",
                    method,
                    log_url,
                    exc,
                )
                return None
            except httpx.RequestError as exc:
                logger.error(
                    "FMP network error: %s %s — %s",
                    method,
                    log_url,
                    exc,
                )
                return None

            # Handle 429 — rate limited
            if response.status_code == 429:
                if attempt < _MAX_RETRIES:
                    backoff_seconds = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "FMP rate-limited (429) on %s %s — retrying in %.1fs (attempt %d/%d)",
                        method,
                        log_url,
                        backoff_seconds,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue
                else:
                    logger.error(
                        "FMP rate-limited (429) on %s %s — max retries (%d) exhausted",
                        method,
                        log_url,
                        _MAX_RETRIES,
                    )
                    return None

            # Handle all other HTTP errors
            if response.is_error:
                body_snippet = response.text[:500] if response.text else "<empty body>"
                logger.error(
                    "FMP HTTP error %d on %s %s — body: %s",
                    response.status_code,
                    method,
                    log_url,
                    body_snippet,
                )
                return None

            # Success — parse and return JSON
            try:
                return response.json()
            except Exception as exc:  # noqa: BLE001 — JSON parse errors vary
                logger.error(
                    "FMP JSON decode error on %s %s — %s",
                    method,
                    log_url,
                    exc,
                )
                return None

        # Should never be reached, but satisfy the type checker
        return None  # pragma: no cover

    def _stable(self, path: str) -> str:
        """Build a stable endpoint URL.  ``path`` must NOT start with a slash."""
        return f"{_STABLE_BASE}/{path}"

    # ------------------------------------------------------------------
    # Public API methods — active endpoints
    # ------------------------------------------------------------------

    async def get_quote(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch real-time quote data for a ticker.

        Endpoint: ``GET /stable/quote?symbol={ticker}``

        Returns fields such as price, change, changePercent, volume, and
        market cap.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of quote objects, or ``None`` on failure.
        """
        url = self._stable("quote")
        params: Dict[str, Any] = {"symbol": ticker}
        return await self._request("GET", url, params=params)

    async def get_quotes(self, tickers: List[str]) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch real-time quote data for multiple tickers in parallel.

        Each ticker is fetched individually via :meth:`get_quote` because
        FMP's stable API does not support comma-separated batch requests.

        Args:
            tickers: List of stock symbols, e.g. ``["GOOGL", "MSFT", "AAPL"]``.

        Returns:
            Flat list of quote objects (one per successful ticker), or
            ``None`` if every individual request failed.
        """
        if not tickers:
            return []

        results = await asyncio.gather(*(self.get_quote(t) for t in tickers))

        quotes: List[Dict[str, Any]] = []
        for result in results:
            if result and len(result) > 0:
                quotes.append(result[0])

        logger.debug(
            "get_quotes: fetched %d/%d symbols successfully",
            len(quotes),
            len(tickers),
        )

        return quotes if quotes else None

    async def get_historical_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full historical OHLCV data for charting.

        Endpoint: ``GET /stable/historical-price-eod/full?symbol={ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            Dict containing ``"symbol"`` and ``"historical"`` list, or ``None``
            on failure.
        """
        url = self._stable("historical-price-eod/full")
        params: Dict[str, Any] = {"symbol": ticker}
        return await self._request("GET", url, params=params)

    async def get_stock_price_change(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch price performance across multiple time periods for a ticker.

        Endpoint: ``GET /stable/stock-price-change?symbol={ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of price-change objects, or ``None`` on failure.
        """
        url = self._stable("stock-price-change")
        params: Dict[str, Any] = {"symbol": ticker}
        return await self._request("GET", url, params=params)

    async def get_stock_news(
        self,
        ticker: str,
        limit: int = 50,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch recent news articles for a ticker.

        Endpoint: ``GET /stable/news/stock?symbol={ticker}&limit={limit}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.
            limit: Maximum number of articles to return (default 50).

        Returns:
            List of news article objects, or ``None`` on failure.
        """
        url = self._stable("news/stock")
        params: Dict[str, Any] = {"symbol": ticker, "limit": limit}
        return await self._request("GET", url, params=params)

    async def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 8,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch cash flow statements for a symbol.

        Endpoint:
            ``GET /stable/cash-flow-statement?symbol={symbol}&period={period}&limit={limit}``

        Note: CapEx values are reported as negative numbers in cash flow
        statements.  Callers should apply ``abs()`` when computing magnitudes.

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.
            period: Reporting period — ``"quarter"`` or ``"annual"``
                    (default ``"quarter"``).
            limit: Number of periods to return (default 8).

        Returns:
            List of cash flow statement objects, or ``None`` on failure.
        """
        url = self._stable("cash-flow-statement")
        params: Dict[str, Any] = {"symbol": symbol, "period": period, "limit": limit}
        return await self._request("GET", url, params=params)

    async def get_income_statement(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 8,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch income statements (revenue, EPS, margins) for a symbol.

        Endpoint:
            ``GET /stable/income-statement?symbol={symbol}&period={period}&limit={limit}``

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.
            period: Reporting period — ``"quarter"`` or ``"annual"``
                    (default ``"quarter"``).
            limit: Number of periods to return (default 8).

        Returns:
            List of income statement objects, or ``None`` on failure.
        """
        url = self._stable("income-statement")
        params: Dict[str, Any] = {"symbol": symbol, "period": period, "limit": limit}
        return await self._request("GET", url, params=params)

    async def get_analyst_estimates(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch analyst EPS and revenue consensus estimates for a ticker.

        Endpoint: ``GET /stable/analyst-estimates?symbol={ticker}&period=annual``

        Note: Only annual estimates are available on the FMP Starter plan.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of estimate objects, or ``None`` on failure.
        """
        url = self._stable("analyst-estimates")
        params: Dict[str, Any] = {"symbol": ticker, "period": "annual"}
        return await self._request("GET", url, params=params)

    async def get_earnings_calendar(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the upcoming earnings calendar.

        Endpoint: ``GET /stable/earnings-calendar``

        Returns:
            List of calendar entries, or ``None`` on failure.
        """
        url = self._stable("earnings-calendar")
        return await self._request("GET", url)

    # ------------------------------------------------------------------
    # Public API methods — deprecated / unavailable endpoints
    #
    # These methods retain their original signatures so that existing call
    # sites continue to compile.  Each logs a deprecation warning and
    # returns None immediately without making any HTTP request.
    # ------------------------------------------------------------------

    async def get_earnings_surprises(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        DEPRECATED — not available on FMP's stable API.

        The ``/v3/earnings-surprises/{ticker}`` endpoint was removed when FMP
        migrated to the ``/stable/`` base and has no replacement on the Starter
        plan.  This method always returns ``None``.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            Always ``None``.
        """
        logger.warning(
            "get_earnings_surprises(%r) called but this endpoint is no longer available "
            "on FMP's stable API — returning None",
            ticker,
        )
        return None

    async def get_options_chain(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        DEPRECATED — FMP dropped options chain data entirely from the stable API.

        Both the former ``/v4/stock/{ticker}/options`` and
        ``/v3/stock/{ticker}/options/chain`` endpoints are unavailable.
        This method always returns ``None``.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            Always ``None``.
        """
        logger.warning(
            "get_options_chain(%r) called but FMP dropped options chain data from "
            "the stable API — returning None",
            ticker,
        )
        return None

    async def get_social_sentiment(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        DEPRECATED — not available on FMP's stable API.

        The former ``/v4/social-sentiments`` endpoint has no replacement on
        the stable API for the Starter plan.  This method always returns ``None``.

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            Always ``None``.
        """
        logger.warning(
            "get_social_sentiment(%r) called but this endpoint is no longer available "
            "on FMP's stable API — returning None",
            symbol,
        )
        return None

    async def get_real_time_price(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        DEPRECATED — not confirmed available on FMP's stable API.

        The former ``/v3/stock/full/real-time-price/{ticker}`` endpoint has
        not been validated on the stable base URL.  This method always returns
        ``None`` to avoid silent data errors.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            Always ``None``.
        """
        logger.warning(
            "get_real_time_price(%r) called but this endpoint is not confirmed on "
            "FMP's stable API — returning None",
            ticker,
        )
        return None

    async def get_market_actives(self) -> Optional[List[Dict[str, Any]]]:
        """
        DEPRECATED — endpoint removed and no longer needed.

        The former ``/v3/stock_market/actives`` endpoint is not used by any
        engine in the current architecture.  This method always returns ``None``.

        Returns:
            Always ``None``.
        """
        logger.warning(
            "get_market_actives() called but this endpoint has been removed — returning None",
        )
        return None

    async def get_earning_call_transcript(
        self,
        symbol: str,
        year: int,
        quarter: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        DEPRECATED — requires a higher FMP plan than Starter (HTTP 402).

        The former ``/v3/earning_call_transcript/{symbol}`` endpoint returns
        HTTP 402 on the Starter plan and has not been validated on the stable
        base URL.  This method always returns ``None``.

        Note: FMP Starter plan may return summary-only transcripts even on
        plans where transcripts are nominally available.  Callers should
        validate the response content before processing.

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.
            year: Four-digit fiscal year, e.g. ``2024``.
            quarter: Fiscal quarter number (1–4).

        Returns:
            Always ``None``.
        """
        logger.warning(
            "get_earning_call_transcript(%r, year=%d, quarter=%d) called but this "
            "endpoint requires a higher FMP plan (402) — returning None",
            symbol,
            year,
            quarter,
        )
        return None
