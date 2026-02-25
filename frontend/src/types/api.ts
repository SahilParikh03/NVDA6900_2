// ============================================================
// NVDA6900 — Backend API Response Types
// ============================================================

// ----------------------------------------------------------
// Price endpoints
// ----------------------------------------------------------

/** GET /api/price/ */
export interface PriceQuote {
  symbol: string;
  price: number;
  changePercentage: number;
  change: number;
  dayLow: number;
  dayHigh: number;
  yearLow: number;
  yearHigh: number;
  marketCap: number;
  priceAvg50: number;
  priceAvg200: number;
  volume: number;
  avgVolume: number;
  exchange: string;
  open: number;
  previousClose: number;
  timestamp: number;
}

/** GET /api/price/history — single bar */
export interface PriceHistoryEntry {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** GET /api/price/change */
export interface PriceChange {
  symbol: string;
  "1D": number;
  "5D": number;
  "1M": number;
  "3M": number;
  "6M": number;
  ytd: number;
  "1Y": number;
  "3Y": number;
  "5Y": number;
  "10Y": number;
  max: number;
}

// ----------------------------------------------------------
// Options / Polymarket endpoints
// ----------------------------------------------------------

export interface PolymarketMarket {
  question: string;
  strike: number;
  yes_price: number;
  market_id: string;
  volume: number;
  volume_24h: number;
  liquidity: number;
}

/** GET /api/options/heatmap */
export interface PolymarketHeatmap {
  price_levels: PolymarketMarket[];
  key_levels: {
    max_conviction: number;
    fifty_percent_level: number;
    low_conviction: number;
  };
  supplementary: SupplementaryMarket[];
  total_volume: number;
  market_count: number;
  last_updated: string;
}

export interface SupplementaryMarket {
  question: string;
  yes_price: number;
  volume: number;
  market_id: string;
}

/** GET /api/options/supplementary */
export interface SupplementaryMarkets {
  supplementary: SupplementaryMarket[];
  market_count: number;
  last_updated: string;
}

// ----------------------------------------------------------
// Earnings endpoints
// ----------------------------------------------------------

/** GET /api/earnings/calendar */
export interface EarningsCalendarEntry {
  date: string;
  symbol: string;
  eps: number | null;
  epsEstimated: number | null;
  revenue: number | null;
  revenueEstimated: number | null;
}

/** GET /api/earnings/estimates — single period */
export interface EarningsEstimate {
  date: string;
  symbol: string;
  estimatedEpsAvg: number;
  estimatedEpsHigh: number;
  estimatedEpsLow: number;
  estimatedRevenueAvg: number;
  estimatedRevenueHigh: number;
  estimatedRevenueLow: number;
  numberAnalystEstimatedEps: number;
  numberAnalystEstimatedRevenue: number;
}

/** GET /api/earnings/surprises — single quarter */
export interface EarningsSurprise {
  date: string;
  symbol: string;
  actualEarningResult: number;
  estimatedEarning: number;
}

/** GET /api/earnings/ — consolidated */
export interface EarningsConsolidated {
  calendar: EarningsCalendarEntry;
  estimates: EarningsEstimate[];
  surprises: EarningsSurprise[];
}

// ----------------------------------------------------------
// Sentiment endpoints
// ----------------------------------------------------------

export interface SentimentHistoryEntry {
  date: string;
  score: number;
  mentions: number;
}

/** GET /api/sentiment/ */
export interface SentimentData {
  current_score: number;
  sentiment_label: string;
  rate_of_change: number;
  roc_direction: string;
  mention_volume_today: number;
  mention_volume_7d_avg: number;
  volume_spike: boolean;
  history: SentimentHistoryEntry[];
  last_updated: string;
}

/** GET /api/sentiment/news — single article */
export interface NewsArticle {
  title: string;
  text: string;
  url: string;
  publishedDate: string;
  site: string;
  image?: string;
}

// ----------------------------------------------------------
// Hyperscaler endpoints
// ----------------------------------------------------------

export interface CapexQuarter {
  period: string;
  capex: number;
  revenue: number;
  capex_to_revenue: number;
  capex_qoq_growth: number | null;
}

export interface CapexCompany {
  symbol: string;
  name: string;
  quarters: CapexQuarter[];
}

/** GET /api/hyperscaler/capex */
export interface CapexData {
  companies: CapexCompany[];
  aggregate_trend: string;
  last_updated: string;
}

export interface TranscriptKeyword {
  keyword: string;
  count: number;
}

export interface TranscriptEntry {
  symbol: string;
  quarter: string;
  total_ai_score: number;
  top_keywords: TranscriptKeyword[];
}

/** GET /api/hyperscaler/transcripts */
export interface TranscriptData {
  transcripts: TranscriptEntry[];
  trend: string;
  last_updated: string;
}

// ----------------------------------------------------------
// Predictions endpoint
// ----------------------------------------------------------

export interface PredictionSignal {
  factor: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  detail: string;
}

/** GET /api/predictions/ */
export interface PredictionsData {
  outlook: string;
  confidence: string;
  signals: PredictionSignal[];
  last_updated: string;
}
