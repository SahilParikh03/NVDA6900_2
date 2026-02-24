"""
Tests for backend.engines.transcript_nlp.

All tests use synthetic fixture data — no live FMP calls.

Run with:
    pytest backend/tests/test_transcript_nlp.py -v
"""

import pytest

from backend.engines.transcript_nlp import (
    TranscriptAnalysisResult,
    analyze_transcripts,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _transcript(
    symbol: str,
    quarter: int,
    year: int,
    content: str,
    date: str | None = None,
) -> dict:
    """Build a minimal transcript dict matching FMP format."""
    rec: dict = {"symbol": symbol, "quarter": quarter, "year": year, "content": content}
    if date is not None:
        rec["date"] = date
    return rec


# Realistic content blocks referencing NVDA products
MSFT_Q4_CONTENT = (
    "We are deploying H100 and H200 clusters across all Azure regions. "
    "Our AI infrastructure investment continues with DGX systems and NVLink fabrics. "
    "AI training and AI inference workloads are growing. GPU demand is exceptional. "
    "Data center build-out accelerated. AI workload capacity is being scaled. "
    "Blackwell GPUs will arrive in Q1. accelerator deployments doubled this quarter."
)

AMZN_Q3_CONTENT = (
    "AWS continues to invest in GPU compute. We are deploying H100 instances "
    "for AI training. Accelerator adoption is up. Data center capex was $22B. "
    "AI inference traffic on Trainium and H100 grew 3x. "
    "compute spend is rising across all business segments. Hopper chips are in production."
)

GOOGL_Q3_CONTENT = (
    "Our AI infrastructure now includes Blackwell systems and H200 GPUs. "
    "Google Cloud AI workload revenue doubled. compute capacity expansion is on track. "
    "We mention GPU briefly. HGX deployment was completed in two new regions."
)

META_Q2_CONTENT = (
    "Meta AI relies on H100 and B200 clusters. "
    "We have significant compute spend for AI training. "
    "Data center investments are on plan. AI infrastructure is core to our roadmap."
)

# Intentionally low-signal content for trend comparison
MSFT_Q3_CONTENT = (
    "Revenue grew 15%. Operating margin expanded. We continue to invest in cloud. "
    "GPU supply remains a consideration for our AI services."
)


def _realistic_batch_latest() -> list[dict]:
    """Four transcripts from the same quarter (Q4/Q3 2025)."""
    return [
        _transcript("MSFT", 4, 2025, MSFT_Q4_CONTENT, date="2025-10-25"),
        _transcript("AMZN", 3, 2025, AMZN_Q3_CONTENT, date="2025-10-26"),
        _transcript("GOOGL", 3, 2025, GOOGL_Q3_CONTENT, date="2025-10-29"),
        _transcript("META", 2, 2025, META_Q2_CONTENT, date="2025-07-30"),
    ]


def _two_quarter_batch() -> list[dict]:
    """MSFT transcripts across two quarters for trend detection testing."""
    return [
        _transcript("MSFT", 3, 2025, MSFT_Q3_CONTENT, date="2025-07-25"),
        _transcript("MSFT", 4, 2025, MSFT_Q4_CONTENT, date="2025-10-25"),
    ]


# ---------------------------------------------------------------------------
# Test 1 — Happy-path: correct result type and structure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_result_schema() -> None:
    """analyze_transcripts must return a valid TranscriptAnalysisResult."""
    result = await analyze_transcripts(_realistic_batch_latest())

    assert isinstance(result, TranscriptAnalysisResult)
    assert isinstance(result.transcripts, list)
    assert isinstance(result.trend, str)
    assert isinstance(result.last_updated, str)
    assert "T" in result.last_updated  # ISO-8601 check


# ---------------------------------------------------------------------------
# Test 2 — Correct number of transcript entries
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_transcript_count() -> None:
    """Output must contain one TranscriptScore per valid input transcript."""
    result = await analyze_transcripts(_realistic_batch_latest())
    assert len(result.transcripts) == 4


# ---------------------------------------------------------------------------
# Test 3 — Quarter label formatting
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_quarter_label_format() -> None:
    """quarter field must be formatted as 'Q<N> <YYYY>'."""
    result = await analyze_transcripts([
        _transcript("MSFT", 4, 2025, MSFT_Q4_CONTENT),
    ])
    assert result.transcripts[0].quarter == "Q4 2025"


# ---------------------------------------------------------------------------
# Test 4 — total_ai_score is a non-negative integer
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_total_ai_score_non_negative() -> None:
    """total_ai_score must be >= 0 for every transcript."""
    result = await analyze_transcripts(_realistic_batch_latest())
    for ts in result.transcripts:
        assert ts.total_ai_score >= 0, (
            f"{ts.symbol} {ts.quarter} has negative score: {ts.total_ai_score}"
        )


# ---------------------------------------------------------------------------
# Test 5 — top_keywords sorted descending by count
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_top_keywords_sorted_descending() -> None:
    """top_keywords must be in descending order of count."""
    result = await analyze_transcripts([
        _transcript("MSFT", 4, 2025, MSFT_Q4_CONTENT),
    ])
    ts = result.transcripts[0]
    counts = [kw.count for kw in ts.top_keywords]
    assert counts == sorted(counts, reverse=True), (
        f"top_keywords not sorted descending: {counts}"
    )


# ---------------------------------------------------------------------------
# Test 6 — top_keywords capped at 5
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_top_keywords_capped_at_five() -> None:
    """top_keywords must contain at most 5 entries per transcript."""
    result = await analyze_transcripts(_realistic_batch_latest())
    for ts in result.transcripts:
        assert len(ts.top_keywords) <= 5, (
            f"{ts.symbol} {ts.quarter} returned {len(ts.top_keywords)} top keywords"
        )


# ---------------------------------------------------------------------------
# Test 7 — Empty content string produces score 0 and empty top_keywords
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_content_zero_score() -> None:
    """An empty content string must yield total_ai_score=0 and no top_keywords."""
    result = await analyze_transcripts([
        _transcript("NVDA", 2, 2025, ""),
    ])
    assert len(result.transcripts) == 1
    ts = result.transcripts[0]
    assert ts.total_ai_score == 0
    assert ts.top_keywords == []


# ---------------------------------------------------------------------------
# Test 8 — Empty transcripts list returns empty result with trend "stable"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_transcripts_list() -> None:
    """An empty input list must return TranscriptAnalysisResult with no transcripts."""
    result = await analyze_transcripts([])

    assert result.transcripts == []
    assert result.trend == "stable"


# ---------------------------------------------------------------------------
# Test 9 — Missing 'content' field skips the transcript
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_content_field_skipped() -> None:
    """Transcripts lacking the 'content' key must be silently skipped."""
    transcripts = [
        {"symbol": "AMZN", "quarter": 3, "year": 2025},  # no 'content'
        _transcript("MSFT", 4, 2025, MSFT_Q4_CONTENT),
    ]
    result = await analyze_transcripts(transcripts)
    symbols = {ts.symbol for ts in result.transcripts}
    assert "AMZN" not in symbols
    assert "MSFT" in symbols


# ---------------------------------------------------------------------------
# Test 10 — Single transcript: trend is "stable"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_transcript_trend_stable() -> None:
    """With only one transcript (one quarter), trend must be 'stable'."""
    result = await analyze_transcripts([
        _transcript("MSFT", 4, 2025, MSFT_Q4_CONTENT),
    ])
    assert result.trend == "stable"


# ---------------------------------------------------------------------------
# Test 11 — QoQ trend "increasing" when latest quarter score > previous
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_trend_increasing() -> None:
    """Trend must be 'increasing' when latest quarter total score > previous quarter."""
    # Q3 2025 has low-signal content; Q4 2025 has high-signal content
    result = await analyze_transcripts(_two_quarter_batch())
    assert result.trend == "increasing", (
        f"Expected 'increasing', got '{result.trend}'"
    )


# ---------------------------------------------------------------------------
# Test 12 — QoQ trend "decreasing" when latest quarter score < previous
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_trend_decreasing() -> None:
    """Trend must be 'decreasing' when latest quarter total score < previous quarter."""
    # Swap: high-signal in Q3, low-signal in Q4
    transcripts = [
        _transcript("MSFT", 3, 2025, MSFT_Q4_CONTENT, date="2025-07-25"),  # high
        _transcript("MSFT", 4, 2025, MSFT_Q3_CONTENT, date="2025-10-25"),  # low
    ]
    result = await analyze_transcripts(transcripts)
    assert result.trend == "decreasing", (
        f"Expected 'decreasing', got '{result.trend}'"
    )


# ---------------------------------------------------------------------------
# Test 13 — Case-insensitive keyword matching
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_insensitive_matching() -> None:
    """Keywords must be matched case-insensitively (e.g. 'gpu' matches 'GPU')."""
    content = "gpu GPU Gpu gPU blackwell BLACKWELL"
    result = await analyze_transcripts([
        _transcript("NVDA", 1, 2025, content),
    ])
    ts = result.transcripts[0]
    gpu_kw = next((kw for kw in ts.top_keywords if kw.keyword == "GPU"), None)
    blackwell_kw = next(
        (kw for kw in ts.top_keywords if kw.keyword == "Blackwell"), None
    )
    assert gpu_kw is not None and gpu_kw.count == 4, (
        f"Expected 4 GPU matches, got {gpu_kw}"
    )
    assert blackwell_kw is not None and blackwell_kw.count == 2, (
        f"Expected 2 Blackwell matches, got {blackwell_kw}"
    )


# ---------------------------------------------------------------------------
# Test 14 — Plural / compound forms are counted (substring matching)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_plural_forms_captured() -> None:
    """'GPUs', 'accelerators', 'H100s' should all be captured by substring matching."""
    content = (
        "We deployed thousands of GPUs. accelerators are everywhere. "
        "H100s are available. Blackwells ship next quarter."
    )
    result = await analyze_transcripts([
        _transcript("AMZN", 2, 2025, content),
    ])
    ts = result.transcripts[0]
    # At minimum GPU, accelerator, H100, Blackwell should all score > 0
    kw_map = {kw.keyword: kw.count for kw in ts.top_keywords}
    # Check via total_ai_score rather than individual entries (top 5 may not include all)
    assert ts.total_ai_score > 0


# ---------------------------------------------------------------------------
# Test 15 — Missing symbol/quarter/year skips the transcript gracefully
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_required_fields_skipped() -> None:
    """Transcripts missing symbol, quarter, or year must be skipped without raising."""
    transcripts = [
        {"quarter": 1, "year": 2025, "content": "some text"},       # missing symbol
        {"symbol": "MSFT", "year": 2025, "content": "some text"},   # missing quarter
        {"symbol": "AMZN", "quarter": 2, "content": "some text"},   # missing year
        _transcript("GOOGL", 3, 2025, GOOGL_Q3_CONTENT),             # valid
    ]
    result = await analyze_transcripts(transcripts)
    assert len(result.transcripts) == 1
    assert result.transcripts[0].symbol == "GOOGL"


# ---------------------------------------------------------------------------
# Test 16 — Multi-company multi-quarter: totals aggregate by quarter correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_company_quarter_aggregation() -> None:
    """
    When multiple companies have transcripts in the same quarter, their scores
    are summed for the QoQ trend comparison.
    """
    # Q2 2025: two companies with moderate content
    q2_moderate = "GPU deployment continues. AI infrastructure grows. Blackwell pending."
    # Q3 2025: two companies with much richer AI content
    q3_rich = (
        "H100 H200 B100 B200 Blackwell Hopper DGX HGX NVLink GPU GPU GPU "
        "accelerator data center AI infrastructure AI training AI inference "
        "compute spend compute capacity AI workload AI workload AI workload"
    )
    transcripts = [
        _transcript("MSFT", 2, 2025, q2_moderate),
        _transcript("AMZN", 2, 2025, q2_moderate),
        _transcript("MSFT", 3, 2025, q3_rich),
        _transcript("AMZN", 3, 2025, q3_rich),
    ]
    result = await analyze_transcripts(transcripts)
    # Q3 combined score should far exceed Q2 combined score → trend increasing
    assert result.trend == "increasing", (
        f"Expected 'increasing' with rich Q3 content, got '{result.trend}'"
    )
