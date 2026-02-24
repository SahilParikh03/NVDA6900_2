import { useCallback } from 'react'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchEarnings } from '../../api/client'
import type {
  EarningsConsolidated,
  EarningsEstimate,
  EarningsSurprise,
} from '../../types/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(1)}B`
  }
  if (abs >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`
  }
  return `$${value.toFixed(2)}`
}

function formatEps(value: number): string {
  return `$${value.toFixed(2)}`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EpsEstimate({ estimate }: { estimate: EarningsEstimate }) {
  return (
    <div className="glass-panel-inner p-4">
      <h4 className="mb-3 font-display text-[10px] uppercase tracking-wider text-text-muted">
        EPS Estimate
      </h4>
      <div className="flex items-baseline gap-2">
        <span className="font-data text-2xl font-bold text-nvda-green tabular-nums">
          {formatEps(estimate.estimatedEpsAvg)}
        </span>
        <span className="font-data text-xs text-text-muted">avg</span>
      </div>
      <div className="mt-2 flex items-center gap-4">
        <div className="flex flex-col">
          <span className="font-data text-[10px] text-text-muted">Low</span>
          <span className="font-data text-sm text-red tabular-nums">
            {formatEps(estimate.estimatedEpsLow)}
          </span>
        </div>
        {/* Range bar */}
        <div className="flex-1">
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface">
            <RangeBar
              low={estimate.estimatedEpsLow}
              avg={estimate.estimatedEpsAvg}
              high={estimate.estimatedEpsHigh}
            />
          </div>
        </div>
        <div className="flex flex-col items-end">
          <span className="font-data text-[10px] text-text-muted">High</span>
          <span className="font-data text-sm text-nvda-green tabular-nums">
            {formatEps(estimate.estimatedEpsHigh)}
          </span>
        </div>
      </div>
      <p className="mt-2 font-data text-[10px] text-text-muted">
        {estimate.numberAnalystEstimatedEps} analysts
      </p>
    </div>
  )
}

function RevenueEstimate({ estimate }: { estimate: EarningsEstimate }) {
  return (
    <div className="glass-panel-inner p-4">
      <h4 className="mb-3 font-display text-[10px] uppercase tracking-wider text-text-muted">
        Revenue Estimate
      </h4>
      <div className="flex items-baseline gap-2">
        <span className="font-data text-2xl font-bold text-nvda-green tabular-nums">
          {formatCurrency(estimate.estimatedRevenueAvg)}
        </span>
        <span className="font-data text-xs text-text-muted">avg</span>
      </div>
      <div className="mt-2 flex items-center gap-4">
        <div className="flex flex-col">
          <span className="font-data text-[10px] text-text-muted">Low</span>
          <span className="font-data text-sm text-red tabular-nums">
            {formatCurrency(estimate.estimatedRevenueLow)}
          </span>
        </div>
        <div className="flex-1">
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface">
            <RangeBar
              low={estimate.estimatedRevenueLow}
              avg={estimate.estimatedRevenueAvg}
              high={estimate.estimatedRevenueHigh}
            />
          </div>
        </div>
        <div className="flex flex-col items-end">
          <span className="font-data text-[10px] text-text-muted">High</span>
          <span className="font-data text-sm text-nvda-green tabular-nums">
            {formatCurrency(estimate.estimatedRevenueHigh)}
          </span>
        </div>
      </div>
      <p className="mt-2 font-data text-[10px] text-text-muted">
        {estimate.numberAnalystEstimatedRevenue} analysts
      </p>
    </div>
  )
}

function RangeBar({
  low,
  avg,
  high,
}: {
  low: number
  avg: number
  high: number
}) {
  const range = high - low
  if (range <= 0) {
    return (
      <div className="absolute inset-0 rounded-full bg-nvda-green/40" />
    )
  }
  const avgPct = ((avg - low) / range) * 100

  return (
    <>
      <div className="absolute inset-0 rounded-full bg-nvda-green/20" />
      <div
        className="absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded-sm bg-nvda-green transition-all duration-500"
        style={{ left: `${avgPct}%` }}
      />
    </>
  )
}

function SurpriseRow({ surprise }: { surprise: EarningsSurprise }) {
  const beat = surprise.actualEarningResult > surprise.estimatedEarning
  const diff = surprise.actualEarningResult - surprise.estimatedEarning

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="font-data text-xs text-text-muted">
        {formatDate(surprise.date)}
      </span>
      <div className="flex items-center gap-3">
        <span className="font-data text-xs text-text-primary tabular-nums">
          {formatEps(surprise.actualEarningResult)}
        </span>
        <span className="font-data text-[10px] text-text-muted">vs</span>
        <span className="font-data text-xs text-text-muted tabular-nums">
          {formatEps(surprise.estimatedEarning)}
        </span>
        <span
          className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold ${
            beat
              ? 'bg-nvda-green/15 text-nvda-green'
              : 'bg-red/15 text-red'
          }`}
        >
          {beat ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <path d="M2 5.5L4.2 7.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <path d="M3 3L7 7M7 3L3 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          )}
        </span>
        <span
          className={`font-data text-[10px] tabular-nums ${
            diff >= 0 ? 'text-nvda-green' : 'text-red'
          }`}
        >
          {diff >= 0 ? '+' : ''}
          {formatEps(diff)}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function EarningsConsensus() {
  const fetcher = useCallback(() => fetchEarnings(), [])
  const { data, error, isLoading, lastUpdated } = usePolling<EarningsConsolidated>(
    fetcher,
    { interval: 86_400_000 }
  )

  const latestEstimate =
    data?.estimates && data.estimates.length > 0 ? data.estimates[0] : null

  const sortedSurprises = data?.surprises
    ? [...data.surprises].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
      )
    : []

  return (
    <GlassPanel title="EARNINGS CONSENSUS">
      {isLoading && !data && <LoadingSkeleton variant="chart" />}
      {error && !data && (
        <ErrorState message="Earnings data unavailable" />
      )}

      {data && (
        <div className="flex flex-col gap-5">
          {/* Next earnings date */}
          {data.calendar && data.calendar.date && (
            <div className="flex items-center gap-2">
              <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
                Next Earnings
              </span>
              <span className="rounded-full border border-nvda-green/30 bg-nvda-green/10 px-3 py-0.5 font-data text-xs text-nvda-green">
                {formatDate(data.calendar.date)}
              </span>
            </div>
          )}

          {/* Estimates grid */}
          {latestEstimate && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <EpsEstimate estimate={latestEstimate} />
              <RevenueEstimate estimate={latestEstimate} />
            </div>
          )}

          {/* Historical beat/miss */}
          {sortedSurprises.length > 0 && (
            <div>
              <h4 className="mb-2 font-display text-[10px] uppercase tracking-wider text-text-muted">
                Historical Beat / Miss
              </h4>
              <div className="glass-panel-inner divide-y divide-border px-4 py-2">
                {sortedSurprises.slice(0, 6).map((s) => (
                  <SurpriseRow key={s.date} surprise={s} />
                ))}
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-end">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default EarningsConsensus
