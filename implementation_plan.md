# NVDA Index — Implementation Plan

> **Date:** February 24, 2026
> **Scope:** Phase 3 (Frontend Build) + Phase 4 (Polish & Deploy)
> **Prerequisite:** Backend is complete. All 15 API endpoints are live.

---

## PHASE 3: FRONTEND BUILD

### Stage 0: Design System Foundation

Before any component work, the Tailwind config, global styles, and base fonts must be updated to match the NVDA Index aesthetic. The current scaffold uses generic defaults (Inter, #00ff88 green, basic cards) — all of this gets replaced.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F0-01 | **Update Tailwind config with NVDA Index design tokens** | `frontend/tailwind.config.js` | — | Replace color palette (#76B900 system), add glass utilities, configure custom fonts (Orbitron, Exo 2, JetBrains Mono), add animation keyframes (fadeIn, slideIn, shimmer, glow-pulse) |
| F0-02 | **Update global CSS with glass system + background** | `frontend/src/styles/globals.css` | F0-01 | Add @font-face / Google Fonts imports, CSS custom properties for color tokens, glass-panel base class, grid background pattern, grain overlay, scrollbar styling, animation utilities |
| F0-03 | **Update index.html with font preloads** | `frontend/index.html` | F0-01 | Preconnect to Google Fonts, preload critical font files, update meta tags (title: "NVDA Index", description, OG tags) |

**Deliverable:** Running `npm run dev` shows the dark mesh background with correct fonts loading. No components yet — just the atmosphere.

---

### Stage 1: Shared Components & Layout Shell

Build the reusable atoms and the app-level layout (tab navigation, content area) before any data panels.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F1-01 | **GlassPanel component** | `frontend/src/components/ui/GlassPanel.tsx` | F0-02 | Reusable container: glass background, border, hover glow, padding variants (sm/md/lg), optional title prop, optional className override |
| F1-02 | **LoadingSkeleton component** | `frontend/src/components/ui/LoadingSkeleton.tsx` | F0-02 | Green-tinted shimmer effect. Variants: line, card, chart (different aspect ratios). Uses CSS animation, not JS. |
| F1-03 | **ErrorState component** | `frontend/src/components/ui/ErrorState.tsx` | F1-01 | "Data temporarily unavailable" message inside a GlassPanel. Optional retry callback. Matches glass aesthetic. |
| F1-04 | **LastUpdated component** | `frontend/src/components/ui/LastUpdated.tsx` | F0-02 | Small timestamp badge: "Updated 3s ago". Relative time formatting. Muted text styling. |
| F1-05 | **AlertBanner component** | `frontend/src/components/ui/AlertBanner.tsx` | F0-02 | Slide-in notification pill. Green/red left border. Frosted glass background. Auto-dismiss after 5s. Stacking support for multiple simultaneous alerts. |
| F1-06 | **TabNav component** | `frontend/src/components/layout/TabNav.tsx` | F1-01 | Horizontal tab bar. Glass treatment. Active tab: green bottom-border + brighter text. Hover: subtle glow. 5 tabs defined. |
| F1-07 | **App layout shell** | `frontend/src/App.tsx` | F1-06 | Top bar (NVDA INDEX logo + TabNav + clock). Content area renders active tab. Alert overlay zone (top-right). Background mesh. Import all fonts. |
| F1-08 | **TypeScript interfaces for all API responses** | `frontend/src/types/api.ts` | — | Interfaces matching every backend Pydantic model: PriceData, PolymarketHeatmap, EarningsData, SentimentData, HyperscalerData, PredictionsData, NewsArticle, etc. |
| F1-09 | **Extend API client with typed fetch functions** | `frontend/src/api/client.ts` | F1-08 | Add typed functions: fetchPrice(), fetchHistory(), fetchHeatmap(), fetchSentiment(), fetchEarnings(), fetchCapex(), fetchTranscripts(), fetchPredictions(), fetchNews(). Each returns typed promise. |

**Deliverable:** App renders with the glass-mesh background, NVDA INDEX logo, 5 working tabs (switching content area), and all shared UI components available. No data panels yet.

---

### Stage 2: NVDA Command Tab (Main Hub)

The primary tab — what users see first. Hero price, predictions, correlated tickers, alerts.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F2-01 | **HeroPrice component** | `frontend/src/components/panels/HeroPrice.tsx` | F1-01, F1-04, F1-09 | Large NVDA price display (Orbitron font). Daily change $ and %. Volume. Price tick animation (flash green/red on change). Candlestick chart via Lightweight Charts (30-day history). Polls every 5s via usePolling. |
| F2-02 | **EarningsCountdown component** | `frontend/src/components/panels/EarningsCountdown.tsx` | F1-01, F1-09 | Days/hours/minutes/seconds countdown to next NVDA earnings. Large monospace numbers. Glass card. If past earnings, show "Last reported" + beat/miss. |
| F2-03 | **PredictionsPanel component** | `frontend/src/components/panels/PredictionsPanel.tsx` | F1-01, F1-09 | BULLISH/BEARISH/NEUTRAL badge with color. Confidence level. Key factors list. Prominent glass card. Updates on data refresh. |
| F2-04 | **TickerCard component** | `frontend/src/components/ui/TickerCard.tsx` | F1-01 | Compact card: ticker symbol, current price (monospace), daily change %, green/red border accent. Reusable for all tickers. |
| F2-05 | **CorrelatedTickers grid** | `frontend/src/components/panels/CorrelatedTickers.tsx` | F2-04, F1-09 | Grid of TickerCards for GOOGL, MSFT, AAPL, AMZN, META, AMD, INTC, TSM, BTC. Each polls at 30s. Compact layout — one glance. |
| F2-06 | **AlertFeed component** | `frontend/src/components/panels/AlertFeed.tsx` | F1-05 | Vertical stack of recent AlertBanners. Monitors all tickers for significant moves (>1% threshold). Auto-scrolling, max 10 visible. |
| F2-07 | **NVDACommandTab layout** | `frontend/src/components/tabs/NVDACommandTab.tsx` | F2-01 thru F2-06 | Compose all command tab components into a responsive grid. HeroPrice spans full width top. Predictions + Countdown side by side. CorrelatedTickers grid below. AlertFeed on the side or bottom. |

**Deliverable:** Main tab fully functional — live NVDA price, earnings countdown, predictions, correlated tickers updating in real-time, alert feed showing price moves.

---

### Stage 3: Probability & Flow Tab

Polymarket prediction market visualizations.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F3-01 | **ProbabilityHeatmap component** | `frontend/src/components/panels/ProbabilityHeatmap.tsx` | F1-01, F1-09 | Horizontal bar chart (Recharts) of implied probabilities by strike price. Color intensity = probability level. Highlight max conviction, 50% expected, low conviction zones. Green gradient color scale. Polls every 30s. |
| F3-02 | **SupplementaryMarkets component** | `frontend/src/components/panels/SupplementaryMarkets.tsx` | F1-01, F1-09 | Card layout for non-price Polymarket markets. Market question + YES probability + liquidity indicator. Glass cards. Polls every 30s. |
| F3-03 | **ProbabilityFlowTab layout** | `frontend/src/components/tabs/ProbabilityFlowTab.tsx` | F3-01, F3-02 | Compose heatmap (top, full width) + supplementary markets (below, card grid). |

**Deliverable:** Probability tab shows Polymarket strike-level probabilities as a visual heatmap plus supplementary market cards.

---

### Stage 4: AI Ecosystem Tab

Multi-ticker dashboard — the "ripple effect" view.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F4-01 | **TickerDashboard component** | `frontend/src/components/panels/TickerDashboard.tsx` | F2-04, F1-09 | Grid of full-size TickerCards for all 11 tickers. Each shows: price, change $, change %, mini sparkline (Recharts). Color-coded borders. Grouped by category (Hyperscaler / Semiconductor / Manufacturing / Crypto). Polls at appropriate intervals. |
| F4-02 | **PerformanceTable component** | `frontend/src/components/panels/PerformanceTable.tsx` | F1-01, F1-09 | Table: rows = tickers, columns = 1D, 5D, 1M, 3M, YTD. Heat-mapped cells (green-red gradient). Sortable columns. Glass panel container. |
| F4-03 | **EcosystemTab layout** | `frontend/src/components/tabs/EcosystemTab.tsx` | F4-01, F4-02 | TickerDashboard at top, PerformanceTable below. |

**Deliverable:** Ecosystem tab shows all 11 tickers with live prices and period performance comparison.

---

### Stage 5: Intelligence Tab

Deep analysis panels — sentiment, earnings, CapEx, NLP.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F5-01 | **SentimentPanel component** | `frontend/src/components/panels/SentimentPanel.tsx` | F1-01, F1-09 | Sentiment score gauge (-100 to +100). Label badge (Bullish/Bearish/Neutral). ROC arrow (accelerating/decelerating). Volume vs 7d avg. Historical area chart (Recharts, 7 days). Polls every 60s. |
| F5-02 | **EarningsConsensus component** | `frontend/src/components/panels/EarningsConsensus.tsx` | F1-01, F1-09 | EPS estimate display. Revenue estimate. Historical beat/miss record (visual: green checkmarks / red X). Annual data only (quarterly behind paywall). |
| F5-03 | **CapExTracker component** | `frontend/src/components/panels/CapExTracker.tsx` | F1-01, F1-09 | Grouped bar chart (Recharts): CapEx-to-Revenue by company by quarter. MSFT, AMZN, GOOGL, META. QoQ growth indicators. Aggregate trend badge. |
| F5-04 | **AIKeywordScores component** | `frontend/src/components/panels/AIKeywordScores.tsx` | F1-01, F1-09 | Table: company × quarter → AI keyword score. Top keywords per transcript. QoQ trend arrows. |
| F5-05 | **IntelligenceTab layout** | `frontend/src/components/tabs/IntelligenceTab.tsx` | F5-01 thru F5-04 | 2-column grid: Sentiment + Earnings top row. CapEx + Keywords bottom row. |

**Deliverable:** Intelligence tab shows all four deep-analysis panels with live data.

---

### Stage 6: Live Feed Tab

Real-time Twitter/X stream + Polymarket odds + news.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F6-01 | **TwitterFeed component** | `frontend/src/components/panels/TwitterFeed.tsx` | F1-01, F1-09 | Scrollable tweet cards. Author, text, timestamp, engagement metrics. Sentiment tag per tweet (green/red/gray dot). Auto-updating chronological feed. Polls every 60s. |
| F6-02 | **PolymarketLiveOdds component** | `frontend/src/components/panels/PolymarketLiveOdds.tsx` | F1-01, F1-09 | Live probability changes for NVDA markets. Show delta: "NVDA > $150: 72% → 74% ▲". Compact card list. |
| F6-03 | **NewsFeed component** | `frontend/src/components/panels/NewsFeed.tsx` | F1-01, F1-09 | Recent NVDA news articles. Headline, source, timestamp, external link. Glass cards. |
| F6-04 | **LiveFeedTab layout** | `frontend/src/components/tabs/LiveFeedTab.tsx` | F6-01 thru F6-03 | 3-column or 2-column layout: Twitter feed (takes most space), Polymarket odds (sidebar), News (below or sidebar). |

**Deliverable:** Live feed tab shows real-time tweets, prediction market odds, and news.

---

### Stage 7: Integration & Animation Polish

Wire everything together and add the premium motion layer.

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| F7-01 | **Staggered page load animation** | All tab components | F2-07, F3-03, F4-03, F5-05, F6-04 | Each panel reveals with scale(0.97)+fade, staggered 80ms. Uses CSS animation-delay or Framer Motion orchestration. |
| F7-02 | **Price tick animations** | `HeroPrice.tsx`, `TickerCard.tsx` | F2-01, F2-04 | Numbers flash green/red briefly on value change, then settle. Smooth number transition. |
| F7-03 | **Alert system integration** | `App.tsx`, `AlertBanner.tsx`, `AlertFeed.tsx` | F1-05, F2-06 | Wire alert detection logic: compare current vs previous tick for all tickers. Fire AlertBanner for moves > 1%. Dismiss after 5s. |
| F7-04 | **Tab transition polish** | `App.tsx`, `TabNav.tsx` | F1-06, F1-07 | Smooth crossfade on tab switch. Content fades out/in. No jarring cuts. |
| F7-05 | **Loading skeleton integration** | All panel components | F1-02 | Every panel shows appropriate skeleton shape while data loads. Skeleton matches final panel dimensions to prevent layout shift. |
| F7-06 | **Error state integration** | All panel components | F1-03 | Every panel gracefully shows ErrorState on API failure. Retry button refetches. Other panels unaffected. |

**Deliverable:** Full premium interaction layer — animations, transitions, loading states, error states. The "damn" factor.

---

## PHASE 4: POLISH & DEPLOY

| ID | Task | Files | Depends On | Agent Work |
|----|------|-------|------------|------------|
| P4-01 | **Disclaimer banner** | `frontend/src/components/layout/Disclaimer.tsx` | F1-07 | Top-of-page banner: "Data may be delayed. Not financial advice. Always verify with your broker." Dismissible. |
| P4-02 | **Responsive pass** | All components | Stage 7 | Desktop-first is primary. Verify tablet (2-col) and mobile (1-col stack) don't break. Adjust font sizes, padding, grid columns via Tailwind breakpoints. |
| P4-03 | **Landing page** | `landing/index.html` or `frontend/src/pages/Landing.tsx` | F0-02 | Marketing page: hero section, feature highlights, CTA to dashboard. Same NVDA Index aesthetic. |
| P4-04 | **Scheduler test fixture fix** | `tests/test_scheduler.py` | — | Add mock PolymarketClient and SocialDataClient to test fixtures. Fix 14 TypeError failures. |
| P4-05 | **Polymarket engine tests** | `backend/tests/test_polymarket_engine.py` | — | Write test suite for polymarket_engine.py (currently has 0 tests). |
| P4-06 | **Deploy config** | `Dockerfile`, `vercel.json`, `railway.toml` | P4-02 | Backend Dockerfile for Railway/Render. Frontend vercel.json with env vars. Proxy config. |

---

## EXECUTION SUMMARY

| Stage | Tasks | Estimated Complexity | Key Output |
|-------|-------|---------------------|------------|
| Stage 0 | 3 | Low | Design system tokens + atmosphere |
| Stage 1 | 9 | Medium | Shared components + app shell + types |
| Stage 2 | 7 | High | NVDA Command tab (main hub) |
| Stage 3 | 3 | Medium | Probability & Flow tab |
| Stage 4 | 3 | Medium | AI Ecosystem tab |
| Stage 5 | 5 | Medium | Intelligence tab |
| Stage 6 | 4 | Medium | Live Feed tab |
| Stage 7 | 6 | Medium | Animation + polish + integration |
| Phase 4 | 6 | Low-Medium | Deploy + final polish |
| **Total** | **46 tasks** | | |

### Parallelization Opportunities

These stages can run in parallel once their dependencies are met:

- **Stage 0 → Stage 1** (sequential — design system must exist first)
- **Stage 1 → Stages 2, 3, 4, 5, 6** (all tab stages can run in parallel once shared components exist)
- **Stage 7** (requires all tabs complete)
- **Phase 4** can partially overlap with Stage 7

With 3 agents:
- Agent 1: Stage 2 (NVDA Command) → Stage 5 (Intelligence)
- Agent 2: Stage 3 (Probability) → Stage 4 (Ecosystem)
- Agent 3: Stage 6 (Live Feed) → Stage 7 (Polish)

---

## FILE TREE (Final)

```
frontend/src/
├── App.tsx
├── main.tsx
├── types/
│   └── api.ts
├── api/
│   └── client.ts                      (exists — extend with typed functions)
├── hooks/
│   └── usePolling.ts                  (exists — production ready)
├── styles/
│   └── globals.css                    (exists — overhaul with new design system)
├── components/
│   ├── ui/
│   │   ├── GlassPanel.tsx
│   │   ├── LoadingSkeleton.tsx
│   │   ├── ErrorState.tsx
│   │   ├── LastUpdated.tsx
│   │   ├── AlertBanner.tsx
│   │   └── TickerCard.tsx
│   ├── layout/
│   │   ├── TabNav.tsx
│   │   └── Disclaimer.tsx
│   ├── panels/
│   │   ├── HeroPrice.tsx
│   │   ├── EarningsCountdown.tsx
│   │   ├── PredictionsPanel.tsx
│   │   ├── CorrelatedTickers.tsx
│   │   ├── AlertFeed.tsx
│   │   ├── ProbabilityHeatmap.tsx
│   │   ├── SupplementaryMarkets.tsx
│   │   ├── TickerDashboard.tsx
│   │   ├── PerformanceTable.tsx
│   │   ├── SentimentPanel.tsx
│   │   ├── EarningsConsensus.tsx
│   │   ├── CapExTracker.tsx
│   │   ├── AIKeywordScores.tsx
│   │   ├── TwitterFeed.tsx
│   │   ├── PolymarketLiveOdds.tsx
│   │   └── NewsFeed.tsx
│   └── tabs/
│       ├── NVDACommandTab.tsx
│       ├── ProbabilityFlowTab.tsx
│       ├── EcosystemTab.tsx
│       ├── IntelligenceTab.tsx
│       └── LiveFeedTab.tsx
```

---

## BACKEND TASKS (Remaining)

These are non-blocking but should be completed during Phase 3:

| ID | Task | Priority |
|----|------|----------|
| B-01 | Fix scheduler test fixtures (add mock Polymarket + SocialData clients) | Medium |
| B-02 | Write polymarket_engine.py test suite | Medium |
| B-03 | Add multi-symbol support to `/api/price/` endpoint (for correlated tickers) | High — needed for Tab 1 & Tab 3 |
| B-04 | Add `/api/sentiment/tweets` endpoint to expose raw tweet data for Live Feed tab | Medium — needed for Tab 5 |
| B-05 | Add ticker alerts endpoint or WebSocket for real-time price move detection | Low — can be computed client-side initially |

---

*End of implementation plan.*
