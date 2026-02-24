"""
SocialData.tools API client.

Provides async access to the Twitter/X search endpoint via the
SocialData.tools API (https://api.socialdata.tools).

Auth: Bearer token passed in the Authorization header.
Rate limit: 120 requests / minute — callers are responsible for
            scheduling requests at an appropriate interval.
"""

import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

_BASE_URL: str = "https://api.socialdata.tools"
_TIMEOUT_SECONDS: float = 15.0


class SocialDataClient:
    """Async HTTP client for the SocialData.tools Twitter/X search API."""

    def __init__(self) -> None:
        settings = get_settings()
        api_key: str = settings.socialdata_api_key
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=_TIMEOUT_SECONDS,
        )

    async def search_tweets(
        self,
        query: str = "$NVDA",
        tweet_type: str = "Latest",
    ) -> list[dict] | None:
        """
        Search for tweets matching *query*.

        Args:
            query:      Search query string.  Defaults to ``"$NVDA"``.
            tweet_type: Result ordering passed to the API.
                        ``"Latest"`` (default) returns chronological order.

        Returns:
            A list of raw tweet dicts as returned by the API, or ``None``
            if the request fails for any reason (network error, auth
            failure, unexpected response shape, etc.).
        """
        params: dict[str, str] = {"query": query, "type": tweet_type}
        try:
            response = await self._client.get("/twitter/search", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "SocialDataClient.search_tweets: HTTP %s for query=%r — %s",
                exc.response.status_code,
                query,
                exc.response.text[:200],
            )
            return None
        except httpx.TimeoutException:
            logger.error(
                "SocialDataClient.search_tweets: request timed out after %.0fs (query=%r)",
                _TIMEOUT_SECONDS,
                query,
            )
            return None
        except httpx.RequestError as exc:
            logger.error(
                "SocialDataClient.search_tweets: network error for query=%r — %s",
                query,
                exc,
            )
            return None

        try:
            payload: dict = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "SocialDataClient.search_tweets: failed to decode JSON response — %s",
                exc,
            )
            return None

        tweets = payload.get("tweets")
        if not isinstance(tweets, list):
            logger.error(
                "SocialDataClient.search_tweets: unexpected response shape — "
                "'tweets' key missing or not a list. keys=%s",
                list(payload.keys()),
            )
            return None

        logger.debug(
            "SocialDataClient.search_tweets: received %d tweets for query=%r",
            len(tweets),
            query,
        )
        return tweets

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._client.aclose()
