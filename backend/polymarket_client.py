"""
Polymarket API client.

Provides access to Polymarket's public APIs for reading prediction market data.
No authentication is required for read-only access.

Two Polymarket APIs are consumed:
  - Gamma API (market discovery): https://gamma-api.polymarket.com
  - CLOB API (order book / prices): https://clob.polymarket.com

All public methods are async and return None on any failure so that callers
can degrade gracefully without propagating exceptions.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT: float = 15.0  # seconds
_GAMMA_BASE_URL: str = "https://gamma-api.polymarket.com"
_CLOB_BASE_URL: str = "https://clob.polymarket.com"


class PolymarketClient:
    """
    Async HTTP client for Polymarket's public Gamma and CLOB APIs.

    No API key is required — both APIs are openly readable.  All methods
    return parsed JSON on success or ``None`` on any failure (network error,
    HTTP error, JSON decode error).

    Usage::

        client = PolymarketClient()
        markets = await client.search_markets("NVDA")
        await client.close()
    """

    def __init__(self) -> None:
        """Initialise the underlying ``httpx.AsyncClient`` with a fixed timeout."""
        self._gamma_base: str = _GAMMA_BASE_URL.rstrip("/")
        self._clob_base: str = _CLOB_BASE_URL.rstrip("/")
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
        params: Optional[dict[str, str]] = None,
    ) -> Optional[object]:
        """
        Execute an HTTP GET request and return the parsed JSON body.

        Args:
            method: HTTP verb (e.g. ``"GET"``).
            url:    Fully-qualified request URL.
            params: Optional query string parameters.

        Returns:
            Parsed JSON body (list or dict), or ``None`` on any failure.
        """
        logger.debug("Polymarket request: %s %s params=%s", method, url, params)

        try:
            response = await self._client.request(method, url, params=params)
        except httpx.TimeoutException as exc:
            logger.error(
                "Polymarket request timed out: %s %s — %s",
                method,
                url,
                exc,
            )
            return None
        except httpx.RequestError as exc:
            logger.error(
                "Polymarket network error: %s %s — %s",
                method,
                url,
                exc,
            )
            return None

        if response.is_error:
            body_snippet = response.text[:500] if response.text else "<empty body>"
            logger.error(
                "Polymarket HTTP error %d: %s %s — body: %s",
                response.status_code,
                method,
                url,
                body_snippet,
            )
            return None

        try:
            return response.json()
        except Exception as exc:  # noqa: BLE001 — JSON parse errors vary
            logger.error(
                "Polymarket JSON decode error: %s %s — %s",
                method,
                url,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Gamma API — Market Discovery
    # ------------------------------------------------------------------

    async def search_markets(self, query: str = "NVDA") -> Optional[list[dict]]:
        """
        Search for active prediction markets matching *query*.

        Endpoint: ``GET {gamma_base}/markets?_q={query}``

        Note: The ``outcomePrices`` field in each returned market dict is a
        JSON-encoded string (a string containing a JSON array).  Callers
        should use ``json.loads(market["outcomePrices"])`` to decode it.

        Args:
            query: Free-text search term, e.g. ``"NVDA"``.

        Returns:
            List of market dicts, or ``None`` on failure.
        """
        url = f"{self._gamma_base}/markets"
        params = {"_q": query}
        result = await self._request("GET", url, params=params)

        if result is None:
            return None

        if not isinstance(result, list):
            logger.error(
                "Polymarket search_markets: expected list, got %s", type(result).__name__
            )
            return None

        logger.info(
            "Polymarket search_markets: found %d markets for query=%r",
            len(result),
            query,
        )
        return result

    async def get_market(self, market_id: str) -> Optional[dict]:
        """
        Fetch a single prediction market by its Polymarket ID.

        Endpoint: ``GET {gamma_base}/markets/{market_id}``

        Args:
            market_id: Polymarket market identifier string.

        Returns:
            Market dict, or ``None`` on failure.
        """
        url = f"{self._gamma_base}/markets/{market_id}"
        result = await self._request("GET", url)

        if result is None:
            return None

        if not isinstance(result, dict):
            logger.error(
                "Polymarket get_market: expected dict, got %s for id=%s",
                type(result).__name__,
                market_id,
            )
            return None

        return result

    # ------------------------------------------------------------------
    # CLOB API — Order Book / Prices
    # ------------------------------------------------------------------

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """
        Fetch the current mid-point price for a market outcome token.

        Endpoint: ``GET {clob_base}/midpoint?token_id={token_id}``

        The midpoint is the arithmetic mean of the best bid and best ask,
        representing the implied probability (0–1) for the outcome.

        Args:
            token_id: CLOB token identifier for a specific outcome (YES/NO).

        Returns:
            Mid-point price as a float in [0, 1], or ``None`` on failure.
        """
        url = f"{self._clob_base}/midpoint"
        params = {"token_id": token_id}
        result = await self._request("GET", url, params=params)

        if result is None:
            return None

        # Response may be {"mid": "0.72"} or {"mid": 0.72}
        if isinstance(result, dict):
            raw = result.get("mid")
            if raw is None:
                logger.error(
                    "Polymarket get_midpoint: 'mid' key missing in response for token=%s",
                    token_id,
                )
                return None
            try:
                return float(raw)
            except (ValueError, TypeError) as exc:
                logger.error(
                    "Polymarket get_midpoint: cannot convert mid=%r to float for token=%s — %s",
                    raw,
                    token_id,
                    exc,
                )
                return None

        # If the API returns a bare float / string
        try:
            return float(result)  # type: ignore[arg-type]
        except (ValueError, TypeError) as exc:
            logger.error(
                "Polymarket get_midpoint: unexpected response type %s for token=%s — %s",
                type(result).__name__,
                token_id,
                exc,
            )
            return None

    async def get_orderbook(self, token_id: str) -> Optional[dict]:
        """
        Fetch the full order book for a market outcome token.

        Endpoint: ``GET {clob_base}/book?token_id={token_id}``

        Returns the bids and asks for a given outcome token, which can be
        used to compute liquidity and price depth.

        Args:
            token_id: CLOB token identifier for a specific outcome (YES/NO).

        Returns:
            Order book dict (with ``"bids"`` and ``"asks"`` lists), or ``None``
            on failure.
        """
        url = f"{self._clob_base}/book"
        params = {"token_id": token_id}
        result = await self._request("GET", url, params=params)

        if result is None:
            return None

        if not isinstance(result, dict):
            logger.error(
                "Polymarket get_orderbook: expected dict, got %s for token=%s",
                type(result).__name__,
                token_id,
            )
            return None

        return result


# ---------------------------------------------------------------------------
# Parsing helper (module-level, used by the engine)
# ---------------------------------------------------------------------------


def parse_outcome_prices(market: dict) -> Optional[list[float]]:
    """
    Decode the ``outcomePrices`` field from a Polymarket market dict.

    Polymarket embeds outcome prices as a JSON-encoded string inside the
    outer JSON response, e.g.::

        "outcomePrices": "[\"0.72\",\"0.28\"]"

    This helper handles both the nested-JSON-string form and any plain
    list form that future API versions may return.

    Args:
        market: A single market dict as returned by the Gamma API.

    Returns:
        List of outcome prices as floats (e.g. ``[0.72, 0.28]``), or
        ``None`` if the field is missing, malformed, or unparseable.
    """
    raw = market.get("outcomePrices")
    if raw is None:
        logger.debug(
            "parse_outcome_prices: 'outcomePrices' missing from market id=%s",
            market.get("id", "<unknown>"),
        )
        return None

    # If already a list, coerce each element to float
    if isinstance(raw, list):
        try:
            return [float(p) for p in raw]
        except (ValueError, TypeError) as exc:
            logger.error(
                "parse_outcome_prices: failed to coerce list to floats for market id=%s — %s",
                market.get("id", "<unknown>"),
                exc,
            )
            return None

    # Otherwise expect a JSON-encoded string
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(
                "parse_outcome_prices: JSON decode error for market id=%s — %s",
                market.get("id", "<unknown>"),
                exc,
            )
            return None

        if not isinstance(decoded, list):
            logger.error(
                "parse_outcome_prices: decoded value is not a list for market id=%s",
                market.get("id", "<unknown>"),
            )
            return None

        try:
            return [float(p) for p in decoded]
        except (ValueError, TypeError) as exc:
            logger.error(
                "parse_outcome_prices: failed to coerce decoded list to floats for market id=%s — %s",
                market.get("id", "<unknown>"),
                exc,
            )
            return None

    logger.error(
        "parse_outcome_prices: unexpected type %s for market id=%s",
        type(raw).__name__,
        market.get("id", "<unknown>"),
    )
    return None
