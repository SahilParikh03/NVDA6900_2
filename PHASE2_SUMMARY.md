# PHASE 2 SUMMARY — Calculation Engines & API Routes Complete

> **Date completed:** February 24, 2026
> **Phase:** 2 of 4 (Calculation Engines)
> **Status:** COMPLETE — all Phase 2 tasks delivered, reviewed, and tested

---

## What Was Built

Phase 2 delivered all five calculation engines as standalone, testable Python modules, plus all six API route modules wiring those engines into the FastAPI backend. The full test suite now has **144 passing tests** across Phase 1 and Phase 2.

---

## Files Created / Modified

### Calculation Engines (5 files)

| File | Task ID | Tests | Description |
|------|---------|-------|-------------|
| `backend/engines/gex_engine.py` | P2-01 | 29 tests | Black-Scholes gamma calculation, GEX aggregation per strike, gamma flip detection. IV bisection method for missing implied volatility. Pydantic models: `StrikeGex`, `KeyLevels`, `GexResult`. |
| `backend/engines/unusual_activity.py` | P2-02 | 15 tests | Options volume/OI ratio scanner. Constants: `VOL_OI_RATIO_THRESHOLD=2.0`, `MIN_VOLUME_FILTER=1000`, `MAX_UNUSUAL_RESULTS=20`. Pydantic models: `UnusualContract`, `UnusualActivityResult`. |
| `backend/engines/sentiment_engine.py` | P2-03 | 18 tests | Social sentiment processor with ROC calculation, volume spike detection, composite score (-100 to +100). Constants: `SCORE_SENTIMENT_SCALE=200`, `VOLUME_SPIKE_MULTIPLIER=2.0`. Pydantic models: `SentimentHistoryEntry`, `SentimentResult`. |
| `backend/engines/capex_engine.py` | P2-04 | 15 tests | CapEx-to-revenue ratio calculator for MSFT, AMZN, GOOGL, META. QoQ growth with division-by-zero guards. Majority-vote aggregate trend. Pydantic models: `CapexQuarter`, `CapexCompany`, `CapexResult`. |
| `backend/engines/transcript_nlp.py` | P2-05 | 16 tests | Case-insensitive keyword frequency analysis across 19 AI-related keywords (hardware + category terms). Top-5 keywords per transcript, cross-company QoQ trend. Pydantic models: `KeywordCount`, `TranscriptScore`, `TranscriptAnalysisResult`. |

### Test Files (5 files)

| File | Test Count | Coverage |
|------|-----------|----------|
| `backend/tests/test_gex_engine.py` | 29 | Black-Scholes math, gamma flip, bisection IV, expired options, zero OI, empty chain, key levels, multi-expiration aggregation |
| `backend/tests/test_unusual_activity.py` | 15 | Happy path, sort order, ratio math, empty chain, zero OI/volume, boundary conditions, top-20 cap, put/call ratio |
| `backend/tests/test_sentiment_engine.py` | 18 | ROC calculation, direction labels, zero-division guard, volume spike, score clamping, Bullish/Bearish/Neutral labels, unsorted input |
| `backend/tests/test_capex_engine.py` | 15 | CapEx positivity, ratio math, QoQ growth, zero guards, empty data, aggregate trend, name fallback |
| `backend/tests/test_transcript_nlp.py` | 16 | Score accuracy, keyword sorting, top-5 cap, empty content, trend detection, case insensitivity, plural forms, missing fields |

### API Routes (6 files)

| File | Task ID | Endpoints | Description |
|------|---------|-----------|-------------|
| `backend/routes/price.py` | P2-06 | `GET /`, `GET /history`, `GET /change` | NVDA quote (cache-first), historical OHLCV, price performance periods |
| `backend/routes/options.py` | P2-06 | `GET /gex`, `GET /unusual` | GEX calculation via engine, unusual activity scanner via engine |
| `backend/routes/earnings.py` | P2-06 | `GET /`, `GET /calendar`, `GET /estimates`, `GET /surprises` | Consolidated earnings data, individual sub-endpoints. Partial degradation supported. |
| `backend/routes/sentiment.py` | P2-06 | `GET /`, `GET /news` | Processed sentiment via engine, raw news articles |
| `backend/routes/hyperscaler.py` | P2-06 | `GET /capex`, `GET /transcripts` | CapEx analysis via engine, transcript NLP analysis via engine |
| `backend/routes/predictions.py` | P2-06 | `GET /` | Rule-based qualitative outlook combining price, options, sentiment, and earnings signals |

### Infrastructure Files

| File | Change | Description |
|------|--------|-------------|
| `conftest.py` | **NEW** | Root conftest setting `FMP_API_KEY` env var for test environment |
| `backend/tests/test_config.py` | **MODIFIED** | Fixed `test_missing_api_key_raises_error` to use `monkeypatch.delenv` for conftest compatibility |

---

## CTO Review — Bugs Found & Fixed

| # | Issue | File | Fix Applied |
|---|-------|------|-------------|
| 1 | GEX engine imported `get_settings` but module uses `settings` singleton | `gex_engine.py:27` | Changed `from backend.config import get_settings` → `from backend.config import settings` |
| 2 | No root `conftest.py` — all engine tests that import config failed because `FMP_API_KEY` not in test env | Project root | Created `conftest.py` with `os.environ.setdefault("FMP_API_KEY", "test-key-not-real")` |
| 3 | Phase 1 config test `test_missing_api_key_raises_error` broke after conftest addition (env var now always set) | `test_config.py:19` | Added `monkeypatch.delenv("FMP_API_KEY", raising=False)` before the assertion |

---

## API Route Map

All routes registered and confirmed working:

| Route | Method | Source |
|-------|--------|--------|
| `/api/price/` | GET | price.py |
| `/api/price/history` | GET | price.py |
| `/api/price/change` | GET | price.py |
| `/api/options/gex` | GET | options.py |
| `/api/options/unusual` | GET | options.py |
| `/api/earnings/` | GET | earnings.py |
| `/api/earnings/calendar` | GET | earnings.py |
| `/api/earnings/estimates` | GET | earnings.py |
| `/api/earnings/surprises` | GET | earnings.py |
| `/api/sentiment/` | GET | sentiment.py |
| `/api/sentiment/news` | GET | sentiment.py |
| `/api/hyperscaler/capex` | GET | hyperscaler.py |
| `/api/hyperscaler/transcripts` | GET | hyperscaler.py |
| `/api/predictions/` | GET | predictions.py |
| `/health` | GET | main.py |

---

## Engine Function Signatures

### GEX Engine
```python
from backend.engines.gex_engine import calculate_gex, GexResult
result: GexResult = await calculate_gex(options_chain: list[dict], current_price: float)
# result.current_price, result.gamma_flip, result.total_gex, result.strikes[], result.key_levels, result.last_updated
```

### Unusual Activity Scanner
```python
from backend.engines.unusual_activity import scan_unusual_activity, UnusualActivityResult
result: UnusualActivityResult = await scan_unusual_activity(options_chain: list[dict])
# result.unusual_activity[], result.total_unusual_contracts, result.put_call_ratio_unusual, result.last_updated
```

### Sentiment Engine
```python
from backend.engines.sentiment_engine import process_sentiment, SentimentResult
result: SentimentResult = await process_sentiment(sentiment_data: list[dict])
# result.current_score, result.sentiment_label, result.rate_of_change, result.roc_direction
# result.mention_volume_today, result.mention_volume_7d_avg, result.volume_spike, result.history[], result.last_updated
```

### CapEx Engine
```python
from backend.engines.capex_engine import calculate_capex, CapexResult
result: CapexResult = await calculate_capex(companies_data: dict[str, dict])
# result.companies[].symbol, .name, .quarters[].period, .capex, .revenue, .capex_to_revenue, .capex_qoq_growth
# result.aggregate_trend, result.last_updated
```

### Transcript NLP Engine
```python
from backend.engines.transcript_nlp import analyze_transcripts, TranscriptAnalysisResult
result: TranscriptAnalysisResult = await analyze_transcripts(transcripts: list[dict])
# result.transcripts[].symbol, .quarter, .total_ai_score, .top_keywords[].keyword, .count
# result.trend, result.last_updated
```

---

## Test Summary

| Suite | Tests | Status |
|-------|-------|--------|
| Phase 1: config | 26 | PASS |
| Phase 1: cache | 10 | PASS |
| Phase 1: scheduler | 14 | PASS |
| Phase 2: gex_engine | 29 | PASS |
| Phase 2: unusual_activity | 15 | PASS |
| Phase 2: sentiment_engine | 18 | PASS |
| Phase 2: capex_engine | 15 | PASS |
| Phase 2: transcript_nlp | 16 | PASS |
| **TOTAL** | **144** | **ALL PASS** |

---

## What's Next — Phase 3: Frontend Dashboard

Phase 3 builds the single-page war room UI with 7 data panels:

| Task ID | Component | Depends On |
|---------|-----------|------------|
| P3-01 | `usePolling.ts` + `api/client.ts` (already scaffolded) | P1-07 (done) |
| P3-02 | `App.tsx` layout + `PricePanel.tsx` | P3-01 |
| P3-03 | `GexHeatmap.tsx` + `UnusualActivity.tsx` | P3-01 |
| P3-04 | `EarningsPanel.tsx` + `SentimentPanel.tsx` | P3-01 |
| P3-05 | `HyperscalerPanel.tsx` + `PredictionsPanel.tsx` | P3-01 |
| P3-06 | Loading skeletons + error states (all components) | P3-02 thru P3-05 |

P3-02 through P3-05 can run **in parallel** (independent component files). P3-06 runs after all panels are approved.

---

*Generated by CTO (Opus 4.6) — Phase 2 orchestration complete*
