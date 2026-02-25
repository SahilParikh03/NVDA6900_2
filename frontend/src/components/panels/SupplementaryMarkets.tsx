import { useCallback } from 'react'
import { fetchSupplementaryMarkets } from '../../api/client'
import usePolling from '../../hooks/usePolling'
import { GlassPanel, LoadingSkeleton, ErrorState, LastUpdated } from '../ui'
import type { SupplementaryMarket } from '../../types/api'

function formatVolume(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toFixed(0)}`
}

interface MarketCardProps {
  market: SupplementaryMarket
  index: number
}

function MarketCard({ market, index }: MarketCardProps) {
  const probabilityPct = market.yes_price * 100

  return (
    <div
      className={`glass-panel-inner p-4 flex flex-col gap-3 animate-fade-in stagger-${Math.min(index + 1, 8)}`}
    >
      {/* Category badge */}
      <div className="flex items-center justify-between">
        <span className="inline-block rounded-full bg-green-dim px-2.5 py-0.5 font-display text-[9px] uppercase tracking-wider text-nvda-green">
          MARKET
        </span>
      </div>

      {/* Question */}
      <p className="font-body text-sm text-text-primary leading-snug line-clamp-2">
        {market.question}
      </p>

      {/* Probability */}
      <div className="flex items-end gap-2">
        <span className="font-data text-2xl text-nvda-green text-glow leading-none">
          {probabilityPct.toFixed(1)}%
        </span>
        <span className="font-data text-xs text-text-muted mb-0.5">YES</span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-surface overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${probabilityPct}%`,
            background:
              probabilityPct > 60
                ? '#76B900'
                : probabilityPct > 30
                  ? 'rgba(118,185,0,0.6)'
                  : 'rgba(118,185,0,0.3)',
          }}
        />
      </div>

      {/* Volume */}
      <div className="flex items-center gap-4 text-text-muted">
        <span className="font-data text-[10px]">
          Vol {formatVolume(market.volume)}
        </span>
      </div>
    </div>
  )
}

function SupplementaryMarketsPanel() {
  const fetcher = useCallback(() => fetchSupplementaryMarkets(), [])
  const { data, error, isLoading, lastUpdated } = usePolling(fetcher, {
    interval: 30000,
  })

  return (
    <GlassPanel title="SUPPLEMENTARY MARKETS">
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }, (_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      )}

      {!isLoading && error && (
        <ErrorState message="Failed to load supplementary markets" />
      )}

      {!isLoading && !error && data && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.supplementary.map((market, idx) => (
              <MarketCard key={market.question} market={market} index={idx} />
            ))}
          </div>

          {data.supplementary.length === 0 && (
            <p className="font-body text-sm text-text-muted text-center py-8">
              No supplementary markets available
            </p>
          )}

          <div className="flex justify-end">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default SupplementaryMarketsPanel
