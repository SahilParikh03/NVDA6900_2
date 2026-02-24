"""
Sentiment Engine.

Processes raw social sentiment data from FMP into actionable signals.

Accepts the last 7 days of sentiment data (most-recent day first or last
is both handled — data is sorted internally by date descending so index 0
is always "today").

Composite scoring formula
-------------------------
  base     = (avg_sentiment - 0.5) * 200          → maps [0,1] → [-100, +100]
  roc_adj  = clamp(roc * 20, -20, +20)
  vol_adj  = +10 if volume_spike else 0
  score    = clamp(base + roc_adj + vol_adj, -100, +100)

Labels
------
  score >  20 → "Bullish"
  score < -20 → "Bearish"
  else        → "Neutral"

ROC direction
-------------
  roc > 0 → "accelerating"
  roc < 0 → "decelerating"
  roc == 0 → "stable"
"""

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
SENTIMENT_DAYS: int = 7
VOLUME_SPIKE_MULTIPLIER: float = 2.0

SCORE_SENTIMENT_SCALE: float = 200.0
SCORE_SENTIMENT_MIDPOINT: float = 0.5
SCORE_ROC_MULTIPLIER: float = 20.0
SCORE_ROC_MAX: float = 20.0
SCORE_VOLUME_SPIKE_BONUS: float = 10.0
SCORE_MIN: float = -100.0
SCORE_MAX: float = 100.0

LABEL_BULLISH_THRESHOLD: float = 20.0
LABEL_BEARISH_THRESHOLD: float = -20.0


# ---------------------------------------------------------------------------
# Output schemas (Pydantic v2)
# ---------------------------------------------------------------------------
class SentimentDay(BaseModel):
    """Per-day historical sentiment snapshot."""

    date: str = Field(..., description="ISO date YYYY-MM-DD")
    score: float = Field(..., description="Composite score for this day (-100 to +100)")
    mentions: int = Field(..., description="Total posts (Stocktwits + Twitter)")


class SentimentResult(BaseModel):
    """Full result from the sentiment engine."""

    current_score: float = Field(..., description="Today's composite score (-100 to +100)")
    sentiment_label: str = Field(..., description="Bullish / Neutral / Bearish")
    rate_of_change: float = Field(
        ..., description="(today_avg - yesterday_avg) / abs(yesterday_avg)"
    )
    roc_direction: str = Field(..., description="accelerating / stable / decelerating")
    mention_volume_today: int = Field(..., description="Total posts today")
    mention_volume_7d_avg: float = Field(..., description="7-day average post count")
    volume_spike: bool = Field(
        ..., description="True when today's mentions > 2x 7-day average"
    )
    history: list[SentimentDay] = Field(
        ..., description="Per-day scores excluding today, oldest-first"
    )
    last_updated: str = Field(..., description="ISO-8601 UTC timestamp")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _clamp(value: float, low: float, high: float) -> float:
    """Return value clamped to [low, high]."""
    return max(low, min(high, value))


def _avg_sentiment(row: dict) -> float:
    """Average of stocktwitsSentiment and twitterSentiment for one row."""
    st: float = float(row.get("stocktwitsSentiment") or 0.0)
    tw: float = float(row.get("twitterSentiment") or 0.0)
    return (st + tw) / 2.0


def _total_mentions(row: dict) -> int:
    """Sum of post counts for one row."""
    st_posts: int = int(row.get("stocktwitsPostsCount") or 0)
    tw_posts: int = int(row.get("twitterPostsCount") or 0)
    return st_posts + tw_posts


def _composite_score(avg_sentiment: float, roc: float, volume_spike: bool) -> float:
    """Compute the composite score and clamp to [-100, +100]."""
    base: float = (avg_sentiment - SCORE_SENTIMENT_MIDPOINT) * SCORE_SENTIMENT_SCALE
    roc_adj: float = _clamp(roc * SCORE_ROC_MULTIPLIER, -SCORE_ROC_MAX, SCORE_ROC_MAX)
    vol_adj: float = SCORE_VOLUME_SPIKE_BONUS if volume_spike else 0.0
    return _clamp(base + roc_adj + vol_adj, SCORE_MIN, SCORE_MAX)


def _sentiment_label(score: float) -> str:
    if score > LABEL_BULLISH_THRESHOLD:
        return "Bullish"
    if score < LABEL_BEARISH_THRESHOLD:
        return "Bearish"
    return "Neutral"


def _roc_direction(roc: float) -> str:
    if roc > 0.0:
        return "accelerating"
    if roc < 0.0:
        return "decelerating"
    return "stable"


def _parse_date(row: dict) -> datetime:
    """
    Parse the 'date' field from a sentiment row.
    FMP format is 'YYYY-MM-DD HH:MM:SS'.
    Falls back to epoch on parse failure.
    """
    raw: str = str(row.get("date", ""))
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse date field: %r — defaulting to epoch", raw)
    return datetime.fromtimestamp(0)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
async def process_sentiment(
    sentiment_data: list[dict],
) -> SentimentResult:
    """
    Process raw FMP social sentiment data into actionable signals.

    Args:
        sentiment_data: List of daily sentiment dicts (up to 7 days).
                        May be in any date order; the engine sorts internally.

    Returns:
        SentimentResult with composite score, label, ROC and history.
    """
    now_utc: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Edge case: empty data ---
    if not sentiment_data:
        logger.info("process_sentiment: received empty sentiment data — returning neutral defaults")
        return SentimentResult(
            current_score=0.0,
            sentiment_label="Neutral",
            rate_of_change=0.0,
            roc_direction="stable",
            mention_volume_today=0,
            mention_volume_7d_avg=0.0,
            volume_spike=False,
            history=[],
            last_updated=now_utc,
        )

    # Sort descending by date so index 0 = most recent ("today")
    sorted_data: list[dict] = sorted(
        sentiment_data, key=_parse_date, reverse=True
    )[:SENTIMENT_DAYS]

    today_row: dict = sorted_data[0]

    # --- Today's values ---
    avg_today: float = _avg_sentiment(today_row)
    mentions_today: int = _total_mentions(today_row)

    # --- Yesterday's values (for ROC) ---
    roc: float = 0.0
    if len(sorted_data) >= 2:
        yesterday_row: dict = sorted_data[1]
        avg_yesterday: float = _avg_sentiment(yesterday_row)
        if avg_yesterday == 0.0:
            logger.debug("process_sentiment: avg_yesterday == 0, ROC set to 0.0")
            roc = 0.0
        else:
            roc = (avg_today - avg_yesterday) / abs(avg_yesterday)
    else:
        logger.info(
            "process_sentiment: only 1 day of data available — ROC set to 0.0"
        )

    # --- 7-day average mention volume (includes today) ---
    all_mentions: list[int] = [_total_mentions(row) for row in sorted_data]
    total_mentions_sum: int = sum(all_mentions)
    avg_7d_mentions: float = (
        total_mentions_sum / len(all_mentions) if all_mentions else 0.0
    )

    # Volume spike: today's mentions > 2x 7-day average, guard all-zero
    volume_spike: bool = (
        avg_7d_mentions > 0.0
        and mentions_today > VOLUME_SPIKE_MULTIPLIER * avg_7d_mentions
    )

    # --- Composite score ---
    score: float = _composite_score(avg_today, roc, volume_spike)

    # --- Historical rows (everything except today), oldest first ---
    history: list[SentimentDay] = []
    for row in reversed(sorted_data[1:]):
        row_avg: float = _avg_sentiment(row)
        row_mentions: int = _total_mentions(row)
        # Compute score for history entry (no ROC/volume context for older days)
        row_score: float = _composite_score(row_avg, 0.0, False)
        date_str: str = _parse_date(row).strftime("%Y-%m-%d")
        history.append(
            SentimentDay(date=date_str, score=round(row_score, 2), mentions=row_mentions)
        )

    logger.info(
        "process_sentiment: score=%.1f label=%s roc=%.4f spike=%s",
        score,
        _sentiment_label(score),
        roc,
        volume_spike,
    )

    return SentimentResult(
        current_score=round(score, 2),
        sentiment_label=_sentiment_label(score),
        rate_of_change=round(roc, 6),
        roc_direction=_roc_direction(roc),
        mention_volume_today=mentions_today,
        mention_volume_7d_avg=round(avg_7d_mentions, 2),
        volume_spike=volume_spike,
        history=history,
        last_updated=now_utc,
    )


# ---------------------------------------------------------------------------
# Twitter / SocialData.tools helpers
# ---------------------------------------------------------------------------

# Keyword sets for basic polarity scoring
_BULLISH_KEYWORDS: frozenset[str] = frozenset(
    {
        "bullish",
        "buy",
        "long",
        "calls",
        "moon",
        "rocket",
        "up",
        "beat",
        "crush",
        "strong",
        "breakout",
        "higher",
    }
)

_BEARISH_KEYWORDS: frozenset[str] = frozenset(
    {
        "bearish",
        "sell",
        "short",
        "puts",
        "crash",
        "down",
        "miss",
        "weak",
        "dump",
        "lower",
        "overvalued",
    }
)


def _tweet_raw_score(text: str) -> float:
    """
    Keyword-based polarity for a single tweet.

    Tokenises *text* to lowercase words and counts bullish vs bearish
    keyword hits.  Returns a raw integer difference
    (bullish_count - bearish_count).  Returns 0.0 when *text* is empty.
    """
    if not text:
        return 0.0
    words: list[str] = text.lower().split()
    bullish_hits: int = sum(1 for w in words if w in _BULLISH_KEYWORDS)
    bearish_hits: int = sum(1 for w in words if w in _BEARISH_KEYWORDS)
    return float(bullish_hits - bearish_hits)


def _normalize_tweet_score(raw: float) -> float:
    """
    Normalise a raw keyword difference to the [-1, +1] range.

    Uses a simple tanh-based squashing so that a single keyword hit
    pushes the score to ±0.76 and three hits reaches ±0.995, while
    zero keywords stays at exactly 0.
    """
    return math.tanh(raw)


def _tweet_engagement_weight(tweet: dict) -> float:
    """
    Engagement weight for a tweet.

    Weight = 1 + log2(1 + likes + retweets).
    A tweet with zero engagement has weight 1.0 (never drops below that).
    """
    likes: int = int(tweet.get("favorite_count") or 0)
    retweets: int = int(tweet.get("retweet_count") or 0)
    return 1.0 + math.log2(1.0 + likes + retweets)


def _parse_tweet_date(tweet: dict) -> str:
    """
    Extract the ISO date string (YYYY-MM-DD) from a tweet's ``created_at``
    field.  Returns ``"1970-01-01"`` on any parse failure.
    """
    raw: str = str(tweet.get("created_at", ""))
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning(
        "_parse_tweet_date: could not parse created_at=%r — defaulting to epoch date",
        raw,
    )
    return "1970-01-01"


def _aggregate_tweets_by_day(
    tweets: list[dict],
) -> dict[str, dict[str, float]]:
    """
    Group tweets by calendar date and compute per-day aggregates.

    Each entry in the returned dict has the shape::

        {
            "weighted_score_sum": float,   # sum of (score * weight) per tweet
            "weight_sum":         float,   # sum of engagement weights
            "count":              float,   # number of tweets that day
        }

    Keys are ISO date strings (YYYY-MM-DD).
    """
    days: dict[str, dict[str, float]] = defaultdict(
        lambda: {"weighted_score_sum": 0.0, "weight_sum": 0.0, "count": 0.0}
    )

    for tweet in tweets:
        date_str: str = _parse_tweet_date(tweet)
        text: str = str(tweet.get("full_text") or "")
        raw: float = _tweet_raw_score(text)
        norm: float = _normalize_tweet_score(raw)
        weight: float = _tweet_engagement_weight(tweet)

        days[date_str]["weighted_score_sum"] += norm * weight
        days[date_str]["weight_sum"] += weight
        days[date_str]["count"] += 1.0

    return dict(days)


def _day_sentiment_0_to_1(agg: dict[str, float]) -> float:
    """
    Convert a day's aggregate bucket to a sentiment value in [0, 1].

    Weighted average of normalised scores sits in [-1, +1]; map to [0, 1]
    via ``(avg + 1) / 2``.  Returns 0.5 (neutral) if weight_sum is zero.
    """
    weight_sum: float = agg["weight_sum"]
    if weight_sum == 0.0:
        return 0.5
    weighted_avg: float = agg["weighted_score_sum"] / weight_sum
    return (weighted_avg + 1.0) / 2.0


# ---------------------------------------------------------------------------
# Twitter sentiment engine entry point
# ---------------------------------------------------------------------------
async def process_twitter_sentiment(tweets: list[dict]) -> SentimentResult:
    """
    Process raw tweet dicts from SocialData.tools into a ``SentimentResult``.

    The function reuses the same composite scoring formula, ROC calculation,
    volume-spike detection, clamping, and labelling logic as
    ``process_sentiment``.  Only the *input parsing* and per-day
    sentiment derivation differ.

    Args:
        tweets: List of raw tweet dicts as returned by
                ``SocialDataClient.search_tweets``.  An empty list
                produces a neutral default result.

    Returns:
        ``SentimentResult`` with composite score, label, ROC, and history.
    """
    now_utc: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Edge case: no tweets ---
    if not tweets:
        logger.info(
            "process_twitter_sentiment: received empty tweet list — returning neutral defaults"
        )
        return SentimentResult(
            current_score=0.0,
            sentiment_label="Neutral",
            rate_of_change=0.0,
            roc_direction="stable",
            mention_volume_today=0,
            mention_volume_7d_avg=0.0,
            volume_spike=False,
            history=[],
            last_updated=now_utc,
        )

    # --- Aggregate tweets by calendar day ---
    day_buckets: dict[str, dict[str, float]] = _aggregate_tweets_by_day(tweets)

    # Sort dates descending (most recent first), cap to SENTIMENT_DAYS
    sorted_dates: list[str] = sorted(day_buckets.keys(), reverse=True)[:SENTIMENT_DAYS]

    # --- Today (index 0) ---
    today_date: str = sorted_dates[0]
    today_agg: dict[str, float] = day_buckets[today_date]
    avg_today: float = _day_sentiment_0_to_1(today_agg)
    mentions_today: int = int(today_agg["count"])

    # --- ROC vs yesterday (index 1) ---
    roc: float = 0.0
    if len(sorted_dates) >= 2:
        yesterday_date: str = sorted_dates[1]
        avg_yesterday: float = _day_sentiment_0_to_1(day_buckets[yesterday_date])
        if avg_yesterday == 0.0:
            logger.debug(
                "process_twitter_sentiment: avg_yesterday == 0, ROC set to 0.0"
            )
            roc = 0.0
        else:
            roc = (avg_today - avg_yesterday) / abs(avg_yesterday)
    else:
        logger.info(
            "process_twitter_sentiment: only 1 day of data available — ROC set to 0.0"
        )

    # --- 7-day average mention volume (includes today) ---
    all_counts: list[int] = [
        int(day_buckets[d]["count"]) for d in sorted_dates
    ]
    avg_7d_mentions: float = sum(all_counts) / len(all_counts) if all_counts else 0.0

    # Volume spike guard
    volume_spike: bool = (
        avg_7d_mentions > 0.0
        and mentions_today > VOLUME_SPIKE_MULTIPLIER * avg_7d_mentions
    )

    # --- Composite score ---
    score: float = _composite_score(avg_today, roc, volume_spike)

    # --- Historical rows (all days except today), oldest first ---
    history: list[SentimentDay] = []
    for date_str in reversed(sorted_dates[1:]):
        agg: dict[str, float] = day_buckets[date_str]
        day_avg: float = _day_sentiment_0_to_1(agg)
        day_mentions: int = int(agg["count"])
        day_score: float = _composite_score(day_avg, 0.0, False)
        history.append(
            SentimentDay(
                date=date_str,
                score=round(day_score, 2),
                mentions=day_mentions,
            )
        )

    logger.info(
        "process_twitter_sentiment: score=%.1f label=%s roc=%.4f spike=%s tweets=%d",
        score,
        _sentiment_label(score),
        roc,
        volume_spike,
        len(tweets),
    )

    return SentimentResult(
        current_score=round(score, 2),
        sentiment_label=_sentiment_label(score),
        rate_of_change=round(roc, 6),
        roc_direction=_roc_direction(roc),
        mention_volume_today=mentions_today,
        mention_volume_7d_avg=round(avg_7d_mentions, 2),
        volume_spike=volume_spike,
        history=history,
        last_updated=now_utc,
    )
