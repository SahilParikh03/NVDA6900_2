import { useCallback } from 'react'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchHeatmap, fetchSupplementaryMarkets } from '../../api/client'
import type {
  PolymarketHeatmap,
  PolymarketMarket,
  SupplementaryMarkets,
  SupplementaryMarket,
} from '../../types/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatProbability(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function formatVolume(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toFixed(0)}`
}

function truncateQuestion(q: string, maxLen: number): string {
  if (q.length <= maxLen) return q
  return q.slice(0, maxLen).trimEnd() + '...'
}

function probabilityColor(prob: number): string {
  if (prob >= 0.7) return 'text-nvda-green'
  if (prob >= 0.4) return 'text-amber'
  return 'text-red'
}

function probabilityBarColor(prob: number): string {
  if (prob >= 0.7) return 'bg-nvda-green/60'
  if (prob >= 0.4) return 'bg-amber/60'
  return 'bg-red/60'
}

function categoryBadgeClass(category: string): string {
  const lower = category.toLowerCase()
  if (lower.includes('earnings') || lower.includes('revenue'))
    return 'border-nvda-green/30 text-nvda-green bg-nvda-green/10'
  if (lower.includes('price') || lower.includes('stock'))
    return 'border-amber/30 text-amber bg-amber/10'
  return 'border-border text-text-muted bg-surface'
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MarketCard({ market }: { market: PolymarketMarket }) {
  return (
    <div className="glass-panel-inner p-3">
      <p
        className="mb-2 font-body text-xs text-text-primary leading-tight line-clamp-1"
        title={market.question}
      >
        {truncateQuestion(market.question, 80)}
      </p>

      <div className="flex items-center gap-3">
        <span
          className={`font-data text-xl font-bold tabular-nums ${probabilityColor(market.probability)}`}
        >
          {formatProbability(market.probability)}
        </span>

        <div className="relative flex-1 h-2 overflow-hidden rounded-full bg-surface">
          <div
            className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ${probabilityBarColor(market.probability)}`}
            style={{ width: `${market.probability * 100}%` }}
          />
        </div>
      </div>

      <div className="mt-2 flex items-center gap-3">
        <span className="font-data text-[10px] text-text-muted">
          Vol: {formatVolume(market.volume)}
        </span>
        <span className="font-data text-[10px] text-text-muted">
          Liq: {formatVolume(market.liquidity)}
        </span>
      </div>
    </div>
  )
}

function SupplementaryCard({ market }: { market: SupplementaryMarket }) {
  return (
    <div className="glass-panel-inner p-3">
      <div className="mb-2 flex items-center gap-2">
        <span
          className={`rounded-full border px-2 py-0.5 font-display text-[9px] uppercase tracking-wider ${categoryBadgeClass(market.category)}`}
        >
          {market.category}
        </span>
      </div>

      <p
        className="mb-2 font-body text-xs text-text-primary leading-tight line-clamp-1"
        title={market.question}
      >
        {truncateQuestion(market.question, 80)}
      </p>

      <div className="flex items-center gap-3">
        <span
          className={`font-data text-lg font-bold tabular-nums ${probabilityColor(market.probability)}`}
        >
          {formatProbability(market.probability)}
        </span>

        <div className="relative flex-1 h-1.5 overflow-hidden rounded-full bg-surface">
          <div
            className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ${probabilityBarColor(market.probability)}`}
            style={{ width: `${market.probability * 100}%` }}
          />
        </div>
      </div>

      <div className="mt-1.5 flex items-center gap-3">
        <span className="font-data text-[10px] text-text-muted">
          Vol: {formatVolume(market.volume)}
        </span>
        <span className="font-data text-[10px] text-text-muted">
          Liq: {formatVolume(market.liquidity)}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function PolymarketLiveOdds() {
  const heatmapFetcher = useCallback(() => fetchHeatmap(), [])
  const suppFetcher = useCallback(() => fetchSupplementaryMarkets(), [])

  const {
    data: heatmapData,
    error: heatmapError,
    isLoading: heatmapLoading,
    lastUpdated: heatmapUpdated,
  } = usePolling<PolymarketHeatmap>(heatmapFetcher, { interval: 30_000 })

  const {
    data: suppData,
    error: suppError,
    isLoading: suppLoading,
  } = usePolling<SupplementaryMarkets>(suppFetcher, { interval: 30_000 })

  const isLoading = heatmapLoading || suppLoading
  const hasError = (heatmapError && !heatmapData) || (suppError && !suppData)

  return (
    <GlassPanel title="POLYMARKET LIVE ODDS" className="flex flex-col h-full">
      {isLoading && !heatmapData && !suppData && (
        <LoadingSkeleton variant="line" lines={6} />
      )}
      {hasError && !heatmapData && !suppData && (
        <ErrorState message="Polymarket data unavailable" />
      )}

      {(heatmapData || suppData) && (
        <div className="flex flex-1 flex-col gap-4 min-h-0">
          <div className="flex-1 space-y-3 overflow-y-auto max-h-[600px] pr-1">
            {/* Heatmap markets */}
            {heatmapData && heatmapData.markets.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
                    NVDA Price Markets
                  </span>
                  {heatmapData.expected_level > 0 && (
                    <span className="font-data text-xs text-nvda-green tabular-nums">
                      Expected: ${heatmapData.expected_level.toFixed(0)}
                    </span>
                  )}
                </div>
                {heatmapData.markets.map((market) => (
                  <MarketCard key={market.token_id} market={market} />
                ))}
              </div>
            )}

            {/* Supplementary markets */}
            {suppData && suppData.markets.length > 0 && (
              <div className="space-y-2">
                <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
                  Supplementary Markets
                </span>
                {suppData.markets.map((market, idx) => (
                  <SupplementaryCard
                    key={`${market.question}-${idx}`}
                    market={market}
                  />
                ))}
              </div>
            )}

            {/* Empty state */}
            {(!heatmapData || heatmapData.markets.length === 0) &&
              (!suppData || suppData.markets.length === 0) && (
                <p className="py-8 text-center font-body text-sm text-text-muted">
                  No active markets
                </p>
              )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end pt-2">
            <LastUpdated timestamp={heatmapUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default PolymarketLiveOdds
