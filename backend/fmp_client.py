"""
FMP (Financial Modeling Prep) API client.

All HTTP calls to the external FMP API route through this module.
No other module in the project should make HTTP calls to FMP directly.
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


class FMPClient:
    """
    Async HTTP client for the Financial Modeling Prep API.

    All public methods map 1-to-1 to a specific FMP endpoint.  Authentication
    is handled internally — callers never need to touch the API key.  Every
    method returns the parsed JSON payload on success or ``None`` on any
    failure (network error, 4xx/5xx, exhausted retries after 429).

    Usage::

        client = FMPClient()
        quote = await client.get_quote("NVDA")
        await client.close()
    """

    def __init__(self) -> None:
        """Initialise the underlying ``httpx.AsyncClient`` with a fixed timeout."""
        self._api_key: str = settings.fmp_api_key
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
    # Internal helper
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

    # ------------------------------------------------------------------
    # URL builders
    # ------------------------------------------------------------------

    def _v3(self, path: str) -> str:
        """Build a v3 endpoint URL.  ``path`` must NOT start with a slash."""
        return f"{self._base_url}/v3/{path}"

    def _v4(self, path: str) -> str:
        """Build a v4 endpoint URL.  ``path`` must NOT start with a slash."""
        return f"{self._base_url}/v4/{path}"

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_quote(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch real-time quote data for a ticker.

        Endpoint: ``GET /v3/quote/{ticker}``

        Returns fields such as price, change, changePercent, volume, and
        market cap.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of quote objects, or ``None`` on failure.
        """
        url = self._v3(f"quote/{ticker}")
        return await self._request("GET", url)

    async def get_market_actives(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the most actively traded stocks in the current session.

        Endpoint: ``GET /v3/stock_market/actives``

        Returns:
            List of active stock objects, or ``None`` on failure.
        """
        url = self._v3("stock_market/actives")
        return await self._request("GET", url)

    async def get_analyst_estimates(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch analyst EPS and revenue consensus estimates for a ticker.

        Endpoint: ``GET /v3/analyst-estimates/{ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of estimate objects, or ``None`` on failure.
        """
        url = self._v3(f"analyst-estimates/{ticker}")
        return await self._request("GET", url)

    async def get_earnings_surprises(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch historical earnings beat/miss data for a ticker.

        Endpoint: ``GET /v3/earnings-surprises/{ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of earnings surprise objects, or ``None`` on failure.
        """
        url = self._v3(f"earnings-surprises/{ticker}")
        return await self._request("GET", url)

    async def get_earnings_calendar(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the upcoming earnings calendar.

        Endpoint: ``GET /v3/earning_calendar``

        Returns:
            List of calendar entries, or ``None`` on failure.
        """
        url = self._v3("earning_calendar")
        return await self._request("GET", url)

    async def get_stock_price_change(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch price performance across multiple time periods for a ticker.

        Endpoint: ``GET /v3/stock-price-change/{ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of price-change objects, or ``None`` on failure.
        """
        url = self._v3(f"stock-price-change/{ticker}")
        return await self._request("GET", url)

    async def get_historical_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full historical OHLCV data for charting.

        Endpoint: ``GET /v3/historical-price-full/{ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            Dict containing ``"symbol"`` and ``"historical"`` list, or ``None``
            on failure.
        """
        url = self._v3(f"historical-price-full/{ticker}")
        return await self._request("GET", url)

    async def get_real_time_price(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch intraday real-time tick data for a ticker.

        Endpoint: ``GET /v3/stock/full/real-time-price/{ticker}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of real-time price tick objects, or ``None`` on failure.
        """
        url = self._v3(f"stock/full/real-time-price/{ticker}")
        return await self._request("GET", url)

    async def get_stock_news(
        self,
        ticker: str,
        limit: int = 50,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch recent news articles for a ticker.

        Endpoint: ``GET /v3/stock_news?tickers={ticker}&limit={limit}``

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.
            limit: Maximum number of articles to return (default 50).

        Returns:
            List of news article objects, or ``None`` on failure.
        """
        url = self._v3("stock_news")
        params: Dict[str, Any] = {"tickers": ticker, "limit": limit}
        return await self._request("GET", url, params=params)

    async def get_social_sentiment(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch trending social sentiment data for a symbol.

        Endpoint: ``GET /v4/social-sentiments?symbol={symbol}``

        Note: This is a v4 endpoint.

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of sentiment objects, or ``None`` on failure.
        """
        url = self._v4("social-sentiments")
        params: Dict[str, Any] = {"symbol": symbol}
        return await self._request("GET", url, params=params)

    async def get_options_chain(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the full options chain for a ticker.

        Primary endpoint:  ``GET /v4/stock/{ticker}/options``
        Fallback endpoint: ``GET /v3/stock/{ticker}/options/chain``

        The v4 URL is tried first.  If it returns ``None`` (any failure),
        the v3 fallback is attempted automatically.

        Note: Options chain data may be incomplete on the FMP Starter plan.

        Args:
            ticker: Stock symbol, e.g. ``"NVDA"``.

        Returns:
            List of option contract objects, or ``None`` on failure.
        """
        # Primary: v4
        url_v4 = self._v4(f"stock/{ticker}/options")
        result = await self._request("GET", url_v4)
        if result is not None:
            return result

        # Fallback: v3
        logger.debug("Options chain v4 returned None for %s — trying v3 fallback", ticker)
        url_v3 = self._v3(f"stock/{ticker}/options/chain")
        return await self._request("GET", url_v3)

    async def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 8,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch cash flow statements for a symbol.

        Endpoint:
            ``GET /v3/cash-flow-statement/{symbol}?period={period}&limit={limit}``

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
        url = self._v3(f"cash-flow-statement/{symbol}")
        params: Dict[str, Any] = {"period": period, "limit": limit}
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
            ``GET /v3/income-statement/{symbol}?period={period}&limit={limit}``

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.
            period: Reporting period — ``"quarter"`` or ``"annual"``
                    (default ``"quarter"``).
            limit: Number of periods to return (default 8).

        Returns:
            List of income statement objects, or ``None`` on failure.
        """
        url = self._v3(f"income-statement/{symbol}")
        params: Dict[str, Any] = {"period": period, "limit": limit}
        return await self._request("GET", url, params=params)

    async def get_earning_call_transcript(
        self,
        symbol: str,
        year: int,
        quarter: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the earnings call transcript for a specific quarter.

        Endpoint:
            ``GET /v3/earning_call_transcript/{symbol}?year={year}&quarter={quarter}``

        Note: FMP Starter plan may return summary-only transcripts.  Callers
        should validate the response content before processing.

        Args:
            symbol: Stock symbol, e.g. ``"NVDA"``.
            year: Four-digit fiscal year, e.g. ``2024``.
            quarter: Fiscal quarter number (1–4).

        Returns:
            List of transcript objects, or ``None`` on failure.
        """
        url = self._v3(f"earning_call_transcript/{symbol}")
        params: Dict[str, Any] = {"year": year, "quarter": quarter}
        return await self._request("GET", url, params=params)
