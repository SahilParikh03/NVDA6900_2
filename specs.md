# NVDA Index — Product Specification

> **Version:** 3.0 — Stage 7 Animation Polish
> **Date:** February 24, 2026
> **Status:** Backend complete. Frontend Stages 0–6 complete. Stage 7 (animation polish) in progress.

---

## 1. PRODUCT IDENTITY

**Name:** NVDA Index
**Concept:** The only screen you need open when NVIDIA drops earnings — a premium real-time command center that visualizes the entire AI ecosystem reacting in real-time.

**Tagline energy:** *"The entire AI bubble on one screen."*

NVIDIA is the proxy for the AI trade. When NVDA moves, AMD, INTC, GOOGL, MSFT, AAPL, AMZN, META, TSM, Samsung, and BTC all move. NVDA Index gives traders a single premium dashboard to watch it all unfold — live prices, prediction markets, Twitter/X sentiment, hyperscaler CapEx trends, and a synthesized outlook.

---

## 2. CURRENT PROJECT STATE

| Phase | Status | Details |
|-------|--------|---------|
| **Phase 1: Foundation** | ✅ Complete | Config, cache, FMP/Polymarket/SocialData clients, FastAPI skeleton, scheduler, frontend scaffold |
| **Phase 2: Engines** | ✅ Complete | GEX, unusual activity, sentiment, CapEx, transcript NLP, Polymarket engine, all API routes (15 endpoints) |
| **Phase 3: Frontend (Stages 0–6)** | ✅ Complete | Design system, shared components, all 5 tabs built with 16 panels, typed API client, polling hooks |
| **Phase 3: Frontend (Stage 7)** | 🔧 In Progress | Animation polish, alert system wiring, tab transitions |
| **Phase 4: Polish** | ❌ Not started | Landing page, responsive pass, deploy config |

**Backend:** 3000+ lines of production Python, 130+ passing tests, 6 engines, 15 API endpoints, 3 data sources integrated.
**Frontend:** 35 TypeScript/TSX files, 5 tabs, 16 data panels, 6 shared UI components, typed API client with 14 fetch functions. All building and type-checking cleanly. Stage 7 animation polish remains.

---

## 3. ARCHITECTURE

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                     │
│                                                              │
│   FMP (Starter)          Polymarket           SocialData     │
│   /stable/ endpoints     Gamma + CLOB APIs    Twitter/X API  │
│   Price, financials,     Prediction markets    $NVDA tweets   │
│   estimates, news        No auth required      Bearer auth    │
└──────────┬─────────────────────┬──────────────────┬──────────┘
           │                     │                  │
           ▼                     ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    PYTHON BACKEND (FastAPI)                   │
│                                                              │
│   ┌─────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│   │  Cache   │◄──│  Scheduler   │──▶│  API Clients        │  │
│   │  (TTL)   │   │  (5 tasks)   │   │  FMP / Polymarket / │  │
│   └────┬─────┘   └──────────────┘   │  SocialData         │  │
│        │                             └─────────────────────┘  │
│        ▼                                                      │
│   ┌──────────────────────────────────────────┐               │
│   │  ENGINES                                  │               │
│   │  GEX · Unusual Activity · Sentiment       │               │
│   │  CapEx · Transcript NLP · Polymarket      │               │
│   └──────────────────────────────────────────┘               │
│        │                                                      │
│        ▼                                                      │
│   ┌──────────────────────────────────────────┐               │
│   │  ROUTES (15 endpoints)                    │               │
│   │  /api/price · /api/options · /api/earnings│               │
│   │  /api/sentiment · /api/hyperscaler        │               │
│   │  /api/predictions                         │               │
│   └──────────────────────────────────────────┘               │
└──────────────────────────┬───────────────────────────────────┘
                           │
                     HTTP JSON responses
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    REACT FRONTEND                             │
│                                                              │
│   Tab Navigation ──▶ Component Panels ──▶ usePolling hooks   │
│                                                              │
│   Frontend NEVER calls external APIs directly.               │
│   All data flows through the FastAPI backend.                │
└─────────────────────────────────────────────────────────────┘
```

### Backend API Endpoints (All Built)

| Route | Method | Endpoint | Returns |
|-------|--------|----------|---------|
| Price | GET | `/api/price/` | NVDA quote (price, change, volume) |
| Price | GET | `/api/price/history` | Historical OHLCV for charting |
| Price | GET | `/api/price/change` | Price performance periods |
| Options | GET | `/api/options/heatmap` | Polymarket probability heatmap by strike |
| Options | GET | `/api/options/supplementary` | Non-price Polymarket markets (beat/miss, revenue) |
| Earnings | GET | `/api/earnings/` | Consolidated earnings data |
| Earnings | GET | `/api/earnings/calendar` | Next earnings date |
| Earnings | GET | `/api/earnings/estimates` | Analyst EPS/revenue estimates |
| Earnings | GET | `/api/earnings/surprises` | Historical beat/miss (may 404) |
| Sentiment | GET | `/api/sentiment/` | Processed Twitter/X sentiment scores |
| Sentiment | GET | `/api/sentiment/news` | Recent NVDA news articles |
| Hyperscaler | GET | `/api/hyperscaler/capex` | CapEx-to-revenue ratios (MSFT, AMZN, GOOGL, META) |
| Hyperscaler | GET | `/api/hyperscaler/transcripts` | AI keyword frequency from earnings transcripts |
| Predictions | GET | `/api/predictions/` | Rule-based bull/bear/neutral synthesis |

### Refresh Intervals

| Data | Cache TTL | Scheduler Interval |
|------|-----------|-------------------|
| NVDA Price | 5s | 5s |
| Polymarket | 30s | 30s |
| Twitter/X Sentiment | 60s | 60s |
| Earnings | 86400s | Daily |
| Hyperscaler CapEx | 86400s | Daily |

---

## 4. DESIGN SYSTEM — "NVDA INDEX"

### Aesthetic Direction

**Premium Sci-Fi HUD + Glassmorphism.** Not a generic dark dashboard. Not Bloomberg. Not AI slop. This is a holographic command center — frosted glass panels floating over a dark mesh, NVIDIA green edge-lighting, data that feels alive. The aesthetic of looking at a holographic display in a high-end trading operations room.

### Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--base` | `#0A0A0F` | Deep near-black background |
| `--surface` | `rgba(255,255,255,0.04)` | Glass panel fill |
| `--surface-hover` | `rgba(255,255,255,0.07)` | Glass panel hover state |
| `--nvda-green` | `#76B900` | Primary accent — NVIDIA brand green |
| `--green-glow` | `rgba(118,185,0,0.25)` | Edge lighting, hover halos, subtle pulses |
| `--green-dim` | `rgba(118,185,0,0.12)` | Borders, dividers, inactive states |
| `--red` | `#FF3B3B` | Negative deltas, bearish signals |
| `--amber` | `#FFB800` | Warnings, neutral/volatile state |
| `--text-primary` | `#E8E8EC` | Main text |
| `--text-muted` | `#6B6B7B` | Labels, secondary info, timestamps |
| `--border` | `rgba(118,185,0,0.10)` | Default panel borders |
| `--border-hover` | `rgba(118,185,0,0.25)` | Hover/active panel borders |

### Glass System

Every panel uses a consistent glass treatment:

```css
.glass-panel {
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(118, 185, 0, 0.10);
  border-radius: 16px;
  box-shadow:
    0 0 0 1px rgba(118, 185, 0, 0.05) inset,
    0 8px 32px rgba(0, 0, 0, 0.4);
}

.glass-panel:hover {
  border-color: rgba(118, 185, 0, 0.25);
  box-shadow:
    0 0 0 1px rgba(118, 185, 0, 0.08) inset,
    0 0 20px rgba(118, 185, 0, 0.06),
    0 8px 32px rgba(0, 0, 0, 0.4);
}
```

Panels layer at 2-3 depth levels. Inner cards within panels use slightly different opacity. The effect is holographic depth — panels floating in space.

### Typography

| Role | Font | Usage |
|------|------|-------|
| Display / Headings | **Orbitron** or **Rajdhani** (geometric, techy, distinctive) | Tab labels, panel titles, hero price |
| Body | **Geist Sans** or **Exo 2** (clean, high-legibility, futuristic lean) | Descriptions, labels, paragraph text |
| Data / Monospace | **JetBrains Mono** | All prices, percentages, timestamps, ticker symbols |

**Hard rule:** No Inter, Roboto, Arial, Space Grotesk, or system fonts anywhere.

### Motion & Interaction

| Trigger | Effect | Duration |
|---------|--------|----------|
| Page load | Staggered panel reveal — scale(0.97) + opacity:0 → scale(1) + opacity:1 | 400ms per panel, 80ms stagger |
| Price tick | Number briefly flashes green (up) or red (down), then settles | 600ms |
| Alert | Slides in from right edge — frosted glass pill with colored left border | 300ms in, 5s visible, 300ms out |
| Hover (panel) | Border brightens, faint green glow blooms outward | 200ms ease |
| Tab switch | Smooth crossfade between tab contents | 250ms |
| Data loading | Skeleton shimmer with green-tinted gradient | Continuous until loaded |

### Background & Atmosphere

- Base: `#0A0A0F` solid
- Overlay: CSS grid pattern — very faint green gridlines (`rgba(118,185,0,0.03)`) creating a subtle mesh
- Optional: grain/noise texture at 2-3% opacity for depth
- The background should feel like a dark room with faint holographic grid lines — not flat, not busy

### Alert Banners

Slide-in notifications for significant price moves:

```
┌──────────────────────────────────────┐
│ ▌ ▲ AMD GAPPED UP 2.3%    12:04 PM  │
└──────────────────────────────────────┘
```

- Green left border for positive, red for negative
- Frosted glass background
- Auto-dismiss after 5 seconds
- Stack vertically if multiple alerts fire simultaneously

### Anti-Patterns (NEVER)

- Inter, Roboto, Arial, system fonts
- Purple gradients on white backgrounds
- Generic card layouts with no character
- Cookie-cutter component patterns
- Flat solid-color backgrounds with no texture/depth
- The overused green-on-black terminal look without the glass/premium layer
- `#00ff88` neon green (too terminal-y; use NVIDIA brand `#76B900`)

---

## 5. TAB STRUCTURE & COMPONENT SPECIFICATIONS

### Navigation

Horizontal tab bar at the top of the viewport. Tabs have:
- Glass treatment matching the overall system
- Active tab: solid NVIDIA green bottom-border + slightly brighter text
- Hover: subtle green glow
- Icons optional but should be minimal/geometric if used

### Tab 1: NVDA Command (Main Hub)

The first thing users see. The nerve center.

**Components:**

#### 1a. Hero Price Display
- NVDA ticker symbol + current price in large display font (Orbitron/Rajdhani)
- Price in monospace (JetBrains Mono), large — this is the centerpiece
- Daily change ($) and change (%) with green/red coloring
- 24h volume
- Mini candlestick chart (TradingView Lightweight Charts) — last 30 days
- "Last updated: Xs ago" timestamp
- **Data:** `GET /api/price/` (5s poll), `GET /api/price/history`

#### 1b. Earnings Countdown
- Days / Hours / Minutes / Seconds until next NVDA earnings
- Glass card with prominent countdown numbers
- If earnings already passed, show "Last reported: [date]" with beat/miss result
- **Data:** `GET /api/earnings/calendar`

#### 1c. Predictions Panel
- Rule-based synthesis output: BULLISH / BEARISH / NEUTRAL
- Confidence level (high/medium/low)
- Key factors list (which signals are driving the call)
- Prominent placement — this is the "so what?" answer
- **Data:** `GET /api/predictions/`

#### 1d. Correlated Tickers Mini-Grid
- Small cards for each tracked ticker: GOOGL, MSFT, AAPL, AMZN, META, AMD, INTC, TSM, BTC
- Each card shows: ticker, current price, daily change %
- Color-coded: green if up, red if down
- Compact — one glance to see if the AI ecosystem is moving together
- **Data:** `GET /api/price/` with multiple symbols (or extend endpoint)

#### 1e. Live Alert Feed
- Vertical stack of recent alert banners
- Shows significant price moves across all tracked tickers
- "AMZN UP 1.8%" / "BTC DOWN 3.2%" etc.
- Auto-scrolling, most recent on top
- Max 10 visible, older ones fade out

### Tab 2: Probability & Flow

Polymarket prediction market data — the replacement for traditional options GEX.

#### 2a. Probability Heatmap
- Horizontal bar chart of implied probabilities by strike price
- Derived from Polymarket binary YES/NO markets
- Highlight: max conviction zone, 50% expected level, low conviction zones
- Color intensity maps to probability (brighter green = higher probability)
- **Data:** `GET /api/options/heatmap` (30s poll)

#### 2b. Supplementary Markets
- Non-price-level Polymarket markets for NVDA
- Examples: "Will NVDA beat earnings?", "NVDA revenue above $40B?"
- Card layout showing market question + YES probability + liquidity
- **Data:** `GET /api/options/supplementary` (30s poll)

### Tab 3: AI Ecosystem

The "ripple effect" view — how every AI-adjacent ticker moves when NVDA moves.

#### 3a. Multi-Ticker Dashboard
- Full-size cards for each ticker: NVDA, GOOGL, MSFT, AAPL, AMZN, META, AMD, INTC, TSM, Samsung, BTC
- Each card: price, daily change $, daily change %, mini sparkline
- Sorted by correlation to NVDA or by sector grouping
- Glass cards with color-coded borders (green if up, red if down)
- **Data:** `GET /api/price/` per ticker (5s poll for NVDA, 30s for others)

#### 3b. Performance Comparison
- Period performance table: 1D, 5D, 1M, 3M, YTD
- All tickers side by side
- Heat-mapped cells (deeper green = better performance, deeper red = worse)
- **Data:** `GET /api/price/change` per ticker

### Tab 4: Intelligence

Deep analysis — sentiment, CapEx, earnings, transcript NLP.

#### 4a. Sentiment Engine
- Current sentiment score (-100 to +100) with visual gauge
- Sentiment label: Bullish / Bearish / Neutral
- Rate of change indicator (accelerating / decelerating)
- Mention volume vs 7-day average (spike detection)
- Historical sentiment chart (area chart, last 7 days)
- **Data:** `GET /api/sentiment/` (60s poll)

#### 4b. Earnings Consensus
- EPS estimate (annual — quarterly requires higher FMP plan)
- Revenue estimate
- Historical beat/miss record (last available quarters)
- Next earnings date
- **Data:** `GET /api/earnings/`, `GET /api/earnings/estimates`

#### 4c. Hyperscaler CapEx Tracker
- Grouped bar chart: CapEx-to-Revenue ratio by company (MSFT, AMZN, GOOGL, META) by quarter
- QoQ growth rates
- Aggregate trend indicator (increasing/decreasing/stable)
- **Data:** `GET /api/hyperscaler/capex`

#### 4d. AI Keyword Scores
- Table: company × quarter → total AI keyword score
- Top keywords per transcript
- QoQ trend
- **Data:** `GET /api/hyperscaler/transcripts`

### Tab 5: Live Feed

Real-time social and prediction market stream.

#### 5a. Twitter/X Feed
- Live tweet cards for `$NVDA`, `$GOOGL`, `$MSFT`, and other tracked tickers
- Each tweet shows: author, text, timestamp, engagement metrics
- Sentiment-tagged (positive/negative/neutral indicator per tweet)
- Chronological, auto-updating
- **Data:** `GET /api/sentiment/` (raw tweets if exposed) or new endpoint

#### 5b. Polymarket Live Odds
- Real-time probability changes for active NVDA markets
- Show delta from last update ("NVDA > $150: 72% → 74% ▲")
- **Data:** `GET /api/options/heatmap`, `GET /api/options/supplementary`

#### 5c. News Feed
- Recent NVDA news articles from FMP
- Headline, source, timestamp, link
- **Data:** `GET /api/sentiment/news`

---

## 6. SHARED COMPONENTS

These components are used across multiple tabs:

| Component | Purpose |
|-----------|---------|
| `GlassPanel` | Base container with glass styling, hover effects, consistent padding |
| `TickerCard` | Compact price display card (ticker, price, change, sparkline) |
| `AlertBanner` | Slide-in notification pill for price alerts |
| `LoadingSkeleton` | Green-tinted shimmer placeholder for loading states |
| `ErrorState` | "Data temporarily unavailable" with retry button |
| `LastUpdated` | Timestamp badge showing data freshness |
| `TabNav` | Top navigation bar with glass treatment |
| `CountdownTimer` | Earnings countdown display |

---

## 7. TICKERS TRACKED

| Ticker | Category | Polling Interval |
|--------|----------|-----------------|
| NVDA | Primary | 5s |
| GOOGL | Hyperscaler | 30s |
| MSFT | Hyperscaler | 30s |
| AAPL | Hyperscaler | 30s |
| AMZN | Hyperscaler | 30s |
| META | Hyperscaler | 30s |
| AMD | Semiconductor | 30s |
| INTC | Semiconductor | 30s |
| TSM | Manufacturing | 30s |
| Samsung (005930.KS) | Manufacturing | 60s |
| BTC-USD | Crypto | 30s |

---

## 8. GRACEFUL DEGRADATION

Every panel must handle failure independently. If one data source is down, only that panel shows an error state — all other panels continue working.

| Failure Scenario | Behavior |
|------------------|----------|
| FMP down | Price panels show last cached data + "stale" badge; other panels unaffected |
| Polymarket down | Probability tab shows error state; predictions run on remaining signals |
| SocialData down | Sentiment shows error state; predictions exclude sentiment signal |
| Single endpoint 404 | That specific panel shows "Data unavailable"; all others work |
| Rate limited (429) | Backend retries with exponential backoff (1s/2s/4s, max 3); panel shows last cached data |
| Empty response | Panel shows "No data available" with muted styling |

---

## 9. ENVIRONMENT VARIABLES

### Backend (.env)
```
FMP_API_KEY=<key>
FMP_BASE_URL=https://financialmodelingprep.com/api
RISK_FREE_RATE=0.045
CACHE_TTL_PRICE=5
CACHE_TTL_OPTIONS=60
CACHE_TTL_SENTIMENT=900
CACHE_TTL_EARNINGS=86400
CACHE_TTL_HYPERSCALER=86400
SOCIALDATA_API_KEY=<key>
CACHE_TTL_SOCIAL=60
CACHE_TTL_POLYMARKET=30
```

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## 10. TECH STACK

### Backend (Complete)
- Python 3.11+ / FastAPI / APScheduler
- httpx (async HTTP) / Pydantic v2 / NumPy + SciPy
- In-memory TTL cache

### Frontend (Stages 0–6 Complete, Stage 7 In Progress)
- React 18 / Vite 5 / TypeScript (strict) — zero type errors
- Tailwind CSS with custom NVDA6900 design tokens (glass system, NVIDIA green palette)
- TradingView Lightweight Charts (candlestick chart in HeroPrice)
- Recharts (bar charts, area charts, heatmaps across multiple panels)
- Axios (typed API client with 14 fetch functions)
- CSS animations (fadeIn, slideIn, shimmer, glowPulse, priceTick, crossfade) — no Framer Motion needed
- Google Fonts (Orbitron + Exo 2 + JetBrains Mono)

---

*End of specification.*
