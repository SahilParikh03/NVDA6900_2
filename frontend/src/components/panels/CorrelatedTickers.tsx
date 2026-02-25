import { useCallback } from 'react'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import TickerCard from '../ui/TickerCard'
import usePolling from '../../hooks/usePolling'
import { fetchCorrelatedPrices } from '../../api/client'
import type { PriceQuote } from '../../types/api'

const CORRELATED_SYMBOLS = [
  'GOOGL',
  'MSFT',
  'AAPL',
  'AMZN',
  'META',
  'AMD',
  'INTC',
  'TSM',
  'BTCUSD',
] as const

function CorrelatedTickers() {
  const fetcher = useCallback(() => fetchCorrelatedPrices(), [])
  const { data, error, isLoading } = usePolling<Record<string, PriceQuote>>(
    fetcher,
    { interval: 30000 },
  )

  if (isLoading && !data) {
    return (
      <GlassPanel title="CORRELATED TICKERS">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {CORRELATED_SYMBOLS.map((sym) => (
            <LoadingSkeleton key={sym} variant="card" className="h-24" />
          ))}
        </div>
      </GlassPanel>
    )
  }

  if (error && !data) {
    return (
      <GlassPanel title="CORRELATED TICKERS">
        <ErrorState message="Failed to load correlated tickers" />
      </GlassPanel>
    )
  }

  return (
    <GlassPanel title="CORRELATED TICKERS">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {CORRELATED_SYMBOLS.map((symbol) => {
          const quote = data?.[symbol]
          return (
            <TickerCard
              key={symbol}
              symbol={symbol}
              price={quote?.price ?? 0}
              changePercent={quote?.changePercentage ?? 0}
            />
          )
        })}
      </div>
    </GlassPanel>
  )
}

export default CorrelatedTickers
