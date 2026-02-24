"""
Transcript NLP Engine — AI keyword frequency analysis of earnings call transcripts.

Accepts raw FMP earnings call transcript data for hyperscaler companies (MSFT,
AMZN, GOOGL, META, NVDA) and produces per-transcript AI keyword scores plus a
quarter-over-quarter trend across all companies.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — AI keyword sets
# ---------------------------------------------------------------------------

# Hardware-specific model / platform names
HARDWARE_KEYWORDS: tuple[str, ...] = (
    "H100",
    "H200",
    "B100",
    "B200",
    "Blackwell",
    "Hopper",
    "Grace",
    "DGX",
    "HGX",
    "NVLink",
)

# Category / theme terms
CATEGORY_KEYWORDS: tuple[str, ...] = (
    "GPU",
    "accelerator",
    "data center",
    "AI infrastructure",
    "AI training",
    "AI inference",
    "compute spend",
    "compute capacity",
    "AI workload",
)

# Combined list used for scoring (order preserved for consistency)
ALL_KEYWORDS: tuple[str, ...] = HARDWARE_KEYWORDS + CATEGORY_KEYWORDS

# Maximum top-keywords returned per transcript
TOP_KEYWORDS_LIMIT = 5

# Trend labels
TREND_INCREASING = "increasing"
TREND_DECREASING = "decreasing"
TREND_STABLE = "stable"


# ---------------------------------------------------------------------------
# Output models (Pydantic v2)
# ---------------------------------------------------------------------------


class KeywordCount(BaseModel):
    """A single keyword and its mention count within a transcript."""

    keyword: str
    count: int


class TranscriptScore(BaseModel):
    """AI-keyword scoring for a single earnings call transcript."""

    symbol: str
    quarter: str = Field(description="Quarter label, e.g. 'Q4 2025'")
    total_ai_score: int = Field(description="Sum of all keyword occurrences")
    top_keywords: list[KeywordCount] = Field(
        description=f"Top {TOP_KEYWORDS_LIMIT} keywords by mention count"
    )


class TranscriptAnalysisResult(BaseModel):
    """Top-level output of the transcript NLP engine."""

    transcripts: list[TranscriptScore] = Field(default_factory=list)
    trend: str = Field(
        description=(
            "'increasing' if latest quarter total score exceeds previous quarter, "
            "'decreasing' if lower, 'stable' if equal or only one quarter available"
        )
    )
    last_updated: str = Field(description="ISO-8601 UTC timestamp")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _quarter_label(quarter: int, year: int) -> str:
    """Return a human-readable quarter label, e.g. 'Q4 2025'."""
    return f"Q{quarter} {year}"


def _score_transcript(content: str) -> tuple[int, list[KeywordCount]]:
    """
    Count AI keyword occurrences in transcript text.

    Uses case-insensitive substring counting (`str.lower().count(...)`) which
    naturally captures plural and compound forms (e.g. "GPUs", "DGX systems").

    Returns
    -------
    (total_score, top_keywords)
        total_score  — sum of all keyword hits
        top_keywords — up to TOP_KEYWORDS_LIMIT KeywordCount objects, sorted
                       descending by count, ties broken by original keyword order
    """
    lowered = content.lower()
    counts: list[KeywordCount] = []

    for keyword in ALL_KEYWORDS:
        count = lowered.count(keyword.lower())
        counts.append(KeywordCount(keyword=keyword, count=count))

    # Sort descending by count; stable sort preserves ALL_KEYWORDS order for ties
    counts.sort(key=lambda kc: kc.count, reverse=True)

    total_score = sum(kc.count for kc in counts)
    top_keywords = [kc for kc in counts[:TOP_KEYWORDS_LIMIT] if kc.count > 0]

    return total_score, top_keywords


def _determine_trend(scored: list[tuple[str, int]]) -> str:
    """
    Determine QoQ trend from a time-ordered list of (quarter_key, total_score) tuples.

    `quarter_key` is used only for sorting; it must be a lexicographically
    sortable string (ISO-8601 date preferred).

    With fewer than 2 data points the trend is always "stable".
    """
    if len(scored) < 2:
        return TREND_STABLE

    latest_score = scored[-1][1]
    previous_score = scored[-2][1]

    if latest_score > previous_score:
        return TREND_INCREASING
    if latest_score < previous_score:
        return TREND_DECREASING
    return TREND_STABLE


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def analyze_transcripts(
    transcripts: list[dict],
) -> TranscriptAnalysisResult:
    """
    Analyze AI keyword frequency across earnings call transcripts.

    Parameters
    ----------
    transcripts:
        List of transcript dicts.  Each dict must contain:
            - "symbol":  str — ticker (e.g. "MSFT")
            - "quarter": int — fiscal quarter number (1-4)
            - "year":    int — calendar year
            - "content": str — full transcript text
        Optional field:
            - "date":    str — ISO-8601 date; used for QoQ trend sorting when
                               multiple quarters span calendar year boundaries.
                               Falls back to constructed date from year/quarter.

    Returns
    -------
    TranscriptAnalysisResult
        Per-transcript scores and an aggregate quarter-over-quarter trend.
    """
    if not transcripts:
        logger.info(
            "analyze_transcripts called with empty list — returning empty result"
        )
        return TranscriptAnalysisResult(
            transcripts=[],
            trend=TREND_STABLE,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    transcript_scores: list[TranscriptScore] = []

    # Track (sort_key, total_score) per quarter across all companies for trend calc
    # sort_key format: "YYYY-QN" so lexicographic sort works correctly
    quarter_totals: dict[str, int] = {}

    for raw in transcripts:
        symbol = raw.get("symbol")
        quarter_int = raw.get("quarter")
        year_int = raw.get("year")

        # Validate minimum required fields
        if symbol is None or quarter_int is None or year_int is None:
            logger.warning(
                "Skipping transcript with missing symbol/quarter/year: %r",
                {k: raw.get(k) for k in ("symbol", "quarter", "year")},
            )
            continue

        content = raw.get("content")
        if content is None:
            logger.warning(
                "[%s Q%s %s] Skipping transcript — missing 'content' field",
                symbol,
                quarter_int,
                year_int,
            )
            continue

        if not isinstance(content, str):
            logger.warning(
                "[%s Q%s %s] Skipping transcript — 'content' is not a string (got %s)",
                symbol,
                quarter_int,
                year_int,
                type(content).__name__,
            )
            continue

        if content == "":
            logger.debug(
                "[%s Q%s %s] Empty content — score will be 0",
                symbol,
                quarter_int,
                year_int,
            )
            total_score = 0
            top_keywords: list[KeywordCount] = []
        else:
            total_score, top_keywords = _score_transcript(content)

        quarter_label = _quarter_label(quarter_int, year_int)

        logger.info(
            "[%s %s] total_ai_score=%d, top=%s",
            symbol,
            quarter_label,
            total_score,
            [f"{kc.keyword}:{kc.count}" for kc in top_keywords[:3]],
        )

        transcript_scores.append(
            TranscriptScore(
                symbol=symbol,
                quarter=quarter_label,
                total_ai_score=total_score,
                top_keywords=top_keywords,
            )
        )

        # Aggregate totals by quarter for trend detection.
        # Sort key: "YYYY-QN" (zero-pad quarter so Q1..Q4 sort correctly within a year)
        sort_key = f"{year_int:04d}-Q{quarter_int}"
        quarter_totals[sort_key] = quarter_totals.get(sort_key, 0) + total_score

    # Build time-ordered list of (sort_key, total) and derive trend
    sorted_quarters = sorted(quarter_totals.items())  # ascending by sort_key
    trend = _determine_trend(sorted_quarters)

    logger.info(
        "Transcript analysis complete: %d transcripts processed, trend=%s",
        len(transcript_scores),
        trend,
    )

    return TranscriptAnalysisResult(
        transcripts=transcript_scores,
        trend=trend,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
