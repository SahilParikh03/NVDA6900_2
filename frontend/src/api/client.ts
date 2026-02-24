import axios from 'axios'

import type {
  PriceQuote,
  PriceHistoryEntry,
  PriceChange,
  PolymarketHeatmap,
  SupplementaryMarkets,
  EarningsConsolidated,
  EarningsCalendarEntry,
  EarningsEstimate,
  EarningsSurprise,
  SentimentData,
  NewsArticle,
  CapexData,
  TranscriptData,
  PredictionsData,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ----------------------------------------------------------
// Price
// ----------------------------------------------------------

export async function fetchPrice(): Promise<PriceQuote> {
  const response = await apiClient.get<{ source: string; data: PriceQuote[] }>('/price/')
  return response.data.data[0]
}

export async function fetchPriceHistory(): Promise<PriceHistoryEntry[]> {
  const response = await apiClient.get<{ symbol: string; historical: PriceHistoryEntry[] }>('/price/history')
  return response.data.historical
}

export async function fetchPriceChange(symbol?: string): Promise<PriceChange> {
  const params = symbol ? { symbol } : undefined
  const response = await apiClient.get<{ data: PriceChange }>('/price/change', { params })
  return response.data.data
}

export async function fetchCorrelatedPrices(): Promise<Record<string, PriceQuote>> {
  const response = await apiClient.get<{ source: string; data: Record<string, PriceQuote> }>('/price/correlated')
  return response.data.data
}

// ----------------------------------------------------------
// Options / Polymarket
// ----------------------------------------------------------

export async function fetchHeatmap(): Promise<PolymarketHeatmap> {
  const response = await apiClient.get<PolymarketHeatmap>('/options/heatmap')
  return response.data
}

export async function fetchSupplementaryMarkets(): Promise<SupplementaryMarkets> {
  const response = await apiClient.get<SupplementaryMarkets>('/options/supplementary')
  return response.data
}

// ----------------------------------------------------------
// Earnings
// ----------------------------------------------------------

export async function fetchEarnings(): Promise<EarningsConsolidated> {
  const response = await apiClient.get<EarningsConsolidated>('/earnings/')
  return response.data
}

export async function fetchEarningsCalendar(): Promise<EarningsCalendarEntry | null> {
  const response = await apiClient.get<{ data: EarningsCalendarEntry[] }>('/earnings/calendar')
  const allEntries = response.data.data
  return allEntries.find((e) => e.symbol === 'NVDA') ?? null
}

export async function fetchEarningsEstimates(): Promise<EarningsEstimate[]> {
  const response = await apiClient.get<{ data: EarningsEstimate[] }>('/earnings/estimates')
  return response.data.data
}

export async function fetchEarningsSurprises(): Promise<EarningsSurprise[]> {
  const response = await apiClient.get<{ data: EarningsSurprise[] }>('/earnings/surprises')
  return response.data.data
}

// ----------------------------------------------------------
// Sentiment
// ----------------------------------------------------------

export async function fetchSentiment(): Promise<SentimentData> {
  const response = await apiClient.get<SentimentData>('/sentiment/')
  return response.data
}

export async function fetchNews(): Promise<NewsArticle[]> {
  const response = await apiClient.get<{ data: NewsArticle[] }>('/sentiment/news')
  return response.data.data
}

// ----------------------------------------------------------
// Hyperscaler
// ----------------------------------------------------------

export async function fetchCapex(): Promise<CapexData> {
  const response = await apiClient.get<CapexData>('/hyperscaler/capex')
  return response.data
}

export async function fetchTranscripts(): Promise<TranscriptData> {
  const response = await apiClient.get<TranscriptData>('/hyperscaler/transcripts')
  return response.data
}

// ----------------------------------------------------------
// Predictions
// ----------------------------------------------------------

export async function fetchPredictions(): Promise<PredictionsData> {
  const response = await apiClient.get<PredictionsData>('/predictions/')
  return response.data
}

export default apiClient
