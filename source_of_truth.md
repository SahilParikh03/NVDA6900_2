# NVDA EARNINGS WAR ROOM — SOURCE OF TRUTH

> **Purpose of this document:** This is the single source of truth for the NVDA Earnings War Room project. It is intended to be read by the Claude Code Orchestrator and forwarded to all subagents. Every agent working on this project must read and follow this document before writing any code.

---

## 1. PROJECT OVERVIEW

### What We're Building

A single-page web dashboard — the "NVDA Earnings War Room" — that consolidates all critical data a trader needs before, during, and after NVIDIA's earnings report. Think: **Bloomberg Terminal for NVDA earnings, built for retail traders.**

### Core Philosophy

- **MVP first.** Ship something useful fast. Polish later.
- **Multi-source data layer.** Primary market data from Financial Modeling Prep (FMP) via their `/stable/` API. Prediction market data from Polymarket (no auth required). Social sentiment from SocialData.tools Twitter/X search API. All three are fetched by the Python backend — the frontend never calls external APIs directly.
- **Derived metrics via Python.** We don't pay for expensive GEX or sentiment APIs. We pull raw data from FMP and compute the "pro" metrics ourselves using Python (Black-Scholes, NLP keyword analysis, CapEx ratios).
- **Guide, not oracle.** This dashboard is a decision-support tool. Users are explicitly told that data may be delayed and should always verify with their own brokers/providers.

### What the User Sees

A single-page dashboard with the following panels:

1. **NVDA Live Price** — Current price, daily change, mini-chart
2. **Polymarket Probability Heatmap** — Bar chart of implied probabilities by strike price from Polymarket binary prediction markets, showing max conviction, 50% expected level, and low conviction zones (replaces the original GEX Heatmap since FMP dropped options chain data)
3. **Supplementary Prediction Markets** — Non-price-level NVDA markets from Polymarket (earnings beat/miss, revenue targets, etc.)
4. **Earnings Consensus** — EPS estimates, revenue estimates, historical beat/miss record
5. **Sentiment Engine** — Twitter/X sentiment via SocialData.tools with keyword-based polarity scoring, engagement-weighted aggregation, rate-of-change, and mention volume spike detection
6. **Hyperscaler CapEx Proxy Indicator** — Bar chart of CapEx-to-Revenue ratios for MSFT, AMZN, GOOGL, META, plus an "AI Keyword Score" from earnings transcripts
7. **Predictions Panel** — Rule-based synthesis combining price action, Polymarket positioning, and Twitter/X sentiment trends into a qualitative outlook

---

## 2. DATA SOURCE

### Provider 1: Financial Modeling Prep (FMP)

- **Plan:** Starter ($19/month)
- **API Base URL:** `https://financialmodelingprep.com/stable/` (migrated from legacy `/api/v3/` and `/api/v4/` — deprecated August 2025)
- **Authentication:** Query parameter `?apikey=YOUR_API_KEY`
- **Rate Limits:** Exponential backoff on 429 responses, max 3 retries.

#### Active FMP Endpoints

| Endpoint | Purpose | Refresh Frequency |
|----------|---------|-------------------|
| `/stable/quote?symbol=NVDA` | Real-time price, change, volume | Every 5 seconds |
| `/stable/historical-price-eod/full?symbol=NVDA` | OHLCV for charting | On demand |
| `/stable/stock-price-change?symbol=NVDA` | Price performance periods | On demand |
| `/stable/news/stock?symbol=NVDA` | News articles | On demand |
| `/stable/cash-flow-statement?symbol=X` | Hyperscaler CapEx (MSFT, AMZN, GOOGL, META) | Daily |
| `/stable/income-statement?symbol=X` | Hyperscaler revenue | Daily |
| `/stable/analyst-estimates?symbol=NVDA` | EPS/revenue consensus (annual only) | Daily |
| `/stable/earnings-calendar` | Next earnings date | Daily |

#### Deprecated / Unavailable FMP Endpoints

| Former Endpoint | Status | Replacement |
|-----------------|--------|-------------|
| `/v3/stock/NVDA/options/chain` | Removed entirely | Polymarket probability heatmap |
| `/v4/social-sentiments?symbol=NVDA` | Removed | SocialData.tools Twitter/X search |
| `/v3/earnings-surprises/NVDA` | 404 on stable API | None (signal removed from predictions) |
| `/v3/earning_call_transcript/NVDA` | 402 (requires higher plan) | Stub returns None; engine exists but cannot be fed live data |
| `/v3/analyst-estimates (quarterly)` | 402 (requires higher plan) | Annual estimates only |

### Provider 2: Polymarket (Prediction Markets)

- **APIs:** Gamma API (`https://gamma-api.polymarket.com`) + CLOB API (`https://clob.polymarket.com`)
- **Authentication:** None required (public read-only APIs)
- **Usage:** Replaces the options chain / GEX heatmap. Binary YES/NO prediction markets for NVDA provide strike-level implied probabilities.

| Endpoint | Purpose | Refresh Frequency |
|----------|---------|-------------------|
| `GET /markets?_q=NVDA` (Gamma API) | Market discovery — search for NVDA markets | Every 30 seconds |
| `GET /midpoint?token_id=X` (CLOB API) | Real-time midpoint price for an outcome token | On demand |
| `GET /book?token_id=X` (CLOB API) | Order book depth for liquidity analysis | On demand |

### Provider 3: SocialData.tools (Twitter/X Search)

- **API Base URL:** `https://api.socialdata.tools`
- **Authentication:** Bearer token in Authorization header
- **Rate Limits:** 120 requests/minute
- **Usage:** Replaces FMP social sentiment. Searches Twitter/X for `$NVDA` tweets every 60 seconds.

| Endpoint | Purpose | Refresh Frequency |
|----------|---------|-------------------|
| `GET /twitter/search?query=$NVDA` | Latest tweets mentioning $NVDA | Every 60 seconds |

> **IMPORTANT:** FMP legacy endpoints (`/api/v3/`, `/api/v4/`) were deprecated in August 2025. All active FMP endpoints now use the `/stable/` base URL. The options chain endpoint was removed entirely — Polymarket is the replacement.

---

## 3. TECH STACK

### Backend

| Technology | Role |
|------------|------|
| **Python 3.11+** | Primary language for data fetching and computation |
| **FastAPI** | REST API server exposing computed metrics to the frontend |
| **APScheduler** | Background job scheduler for data refresh intervals |
| **Redis** (or in-memory dict for MVP) | Cache layer between FMP and frontend. Frontend never calls FMP directly. |
| **NumPy / SciPy** | Black-Scholes gamma calculations |
| **httpx** | Async HTTP client for FMP API calls |

### Frontend

| Technology | Role |
|------------|------|
| **React** (via Vite) | Single-page application framework |
| **TypeScript** | Type safety |
| **Tailwind CSS** | Styling — dark theme (trading terminal aesthetic) |
| **Lightweight Charts** (by TradingView) | NVDA price chart (candlestick + overlays) |
| **Recharts** | Bar charts (GEX heatmap, CapEx ratios), area charts (sentiment) |
| **Axios** or **fetch** | API client to hit our FastAPI backend |

### Deployment (MVP)

| Component | Platform |
|-----------|----------|
| Backend | Railway or Render (free/cheap tier) |
| Frontend | Vercel (free tier) |
| Domain | Optional for MVP — Vercel provides a subdomain |

### Project Structure

```
nvda-war-room/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # FMP API key, refresh intervals, constants
│   ├── scheduler.py             # APScheduler job definitions
│   ├── cache.py                 # In-memory cache (upgrade to Redis later)
│   ├── fmp_client.py            # FMP API wrapper (all HTTP calls to FMP)
│   ├── routes/
│   │   ├── price.py             # /api/price — NVDA quote + historical
│   │   ├── options.py           # /api/options — GEX data + unusual activity
│   │   ├── earnings.py          # /api/earnings — consensus, surprises, calendar
│   │   ├── sentiment.py         # /api/sentiment — processed sentiment data
│   │   ├── hyperscaler.py       # /api/hyperscaler — CapEx ratios + AI keyword scores
│   │   └── predictions.py       # /api/predictions — synthesized outlook
│   ├── engines/
│   │   ├── gex_engine.py        # Black-Scholes gamma calc, GEX aggregation
│   │   ├── unusual_activity.py  # Volume/OI ratio scanner
│   │   ├── sentiment_engine.py  # Rate-of-change, mention volume processing
│   │   ├── capex_engine.py      # CapEx-to-Revenue ratio calculator
│   │   └── transcript_nlp.py    # Keyword frequency analysis on earnings calls
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main layout — single page, grid of panels
│   │   ├── components/
│   │   │   ├── PricePanel.tsx       # Live price + mini candlestick chart
│   │   │   ├── GexHeatmap.tsx       # Gamma exposure bar chart
│   │   │   ├── UnusualActivity.tsx  # Options scanner table
│   │   │   ├── EarningsPanel.tsx    # Consensus + historical beat/miss
│   │   │   ├── SentimentPanel.tsx   # Sentiment gauge + rate of change
│   │   │   ├── HyperscalerPanel.tsx # CapEx bar chart + AI keyword scores
│   │   │   └── PredictionsPanel.tsx # Qualitative outlook summary
│   │   ├── hooks/
│   │   │   └── usePolling.ts    # Generic polling hook for auto-refresh
│   │   ├── api/
│   │   │   └── client.ts        # Axios/fetch wrapper for backend API
│   │   └── styles/
│   │       └── globals.css      # Tailwind config + dark theme overrides
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── landing/                     # Marketing landing page (Phase 4)
│   └── index.html
└── README.md
```

---

## 4. BUILD PHASES & TASK BREAKDOWN

### Phase 1: Foundation (Days 1–3)

**Goal:** Wire up FMP, prove every endpoint returns usable data, build the cache layer.

| Task ID | Task | Agent Scope | Acceptance Criteria |
|---------|------|-------------|---------------------|
| P1-01 | Create `backend/` scaffold with FastAPI, config, and FMP client | Backend | `uvicorn main:app` starts without errors |
| P1-02 | Implement `fmp_client.py` with methods for every endpoint listed in Section 2 | Backend | Each method returns parsed JSON; handles rate limits and errors gracefully |
| P1-03 | Build `cache.py` — in-memory dict with TTL per data type | Backend | Cache hit returns data without FMP call; expired entries trigger refresh |
| P1-04 | Write integration tests: call each FMP endpoint, validate response shape | Backend | All tests pass with a live API key; missing/gated endpoints are flagged |
| P1-05 | Create `frontend/` scaffold with Vite + React + TypeScript + Tailwind | Frontend | `npm run dev` serves a blank dark-themed page |

**Critical validation in Phase 1:**
- Confirm the options chain endpoint returns ALL strikes and expirations (not just near-the-money)
- Confirm the social sentiment endpoint returns data for NVDA specifically
- Confirm cash flow statements for MSFT, AMZN, GOOGL, META include a `capitalExpenditure` field
- Confirm earnings transcript endpoint returns full text, not just metadata
- Document any endpoints that don't work on the Starter plan

---

### Phase 2: Calculation Engines (Days 4–7)

**Goal:** Build all derived-metric engines as standalone, testable Python modules.

| Task ID | Task | Agent Scope | Details |
|---------|------|-------------|---------|
| P2-01 | `gex_engine.py` — GEX Calculator | Backend | See Section 5.1 for full spec |
| P2-02 | `unusual_activity.py` — Options Scanner | Backend | See Section 5.2 for full spec |
| P2-03 | `sentiment_engine.py` — Sentiment Processor | Backend | See Section 5.3 for full spec |
| P2-04 | `capex_engine.py` — CapEx Ratio Calculator | Backend | See Section 5.4 for full spec |
| P2-05 | `transcript_nlp.py` — Transcript Keyword Analyzer | Backend | See Section 5.5 for full spec |
| P2-06 | Wire all engines into FastAPI routes with scheduler | Backend | Each `/api/*` route returns JSON; scheduler refreshes cache on intervals from Section 2 |

---

### Phase 3: Frontend Dashboard (Days 8–14)

**Goal:** Build the single-page war room UI.

| Task ID | Task | Agent Scope | Details |
|---------|------|-------------|---------|
| P3-01 | `App.tsx` — Main grid layout (responsive, dark theme) | Frontend | CSS grid, 2–3 columns on desktop, stacked on mobile |
| P3-02 | `PricePanel.tsx` — Live NVDA price with candlestick chart | Frontend | Use Lightweight Charts; auto-refresh via polling hook; show price, change %, volume |
| P3-03 | `GexHeatmap.tsx` — Gamma exposure bar chart | Frontend | Recharts horizontal bar chart; highlight gamma flip level; color-code positive/negative gamma |
| P3-04 | `UnusualActivity.tsx` — Scanner table | Frontend | Sortable table; columns: Strike, Expiry, Type (Call/Put), Volume, OI, Vol/OI Ratio; highlight rows above threshold |
| P3-05 | `EarningsPanel.tsx` — Consensus display | Frontend | Show EPS estimate vs actual (last 8 quarters), revenue estimate, countdown to next earnings date |
| P3-06 | `SentimentPanel.tsx` — Sentiment gauge | Frontend | Area chart of sentiment over time; show rate-of-change arrow; mention volume bar |
| P3-07 | `HyperscalerPanel.tsx` — CapEx tracker | Frontend | Grouped bar chart (CapEx-to-Revenue by company by quarter); secondary display: AI keyword score table |
| P3-08 | `PredictionsPanel.tsx` — Outlook summary | Frontend | Text-based panel; bullish/bearish/neutral indicator; key factors list |
| P3-09 | `usePolling.ts` — Generic polling hook | Frontend | Configurable interval; pause when tab not visible; error retry with backoff |
| P3-10 | Global error states + loading skeletons | Frontend | Every panel shows a skeleton loader on first load; shows last-updated timestamp; handles backend errors gracefully |

---

### Phase 4: Polish & Launch (Days 15–18)

| Task ID | Task | Agent Scope |
|---------|------|-------------|
| P4-01 | Data delay disclaimer banner at top of dashboard | Frontend |
| P4-02 | Landing/marketing page (separate from dashboard) | Frontend |
| P4-03 | Mobile responsiveness pass | Frontend |
| P4-04 | Error handling hardening (FMP downtime, empty data, etc.) | Full stack |
| P4-05 | Deploy backend to Railway/Render | DevOps |
| P4-06 | Deploy frontend to Vercel | DevOps |
| P4-07 | Environment variable setup (FMP API key, backend URL) | DevOps |

---

## 5. ENGINE SPECIFICATIONS

These are the detailed specs for each calculation engine. Subagents building these modules must follow these specifications exactly.

### 5.1 GEX Engine (`gex_engine.py`)

**Purpose:** Calculate Gamma Exposure (GEX) across all option strikes to identify the "gamma flip" level and key volatility triggers.

**Input:** Raw options chain from FMP (all strikes, all expirations for NVDA)

**Algorithm:**
1. For each option contract in the chain:
   - Extract: strike price, expiration date, option type (call/put), open interest, implied volatility (if available from FMP; otherwise calculate from mid-price using bisection method)
   - Calculate **time to expiration** (T) in years
   - Calculate **Gamma** using the Black-Scholes formula:
     ```
     d1 = (ln(S/K) + (r + σ²/2) * T) / (σ * √T)
     Gamma = N'(d1) / (S * σ * √T)
     ```
     Where: S = current NVDA price, K = strike, r = risk-free rate (use 10Y Treasury, default 4.5%), σ = implied volatility, N'(x) = standard normal PDF
2. Calculate **GEX per strike:**
   ```
   GEX_call = Gamma * OI * 100 * S²  (calls contribute positive gamma)
   GEX_put  = Gamma * OI * 100 * S² * (-1)  (puts contribute negative gamma — dealers are short puts)
   Net_GEX_at_strike = GEX_call + GEX_put
   ```
3. Aggregate across all expirations for the same strike
4. The **Gamma Flip** is the strike where Net GEX crosses from negative to positive

**Output JSON:**
```json
{
  "current_price": 950.25,
  "gamma_flip": 940.0,
  "total_gex": 1250000000,
  "strikes": [
    { "strike": 900, "call_gex": 500000, "put_gex": -800000, "net_gex": -300000 },
    { "strike": 910, "call_gex": 600000, "put_gex": -700000, "net_gex": -100000 }
  ],
  "key_levels": {
    "max_positive_gex": 980,
    "max_negative_gex": 920,
    "gamma_flip": 940
  },
  "last_updated": "2026-02-23T15:30:00Z"
}
```

**Edge cases:**
- If implied volatility is not provided by FMP, calculate it from the option mid-price using the bisection method (not Newton's — more stable for edge cases)
- If T <= 0 (expired options), skip the contract
- If OI = 0, skip the contract
- Use the risk-free rate of 4.5% as default; make it configurable in `config.py`

---

### 5.2 Unusual Activity Scanner (`unusual_activity.py`)

**Purpose:** Identify options strikes with abnormally high volume relative to open interest.

**Algorithm:**
1. For each contract: calculate `vol_oi_ratio = volume / open_interest`
2. Flag as "unusual" if `vol_oi_ratio > 2.0` AND `volume > 1000` (minimum volume filter to avoid noise)
3. Sort by `vol_oi_ratio` descending
4. Return top 20 results

**Output JSON:**
```json
{
  "unusual_activity": [
    {
      "strike": 960,
      "expiration": "2026-03-07",
      "type": "CALL",
      "volume": 15420,
      "open_interest": 3200,
      "vol_oi_ratio": 4.82,
      "implied_volatility": 0.65,
      "last_price": 12.50
    }
  ],
  "total_unusual_contracts": 47,
  "put_call_ratio_unusual": 0.35,
  "last_updated": "2026-02-23T15:30:00Z"
}
```

---

### 5.3 Sentiment Engine (`sentiment_engine.py`)

**Purpose:** Process raw sentiment data into actionable signals.

**Input:** FMP social sentiment data (timestamped sentiment scores and mention counts)

**Processing:**
1. Fetch the last 7 days of sentiment data
2. Calculate **rolling 24-hour average sentiment** (smooths noise)
3. Calculate **rate of change:** `sentiment_roc = (avg_today - avg_yesterday) / abs(avg_yesterday)` — this is the key signal (is bullishness accelerating or decelerating?)
4. Calculate **mention volume spike:** compare today's mention count to 7-day average. Flag if > 2x average.
5. Composite score: combine normalized sentiment + ROC + volume spike into a single -100 to +100 score

**Output JSON:**
```json
{
  "current_score": 72,
  "sentiment_label": "Bullish",
  "rate_of_change": 0.15,
  "roc_direction": "accelerating",
  "mention_volume_today": 4520,
  "mention_volume_7d_avg": 2100,
  "volume_spike": true,
  "history": [
    { "date": "2026-02-22", "score": 65, "mentions": 3800 },
    { "date": "2026-02-21", "score": 58, "mentions": 2200 }
  ],
  "last_updated": "2026-02-23T15:30:00Z"
}
```

---

### 5.4 CapEx Engine (`capex_engine.py`)

**Purpose:** Track the capital expenditure trends of NVDA's biggest customers (hyperscalers) as a proxy for NVDA revenue demand.

**Companies:** MSFT, AMZN, GOOGL, META

**Algorithm:**
1. For each company, fetch the last 8 quarters of cash flow statements from FMP
2. Extract `capitalExpenditure` and `revenue` (from income statement)
3. Calculate `capex_to_revenue_ratio = abs(capitalExpenditure) / revenue` (CapEx is often reported as negative in cash flow statements — use absolute value)
4. Calculate quarter-over-quarter growth rate of CapEx

**Output JSON:**
```json
{
  "companies": [
    {
      "symbol": "MSFT",
      "name": "Microsoft",
      "quarters": [
        { "period": "Q3 2025", "capex": 14200000000, "revenue": 65600000000, "capex_to_revenue": 0.216, "capex_qoq_growth": 0.12 },
        { "period": "Q2 2025", "capex": 12700000000, "revenue": 62000000000, "capex_to_revenue": 0.205, "capex_qoq_growth": 0.08 }
      ]
    }
  ],
  "aggregate_trend": "increasing",
  "last_updated": "2026-02-23T15:30:00Z"
}
```

**Note:** This data is quarterly. Between earnings seasons, this panel will show the same data. That is expected and acceptable for an MVP.

---

### 5.5 Transcript NLP Engine (`transcript_nlp.py`)

**Purpose:** Analyze earnings call transcripts for AI-related keyword frequency as a qualitative sentiment indicator.

**Keywords to track:**
- Hardware-specific: `"H100"`, `"H200"`, `"B100"`, `"B200"`, `"Blackwell"`, `"Hopper"`, `"Grace"`, `"DGX"`, `"HGX"`, `"NVLink"`
- Category terms: `"GPU"`, `"accelerator"`, `"data center"`, `"AI infrastructure"`, `"AI training"`, `"AI inference"`, `"compute spend"`, `"compute capacity"`, `"AI workload"`

**Algorithm:**
1. Fetch the last 4 transcripts for each hyperscaler (MSFT, AMZN, GOOGL, META) + NVDA itself
2. Case-insensitive keyword search
3. Count occurrences per keyword per transcript
4. Calculate total "AI Keyword Score" = sum of all keyword mentions per transcript
5. Track quarter-over-quarter trend of the total score

**Output JSON:**
```json
{
  "transcripts": [
    {
      "symbol": "MSFT",
      "quarter": "Q3 2025",
      "total_ai_score": 47,
      "top_keywords": [
        { "keyword": "AI infrastructure", "count": 12 },
        { "keyword": "GPU", "count": 9 },
        { "keyword": "Blackwell", "count": 7 }
      ]
    }
  ],
  "trend": "increasing",
  "last_updated": "2026-02-23T15:30:00Z"
}
```

---

## 6. DESIGN GUIDELINES

### Visual Identity

- **Theme:** Dark mode only (trading terminal aesthetic)
- **Background:** `#0a0a0f` (near-black with slight blue)
- **Card/Panel backgrounds:** `#12121a` with subtle `#1a1a2e` borders
- **Primary accent:** `#00ff88` (green — for positive/bullish)
- **Secondary accent:** `#ff4444` (red — for negative/bearish)
- **Tertiary accent:** `#4a9eff` (blue — for neutral/informational)
- **Text:** `#e0e0e0` (primary), `#888888` (secondary)
- **Font:** `Inter` or `JetBrains Mono` for numbers/data

### Layout

- CSS Grid: 3 columns on desktop (>=1280px), 2 columns on tablet (>=768px), 1 column on mobile
- Each panel is a card with consistent padding (24px), border radius (12px), and subtle border
- Price panel spans full width at the top
- Every panel shows a "Last updated: X seconds ago" timestamp in the bottom-right corner
- Global disclaimer bar at top: "Data may be delayed. Always verify with your broker."

---

## 7. ENVIRONMENT VARIABLES

```env
# Backend
FMP_API_KEY=your_fmp_api_key_here
FMP_BASE_URL=https://financialmodelingprep.com/api
RISK_FREE_RATE=0.045
CACHE_TTL_PRICE=5
CACHE_TTL_OPTIONS=60
CACHE_TTL_SENTIMENT=900
CACHE_TTL_EARNINGS=86400
CACHE_TTL_HYPERSCALER=86400
SOCIALDATA_API_KEY=your_socialdata_api_key_here
CACHE_TTL_SOCIAL=60
CACHE_TTL_POLYMARKET=30

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## 8. IMPORTANT CONSTRAINTS & RULES FOR ALL AGENTS

1. **Never call FMP from the frontend.** All FMP calls go through the Python backend. The frontend only talks to our FastAPI backend.
2. **Always cache.** Every FMP response must be cached with an appropriate TTL. The cache is the first thing checked on any request.
3. **Graceful degradation.** If any single FMP endpoint fails or returns empty data, that panel shows "Data temporarily unavailable" — it must never crash the entire dashboard.
4. **No hardcoded data.** Everything must come from FMP or be computed from FMP data. No mock data in production.
5. **Type everything.** Backend: use Pydantic models for all API responses. Frontend: use TypeScript interfaces for all data shapes.
6. **Error logging.** All FMP errors and unexpected response shapes must be logged with full context.
7. **Rate limit awareness.** Implement exponential backoff on FMP 429 responses. Never retry more than 3 times.
8. **The FMP API key must never appear in frontend code, git commits, or logs.**

---

## 9. GLOSSARY

| Term | Definition |
|------|-----------|
| **GEX** | Gamma Exposure — the aggregate gamma across all option strikes, indicating where market makers need to hedge |
| **Gamma Flip** | The price level where net GEX crosses from negative to positive; above this level, market makers dampen volatility; below it, they amplify it |
| **Vol/OI Ratio** | Volume divided by Open Interest — a high ratio suggests new positioning, not just existing positions rolling |
| **CapEx** | Capital Expenditure — money spent on infrastructure; hyperscaler CapEx is a leading indicator of GPU demand |
| **FMP** | Financial Modeling Prep — our sole market data provider |
| **Hyperscaler** | Large cloud providers (MSFT, AMZN, GOOGL, META) who are NVDA's biggest data center customers |
| **Polymarket** | Decentralized prediction market platform. Binary YES/NO markets provide implied probabilities for NVDA price levels |
| **SocialData.tools** | Third-party API providing Twitter/X search access. Used for social sentiment analysis |
| **Probability Heatmap** | Visual representation of implied probabilities at different NVDA price strikes, derived from Polymarket prediction markets |

---

## 10. RESOLVED QUESTIONS (Phase 1–2.5)

- **Options chain:** FMP dropped this endpoint entirely from the stable API. **Resolution:** Replaced with Polymarket probability heatmap.
- **Social sentiment:** FMP removed the `/v4/social-sentiments` endpoint. **Resolution:** Replaced with SocialData.tools Twitter/X search.
- **Earnings surprises:** FMP returns 404 for per-symbol surprises on stable API. **Resolution:** Signal removed from predictions engine.
- **Earnings transcripts:** FMP returns 402 (requires higher plan). **Resolution:** Engine exists but runs with empty data. Upgrade FMP plan or find alternative provider to enable.
- **Quarterly analyst estimates:** FMP returns 402. **Resolution:** Annual estimates only.
- **Rate limits:** FMP stable API returns 429 on rate limit. Backend implements exponential backoff with 3 retries.
- **Implied volatility:** FMP did provide IV per contract, but options chain is now unavailable. Bisection method in gex_engine.py exists but has no live data feed.

---

*Last updated: February 24, 2026*
*Version: 1.1 — Post-Data-Migration*