"""
Background scheduler for periodic data refresh tasks.

Implements scheduled jobs that refresh cached data by calling the FMP client
and storing results in the TTL cache. Each job runs at an interval matching
its cache TTL to ensure data freshness.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional

from backend.cache import cache
from backend.config import settings
from backend.fmp_client import FMPClient

logger = logging.getLogger(__name__)


class DataRefreshScheduler:
    """
    Scheduler for periodic background data refresh tasks.

    Each refresh task fetches data via FMP client and stores it in the cache.
    Tasks run at intervals matching their cache TTLs to maintain freshness.
    """

    def __init__(self, fmp_client: FMPClient) -> None:
        """
        Initialize the scheduler.

        Args:
            fmp_client: FMP client instance for fetching market data
        """
        self.fmp_client = fmp_client
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start all scheduled background tasks."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info("Starting data refresh scheduler")

        # Create background tasks for each refresh job
        self._tasks = [
            asyncio.create_task(self._run_periodic_task(
                self._refresh_prices,
                settings.cache_ttl_price,
                "prices"
            )),
            asyncio.create_task(self._run_periodic_task(
                self._refresh_options,
                settings.cache_ttl_options,
                "options"
            )),
            asyncio.create_task(self._run_periodic_task(
                self._refresh_sentiment,
                settings.cache_ttl_sentiment,
                "sentiment"
            )),
            asyncio.create_task(self._run_periodic_task(
                self._refresh_earnings,
                settings.cache_ttl_earnings,
                "earnings"
            )),
            asyncio.create_task(self._run_periodic_task(
                self._refresh_hyperscaler,
                settings.cache_ttl_hyperscaler,
                "hyperscaler"
            )),
        ]

        logger.info(
            "Scheduler started with %d tasks: prices(%ds), options(%ds), "
            "sentiment(%ds), earnings(%ds), hyperscaler(%ds)",
            len(self._tasks),
            settings.cache_ttl_price,
            settings.cache_ttl_options,
            settings.cache_ttl_sentiment,
            settings.cache_ttl_earnings,
            settings.cache_ttl_hyperscaler,
        )

    async def stop(self) -> None:
        """Stop all scheduled background tasks."""
        if not self._running:
            logger.warning("Scheduler not running")
            return

        self._running = False
        logger.info("Stopping data refresh scheduler")

        # Cancel all running tasks
        for task in self._tasks:
            task.cancel()

        # Wait for all tasks to complete cancellation
        await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks = []
        logger.info("Scheduler stopped")

    async def _run_periodic_task(
        self,
        task_func: Callable[..., Awaitable[None]],
        interval_seconds: int,
        task_name: str,
    ) -> None:
        """
        Run a task periodically at the specified interval.

        Args:
            task_func: Async function to execute periodically
            interval_seconds: Interval between executions in seconds
            task_name: Name of the task for logging
        """
        logger.info("Starting periodic task '%s' with interval %ds", task_name, interval_seconds)

        while self._running:
            try:
                await task_func()
            except Exception as e:
                # Log error but continue running - graceful degradation
                logger.error(
                    "Error in periodic task '%s': %s",
                    task_name,
                    str(e),
                    exc_info=True,
                )

            # Wait for the next execution
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("Periodic task '%s' cancelled", task_name)
                break

    async def _refresh_prices(self) -> None:
        """Refresh stock price for NVDA."""
        logger.debug("Refreshing stock prices")

        ticker = "NVDA"
        try:
            price_data = await self.fmp_client.get_quote(ticker)
            if price_data:
                await cache.set(f"price:{ticker}", price_data, ttl=settings.cache_ttl_price)
                logger.debug("Refreshed price for %s", ticker)
        except Exception as e:
            logger.error("Failed to refresh price for %s: %s", ticker, str(e))

    async def _refresh_options(self) -> None:
        """Refresh options chain data for NVDA."""
        logger.debug("Refreshing options data")

        ticker = "NVDA"
        try:
            options_data = await self.fmp_client.get_options_chain(ticker)
            if options_data:
                await cache.set(f"options:{ticker}", options_data, ttl=settings.cache_ttl_options)
                logger.debug("Refreshed options for %s: %d contracts", ticker, len(options_data))
        except Exception as e:
            logger.error("Failed to refresh options for %s: %s", ticker, str(e))

    async def _refresh_sentiment(self) -> None:
        """Refresh social sentiment data for NVDA."""
        logger.debug("Refreshing sentiment data")

        ticker = "NVDA"
        try:
            sentiment_data = await self.fmp_client.get_social_sentiment(ticker)
            if sentiment_data:
                await cache.set(f"sentiment:{ticker}", sentiment_data, ttl=settings.cache_ttl_sentiment)
                logger.debug("Refreshed sentiment for %s", ticker)
        except Exception as e:
            logger.error("Failed to refresh sentiment for %s: %s", ticker, str(e))

    async def _refresh_earnings(self) -> None:
        """Refresh earnings-related data for NVDA."""
        logger.debug("Refreshing earnings data")

        try:
            calendar = await self.fmp_client.get_earnings_calendar()
            if calendar:
                await cache.set("earnings:calendar", calendar, ttl=settings.cache_ttl_earnings)
        except Exception as e:
            logger.error("Failed to refresh earnings calendar: %s", str(e))

        try:
            estimates = await self.fmp_client.get_analyst_estimates("NVDA")
            if estimates:
                await cache.set("earnings:estimates:NVDA", estimates, ttl=settings.cache_ttl_earnings)
        except Exception as e:
            logger.error("Failed to refresh analyst estimates: %s", str(e))

        try:
            surprises = await self.fmp_client.get_earnings_surprises("NVDA")
            if surprises:
                await cache.set("earnings:surprises:NVDA", surprises, ttl=settings.cache_ttl_earnings)
        except Exception as e:
            logger.error("Failed to refresh earnings surprises: %s", str(e))

    async def _refresh_hyperscaler(self) -> None:
        """Refresh hyperscaler financial data."""
        logger.debug("Refreshing hyperscaler data")

        hyperscaler_tickers = ["MSFT", "GOOGL", "AMZN", "META"]

        for ticker in hyperscaler_tickers:
            try:
                cash_flow = await self.fmp_client.get_cash_flow_statement(ticker, period="quarter", limit=8)
                if cash_flow:
                    await cache.set(f"hyperscaler:cashflow:{ticker}", cash_flow, ttl=settings.cache_ttl_hyperscaler)
                    logger.debug("Refreshed cash flow for %s", ticker)
            except Exception as e:
                logger.error("Failed to refresh cash flow for %s: %s", ticker, str(e))

            try:
                income = await self.fmp_client.get_income_statement(ticker, period="quarter", limit=8)
                if income:
                    await cache.set(f"hyperscaler:income:{ticker}", income, ttl=settings.cache_ttl_hyperscaler)
                    logger.debug("Refreshed income statement for %s", ticker)
            except Exception as e:
                logger.error("Failed to refresh income statement for %s: %s", ticker, str(e))


# Global scheduler instance (initialized in main.py)
scheduler: Optional[DataRefreshScheduler] = None


def get_scheduler() -> Optional[DataRefreshScheduler]:
    """
    Get the global scheduler instance.

    Returns:
        The scheduler instance or None if not initialized
    """
    return scheduler


def init_scheduler(fmp_client: FMPClient) -> DataRefreshScheduler:
    """
    Initialize the global scheduler instance.

    Args:
        fmp_client: FMP client instance for data fetching

    Returns:
        The initialized scheduler instance
    """
    global scheduler
    scheduler = DataRefreshScheduler(fmp_client)
    return scheduler
