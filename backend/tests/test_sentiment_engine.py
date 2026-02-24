"""
Tests for backend.engines.sentiment_engine.process_sentiment.

All tests use mock fixture data — no live FMP calls are made.

Run with:
    pytest backend/tests/test_sentiment_engine.py -v
"""

import pytest

from backend.engines.sentiment_engine import (
    LABEL_BEARISH_THRESHOLD,
    LABEL_BULLISH_THRESHOLD,
    VOLUME_SPIKE_MULTIPLIER,
    SentimentResult,
    process_sentiment,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_row(
    date: str,
    stocktwits_sentiment: float = 0.65,
    twitter_sentiment: float = 0.72,
    stocktwits_posts: int = 450,
    twitter_posts: int = 1200,
    symbol: str = "NVDA",
) -> dict:
    """Return a minimal FMP-style social sentiment row."""
    return {
        "date": date,
        "symbol": symbol,
        "stocktwitsSentiment": stocktwits_sentiment,
        "twitterSentiment": twitter_sentiment,
        "stocktwitsPostsCount": stocktwits_posts,
        "twitterPostsCount": twitter_posts,
    }


# 7-day realistic dataset — dates in any order (engine must sort)
SEVEN_DAY_DATA: list[dict] = [
    _make_row("2026-02-17 14:00:00", stocktwits_sentiment=0.55, twitter_sentiment=0.58, stocktwits_posts=300, twitter_posts=800),
    _make_row("2026-02-18 14:00:00", stocktwits_sentiment=0.57, twitter_sentiment=0.60, stocktwits_posts=320, twitter_posts=850),
    _make_row("2026-02-19 14:00:00", stocktwits_sentiment=0.60, twitter_sentiment=0.63, stocktwits_posts=360, twitter_posts=900),
    _make_row("2026-02-20 14:00:00", stocktwits_sentiment=0.62, twitter_sentiment=0.65, stocktwits_posts=390, twitter_posts=950),
    _make_row("2026-02-21 14:00:00", stocktwits_sentiment=0.64, twitter_sentiment=0.68, stocktwits_posts=410, twitter_posts=1000),
    _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.58, twitter_sentiment=0.61, stocktwits_posts=380, twitter_posts=900),
    _make_row("2026-02-23 14:00:00", stocktwits_sentiment=0.65, twitter_sentiment=0.72, stocktwits_posts=450, twitter_posts=1200),
]


# ---------------------------------------------------------------------------
# 1. Happy-path: returns valid SentimentResult with 7 days of data
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_happy_path_returns_sentiment_result() -> None:
    """Seven days of data must produce a populated SentimentResult."""
    result: SentimentResult = await process_sentiment(SEVEN_DAY_DATA)

    assert isinstance(result, SentimentResult)
    assert result.sentiment_label in ("Bullish", "Neutral", "Bearish")
    assert -100.0 <= result.current_score <= 100.0


# ---------------------------------------------------------------------------
# 2. Empty data → neutral defaults
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_data_returns_neutral_defaults() -> None:
    """Empty input must return score=0.0 and label='Neutral'."""
    result: SentimentResult = await process_sentiment([])

    assert result.current_score == 0.0
    assert result.sentiment_label == "Neutral"
    assert result.rate_of_change == 0.0
    assert result.roc_direction == "stable"
    assert result.mention_volume_today == 0
    assert result.volume_spike is False
    assert result.history == []


# ---------------------------------------------------------------------------
# 3. Single day of data → ROC = 0.0, direction = stable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_day_roc_is_zero() -> None:
    """With only 1 day of data, ROC must be 0.0 and direction 'stable'."""
    single_day = [_make_row("2026-02-23 14:00:00")]
    result: SentimentResult = await process_sentiment(single_day)

    assert result.rate_of_change == pytest.approx(0.0)
    assert result.roc_direction == "stable"
    assert result.history == []


# ---------------------------------------------------------------------------
# 4. ROC is calculated correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_roc_calculation_correct() -> None:
    """
    ROC = (avg_today - avg_yesterday) / abs(avg_yesterday).
    avg_today = (0.65 + 0.72) / 2 = 0.685
    avg_yesterday = (0.58 + 0.61) / 2 = 0.595
    roc = (0.685 - 0.595) / 0.595 ≈ 0.1513
    """
    two_days = [
        _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.58, twitter_sentiment=0.61),
        _make_row("2026-02-23 14:00:00", stocktwits_sentiment=0.65, twitter_sentiment=0.72),
    ]
    result: SentimentResult = await process_sentiment(two_days)

    avg_today = (0.65 + 0.72) / 2.0
    avg_yesterday = (0.58 + 0.61) / 2.0
    expected_roc = (avg_today - avg_yesterday) / abs(avg_yesterday)
    assert result.rate_of_change == pytest.approx(expected_roc, rel=1e-4)


# ---------------------------------------------------------------------------
# 5. ROC direction: accelerating when roc > 0
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_roc_direction_accelerating() -> None:
    """Positive ROC must produce direction='accelerating'."""
    two_days = [
        _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.50, twitter_sentiment=0.50),
        _make_row("2026-02-23 14:00:00", stocktwits_sentiment=0.65, twitter_sentiment=0.72),
    ]
    result: SentimentResult = await process_sentiment(two_days)

    assert result.roc_direction == "accelerating"


# ---------------------------------------------------------------------------
# 6. ROC direction: decelerating when roc < 0
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_roc_direction_decelerating() -> None:
    """Negative ROC must produce direction='decelerating'."""
    two_days = [
        _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.70, twitter_sentiment=0.75),
        _make_row("2026-02-23 14:00:00", stocktwits_sentiment=0.50, twitter_sentiment=0.50),
    ]
    result: SentimentResult = await process_sentiment(two_days)

    assert result.roc_direction == "decelerating"


# ---------------------------------------------------------------------------
# 7. Guard: avg_yesterday == 0 → ROC = 0.0 (no ZeroDivisionError)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_avg_yesterday_zero_roc_is_zero() -> None:
    """If both sentiment fields are 0 for yesterday, ROC must be 0.0 (not raise)."""
    two_days = [
        _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.0, twitter_sentiment=0.0),
        _make_row("2026-02-23 14:00:00", stocktwits_sentiment=0.65, twitter_sentiment=0.72),
    ]
    result: SentimentResult = await process_sentiment(two_days)

    assert result.rate_of_change == pytest.approx(0.0)
    assert result.roc_direction == "stable"


# ---------------------------------------------------------------------------
# 8. Volume spike detection: today > 2x 7-day average
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_volume_spike_detected_when_today_exceeds_2x_average() -> None:
    """volume_spike must be True when today's mentions exceed 2x the 7-day mean."""
    # Build 6 baseline days at 1000 mentions each
    baseline = [
        _make_row(f"2026-02-{17 + i:02d} 14:00:00", stocktwits_posts=500, twitter_posts=500)
        for i in range(6)
    ]
    # Today: 10000 mentions (far above 2x of ~1000 average)
    today = _make_row("2026-02-23 14:00:00", stocktwits_posts=5000, twitter_posts=5000)
    result: SentimentResult = await process_sentiment(baseline + [today])

    assert result.volume_spike is True


# ---------------------------------------------------------------------------
# 9. Volume spike not triggered when today is within normal range
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_volume_spike_when_below_threshold() -> None:
    """volume_spike must be False when today's mentions are <= 2x the average."""
    rows = [
        _make_row(f"2026-02-{17 + i:02d} 14:00:00", stocktwits_posts=500, twitter_posts=500)
        for i in range(7)
    ]
    result: SentimentResult = await process_sentiment(rows)

    assert result.volume_spike is False


# ---------------------------------------------------------------------------
# 10. No volume spike when all mentions are zero
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_volume_spike_all_zero_mentions() -> None:
    """When all mention counts are zero, volume_spike must be False (no div-by-zero)."""
    rows = [
        _make_row(f"2026-02-{17 + i:02d} 14:00:00", stocktwits_posts=0, twitter_posts=0)
        for i in range(7)
    ]
    result: SentimentResult = await process_sentiment(rows)

    assert result.volume_spike is False
    assert result.mention_volume_today == 0
    assert result.mention_volume_7d_avg == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 11. Composite score is clamped to [-100, +100]
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_composite_score_clamped() -> None:
    """Composite score must never exceed +100 or go below -100."""
    # Extreme bullish scenario
    ultra_bullish = [
        _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.90, twitter_sentiment=0.90),
        _make_row("2026-02-23 14:00:00", stocktwits_sentiment=1.0, twitter_sentiment=1.0,
                  stocktwits_posts=99999, twitter_posts=99999),
    ]
    result_bull: SentimentResult = await process_sentiment(ultra_bullish)
    assert result_bull.current_score <= 100.0

    # Extreme bearish scenario
    ultra_bearish = [
        _make_row("2026-02-22 14:00:00", stocktwits_sentiment=0.10, twitter_sentiment=0.10),
        _make_row("2026-02-23 14:00:00", stocktwits_sentiment=0.0, twitter_sentiment=0.0),
    ]
    result_bear: SentimentResult = await process_sentiment(ultra_bearish)
    assert result_bear.current_score >= -100.0


# ---------------------------------------------------------------------------
# 12. Bullish label when score > LABEL_BULLISH_THRESHOLD
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bullish_label_when_score_above_threshold() -> None:
    """High sentiment must produce label='Bullish'."""
    bullish_row = [
        _make_row("2026-02-23 14:00:00",
                  stocktwits_sentiment=0.85, twitter_sentiment=0.90)
    ]
    result: SentimentResult = await process_sentiment(bullish_row)

    assert result.sentiment_label == "Bullish"
    assert result.current_score > LABEL_BULLISH_THRESHOLD


# ---------------------------------------------------------------------------
# 13. Bearish label when score < LABEL_BEARISH_THRESHOLD
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bearish_label_when_score_below_threshold() -> None:
    """Low sentiment must produce label='Bearish'."""
    bearish_row = [
        _make_row("2026-02-23 14:00:00",
                  stocktwits_sentiment=0.10, twitter_sentiment=0.05)
    ]
    result: SentimentResult = await process_sentiment(bearish_row)

    assert result.sentiment_label == "Bearish"
    assert result.current_score < LABEL_BEARISH_THRESHOLD


# ---------------------------------------------------------------------------
# 14. Neutral label for mid-range sentiment
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_neutral_label_for_mid_range_sentiment() -> None:
    """Mid-range sentiment (avg ~0.5) must produce label='Neutral'."""
    neutral_row = [
        _make_row("2026-02-23 14:00:00",
                  stocktwits_sentiment=0.50, twitter_sentiment=0.50)
    ]
    result: SentimentResult = await process_sentiment(neutral_row)

    assert result.sentiment_label == "Neutral"


# ---------------------------------------------------------------------------
# 15. History excludes today and is ordered oldest first
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_history_excludes_today_and_is_oldest_first() -> None:
    """history list must not include today's row and must be sorted oldest first."""
    result: SentimentResult = await process_sentiment(SEVEN_DAY_DATA)

    # With 7 days of data, history should have 6 entries (all but today)
    assert len(result.history) == 6

    dates = [row.date for row in result.history]
    assert dates == sorted(dates), f"Expected oldest-first order, got: {dates}"

    # Today's date (2026-02-23) must not appear in history
    assert "2026-02-23" not in dates


# ---------------------------------------------------------------------------
# 16. Missing optional fields default to 0 (no KeyError)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_optional_fields_default_to_zero() -> None:
    """Rows with missing sentiment/count fields must default to 0 without raising."""
    sparse_row = [
        {
            "date": "2026-02-23 14:00:00",
            "symbol": "NVDA",
            # stocktwitsSentiment, twitterSentiment, post counts all missing
        }
    ]
    result: SentimentResult = await process_sentiment(sparse_row)

    # All missing → avg_sentiment = 0.0 → score = (0 - 0.5) * 200 = -100
    assert result.current_score == pytest.approx(-100.0)
    assert result.mention_volume_today == 0


# ---------------------------------------------------------------------------
# 17. last_updated is a non-empty UTC timestamp ending with 'Z'
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_last_updated_is_utc_string() -> None:
    """last_updated must be a non-empty string ending in 'Z'."""
    result: SentimentResult = await process_sentiment(SEVEN_DAY_DATA)

    assert isinstance(result.last_updated, str)
    assert result.last_updated.endswith("Z")
    assert len(result.last_updated) > 0


# ---------------------------------------------------------------------------
# 18. Engine tolerates unsorted input (handles any date ordering)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unsorted_input_handled_correctly() -> None:
    """The engine must sort data by date internally regardless of input order."""
    # Provide rows in reversed (oldest-first) order
    reversed_data = list(reversed(SEVEN_DAY_DATA))
    result_sorted: SentimentResult = await process_sentiment(SEVEN_DAY_DATA)
    result_reversed: SentimentResult = await process_sentiment(reversed_data)

    # Both should produce the same current_score and mention_volume_today
    assert result_sorted.current_score == pytest.approx(result_reversed.current_score, abs=0.01)
    assert result_sorted.mention_volume_today == result_reversed.mention_volume_today
