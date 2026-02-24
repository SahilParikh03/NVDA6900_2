"""
Tests for the data refresh scheduler.

Verifies scheduler initialization, task lifecycle, periodic task error handling,
and that each refresh method calls the correct FMP client methods and caches
results under the correct keys.
"""

import asyncio
import logging
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.scheduler import DataRefreshScheduler, get_scheduler, init_scheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fmp_client() -> AsyncMock:
    """Create a mock FMP client with all methods used by the scheduler."""
    client = AsyncMock()
    client.get_quote = AsyncMock(return_value=[{"price": 950.0, "volume": 1000000}])
    client.get_options_chain = AsyncMock(return_value=[{"strike": 950, "type": "call"}])
    client.get_social_sentiment = AsyncMock(return_value=[{"score": 0.75}])
    client.get_earnings_calendar = AsyncMock(return_value=[{"date": "2026-02-26"}])
    client.get_analyst_estimates = AsyncMock(return_value=[{"estimatedEpsAvg": 0.85}])
    client.get_earnings_surprises = AsyncMock(return_value=[{"actualEarningResult": 0.88}])
    client.get_cash_flow_statement = AsyncMock(
        return_value=[{"capitalExpenditure": -14200000000}]
    )
    client.get_income_statement = AsyncMock(return_value=[{"revenue": 65600000000}])
    return client


@pytest.fixture
def scheduler(mock_fmp_client: AsyncMock) -> DataRefreshScheduler:
    """Create a DataRefreshScheduler with a mock FMP client."""
    return DataRefreshScheduler(mock_fmp_client)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_initialization(mock_fmp_client: AsyncMock) -> None:
    """Scheduler stores fmp_client, starts with _running=False and _tasks=[]."""
    sched = DataRefreshScheduler(mock_fmp_client)

    assert sched.fmp_client is mock_fmp_client
    assert sched._running is False
    assert sched._tasks == []


# ---------------------------------------------------------------------------
# Start / stop lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_start_creates_tasks(scheduler: DataRefreshScheduler) -> None:
    """start() creates exactly 5 background tasks and sets _running=True."""
    await scheduler.start()

    assert scheduler._running is True
    assert len(scheduler._tasks) == 5  # prices, options, sentiment, earnings, hyperscaler

    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_cancels_tasks(scheduler: DataRefreshScheduler) -> None:
    """stop() cancels all tasks and sets _running=False."""
    await scheduler.start()
    assert len(scheduler._tasks) == 5

    await scheduler.stop()

    assert scheduler._running is False
    # All tasks must be done (cancelled counts as done)
    assert all(task.done() for task in scheduler._tasks)


@pytest.mark.asyncio
async def test_scheduler_double_start_warning(
    scheduler: DataRefreshScheduler, caplog: pytest.LogCaptureFixture
) -> None:
    """A second call to start() while already running logs an 'already running' warning."""
    await scheduler.start()

    with caplog.at_level(logging.WARNING, logger="backend.scheduler"):
        await scheduler.start()

    assert "already running" in caplog.text

    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_when_not_running(
    scheduler: DataRefreshScheduler, caplog: pytest.LogCaptureFixture
) -> None:
    """Calling stop() on a scheduler that was never started logs a 'not running' warning."""
    with caplog.at_level(logging.WARNING, logger="backend.scheduler"):
        await scheduler.stop()

    assert "not running" in caplog.text


# ---------------------------------------------------------------------------
# _refresh_prices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_prices_calls_get_quote(
    scheduler: DataRefreshScheduler, mock_fmp_client: AsyncMock
) -> None:
    """_refresh_prices() calls get_quote('NVDA') exactly once and caches under 'price:NVDA'."""
    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()

        await scheduler._refresh_prices()

        mock_fmp_client.get_quote.assert_called_once_with("NVDA")
        mock_cache.set.assert_called_once()
        cache_key: str = mock_cache.set.call_args[0][0]
        assert cache_key == "price:NVDA"


# ---------------------------------------------------------------------------
# _refresh_options
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_options_calls_get_options_chain(
    scheduler: DataRefreshScheduler, mock_fmp_client: AsyncMock
) -> None:
    """_refresh_options() calls get_options_chain('NVDA') exactly once and caches under 'options:NVDA'."""
    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()

        await scheduler._refresh_options()

        mock_fmp_client.get_options_chain.assert_called_once_with("NVDA")
        mock_cache.set.assert_called_once()
        cache_key: str = mock_cache.set.call_args[0][0]
        assert cache_key == "options:NVDA"


# ---------------------------------------------------------------------------
# _refresh_sentiment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_sentiment_calls_get_social_sentiment(
    scheduler: DataRefreshScheduler, mock_fmp_client: AsyncMock
) -> None:
    """_refresh_sentiment() calls get_social_sentiment('NVDA') exactly once and caches under 'sentiment:NVDA'."""
    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()

        await scheduler._refresh_sentiment()

        mock_fmp_client.get_social_sentiment.assert_called_once_with("NVDA")
        mock_cache.set.assert_called_once()
        cache_key: str = mock_cache.set.call_args[0][0]
        assert cache_key == "sentiment:NVDA"


# ---------------------------------------------------------------------------
# _refresh_earnings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_earnings_calls_three_endpoints(
    scheduler: DataRefreshScheduler, mock_fmp_client: AsyncMock
) -> None:
    """_refresh_earnings() calls get_earnings_calendar, get_analyst_estimates, get_earnings_surprises
    and caches results under three distinct keys."""
    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()

        await scheduler._refresh_earnings()

        mock_fmp_client.get_earnings_calendar.assert_called_once()
        mock_fmp_client.get_analyst_estimates.assert_called_once_with("NVDA")
        mock_fmp_client.get_earnings_surprises.assert_called_once_with("NVDA")

        assert mock_cache.set.call_count == 3

        cached_keys: list[str] = [c[0][0] for c in mock_cache.set.call_args_list]
        assert "earnings:calendar" in cached_keys
        assert "earnings:estimates:NVDA" in cached_keys
        assert "earnings:surprises:NVDA" in cached_keys


# ---------------------------------------------------------------------------
# _refresh_hyperscaler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_hyperscaler_calls_cashflow_and_income(
    scheduler: DataRefreshScheduler, mock_fmp_client: AsyncMock
) -> None:
    """_refresh_hyperscaler() calls get_cash_flow_statement and get_income_statement for
    each of the 4 hyperscaler tickers (8 FMP calls total, 8 cache sets)."""
    hyperscaler_tickers: list[str] = ["MSFT", "GOOGL", "AMZN", "META"]

    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()

        await scheduler._refresh_hyperscaler()

        assert mock_fmp_client.get_cash_flow_statement.call_count == 4
        assert mock_fmp_client.get_income_statement.call_count == 4
        assert mock_cache.set.call_count == 8

        # Verify the correct tickers were passed to each method
        cashflow_tickers: list[str] = [
            c[0][0] for c in mock_fmp_client.get_cash_flow_statement.call_args_list
        ]
        income_tickers: list[str] = [
            c[0][0] for c in mock_fmp_client.get_income_statement.call_args_list
        ]
        assert cashflow_tickers == hyperscaler_tickers
        assert income_tickers == hyperscaler_tickers

        # Verify each call uses period=quarter and limit=8
        for c in mock_fmp_client.get_cash_flow_statement.call_args_list:
            kwargs = c[1]
            assert kwargs.get("period") == "quarter"
            assert kwargs.get("limit") == 8
        for c in mock_fmp_client.get_income_statement.call_args_list:
            kwargs = c[1]
            assert kwargs.get("period") == "quarter"
            assert kwargs.get("limit") == 8

        # Verify cache keys cover all tickers for both statement types
        cached_keys: list[str] = [c[0][0] for c in mock_cache.set.call_args_list]
        for ticker in hyperscaler_tickers:
            assert f"hyperscaler:cashflow:{ticker}" in cached_keys
            assert f"hyperscaler:income:{ticker}" in cached_keys


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_refresh_logs_error_continues(
    scheduler: DataRefreshScheduler,
    mock_fmp_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Exception raised by get_quote is caught; error is logged and the method returns normally."""
    mock_fmp_client.get_quote.side_effect = Exception("API error")

    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()
        with caplog.at_level(logging.ERROR, logger="backend.scheduler"):
            await scheduler._refresh_prices()

    assert "Failed to refresh price" in caplog.text
    # Cache must not have been written — no data to store
    mock_cache.set.assert_not_called()
    # Scheduler object is still intact
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_periodic_task_handles_exceptions(
    scheduler: DataRefreshScheduler,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_run_periodic_task() catches exceptions from task_func, logs them, and keeps looping."""
    failing_task = AsyncMock(side_effect=Exception("Task failed"))

    scheduler._running = True
    task = asyncio.create_task(
        scheduler._run_periodic_task(failing_task, 0, "test_task")
    )

    # Allow at least one iteration to execute
    await asyncio.sleep(0.05)

    scheduler._running = False
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert "Error in periodic task 'test_task'" in caplog.text
    # The task function must have been called at least once
    assert failing_task.call_count >= 1


# ---------------------------------------------------------------------------
# Global instance helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_scheduler_creates_global(mock_fmp_client: AsyncMock) -> None:
    """init_scheduler() returns a DataRefreshScheduler and get_scheduler() returns the same instance."""
    sched: DataRefreshScheduler = init_scheduler(mock_fmp_client)

    assert sched is not None
    assert isinstance(sched, DataRefreshScheduler)
    assert sched.fmp_client is mock_fmp_client
    assert get_scheduler() is sched


# ---------------------------------------------------------------------------
# None / empty response guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_handles_none_response(
    scheduler: DataRefreshScheduler, mock_fmp_client: AsyncMock
) -> None:
    """When get_quote returns None, cache.set must NOT be called."""
    mock_fmp_client.get_quote.return_value = None

    with patch("backend.scheduler.cache") as mock_cache:
        mock_cache.set = AsyncMock()

        await scheduler._refresh_prices()

        mock_cache.set.assert_not_called()
