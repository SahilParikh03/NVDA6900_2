import { useCallback } from 'react'
import { fetchPrice, fetchCorrelatedPrices } from '../../api/client'
import usePolling from '../../hooks/usePolling'
import { GlassPanel, LoadingSkeleton, ErrorState, LastUpdated } from '../ui'

import type { PriceQuote } from '../../types/api'

interface TickerCategory {
  label: string
  tickers: TickerDef[]
}

interface TickerDef {
  symbol: string
  displayName?: string
}

const CATEGORIES: TickerCategory[] = [
  {
    label: 'PRIMARY',
    tickers: [{ symbol: 'NVDA' }],
  },
  {
    label: 'HYPERSCALER',
    tickers: [
      { symbol: 'GOOGL' },
      { symbol: 'MSFT' },
      { symbol: 'AAPL' },
      { symbol: 'AMZN' },
      { symbol: 'META' },
    ],
  },
  {
    label: 'SEMICONDUCTOR',
    tickers: [{ symbol: 'AMD' }, { symbol: 'INTC' }],
  },
  {
    label: 'MANUFACTURING',
    tickers: [
      { symbol: 'TSM' },
      { symbol: 'SSNLF', displayName: 'Samsung' },
    ],
  },
  {
    label: 'CRYPTO',
    tickers: [{ symbol: 'BTC-USD', displayName: 'BTC' }],
  },
]

interface TickerCardInlineProps {
  symbol: string
  displayName?: string
  price: number | null
  changePercent: number | null
  isLive: boolean
}

function TickerCardInline({
  symbol,
  displayName,
  price,
  changePercent,
  isLive,
}: TickerCardInlineProps) {
  const isPositive = changePercent !== null && changePercent >= 0
  const isNegative = changePercent !== null && changePercent < 0

  const borderColor = isPositive
    ? 'border-nvda-green/30'
    : isNegative
      ? 'border-red/30'
      : 'border-border'

  const changeColor = isPositive
    ? 'text-nvda-green'
    : isNegative
      ? 'text-red'
      : 'text-text-muted'

  const changeSign = isPositive ? '+' : ''

  return (
    <div
      className={`glass-panel-inner p-4 flex flex-col gap-2 border ${borderColor} transition-colors duration-300`}
    >
      <div className="flex items-center justify-between">
        <span className="font-display text-xs tracking-wider text-text-primary">
          {displayName ?? symbol}
        </span>
        {isLive && (
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-nvda-green animate-glow-pulse" />
        )}
      </div>

      <span className="font-data text-lg text-text-primary leading-none">
        {price !== null ? `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--'}
      </span>

      <span className={`font-data text-xs ${changeColor}`}>
        {changePercent !== null
          ? `${changeSign}${changePercent.toFixed(2)}%`
          : '0.00%'}
      </span>
    </div>
  )
}

function TickerDashboard() {
  const fetcher = useCallback(() => fetchPrice(), [])
  const { data: nvdaPrice, error, isLoading, lastUpdated } = usePolling(fetcher, {
    interval: 5000,
  })

  const correlatedFetcher = useCallback(() => fetchCorrelatedPrices(), [])
  const { data: correlatedPrices } = usePolling<Record<string, PriceQuote>>(
    correlatedFetcher,
    { interval: 30000 },
  )

  if (isLoading) {
    return (
      <GlassPanel title="AI ECOSYSTEM">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 12 }, (_, i) => (
            <LoadingSkeleton key={i} variant="card" className="h-24" />
          ))}
        </div>
      </GlassPanel>
    )
  }

  if (error) {
    return (
      <GlassPanel title="AI ECOSYSTEM">
        <ErrorState message="Failed to load price data" />
      </GlassPanel>
    )
  }

  return (
    <GlassPanel title="AI ECOSYSTEM">
      <div className="flex flex-col gap-6">
        {CATEGORIES.map((category) => (
          <div key={category.label} className="flex flex-col gap-3">
            {/* Category label */}
            <span className="font-display text-[10px] uppercase tracking-widest text-text-muted">
              {category.label}
            </span>

            {/* Ticker grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {category.tickers.map((ticker) => {
                const isNvda = ticker.symbol === 'NVDA'
                const correlated = !isNvda ? correlatedPrices?.[ticker.symbol] : undefined
                const price = isNvda && nvdaPrice
                  ? nvdaPrice.price
                  : correlated?.price ?? null
                const changePercent = isNvda && nvdaPrice
                  ? nvdaPrice.changePercentage
                  : correlated?.changePercentage ?? null

                return (
                  <TickerCardInline
                    key={ticker.symbol}
                    symbol={ticker.symbol}
                    displayName={ticker.displayName}
                    price={price}
                    changePercent={changePercent}
                    isLive={isNvda}
                  />
                )
              })}
            </div>
          </div>
        ))}

        <div className="flex justify-end">
          <LastUpdated timestamp={lastUpdated} />
        </div>
      </div>
    </GlassPanel>
  )
}

export default TickerDashboard
