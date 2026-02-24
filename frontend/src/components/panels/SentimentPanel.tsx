import { useCallback } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchSentiment } from '../../api/client'
import type { SentimentData, SentimentHistoryEntry } from '../../types/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clampScore(score: number): number {
  return Math.max(-100, Math.min(100, score))
}

function scoreToPercent(score: number): number {
  return ((clampScore(score) + 100) / 200) * 100
}

function sentimentColor(label: string): string {
  const lower = label.toLowerCase()
  if (lower === 'bullish') return 'text-nvda-green'
  if (lower === 'bearish') return 'text-red'
  return 'text-amber'
}

function sentimentBgColor(label: string): string {
  const lower = label.toLowerCase()
  if (lower === 'bullish') return 'bg-nvda-green/15 border-nvda-green/30 text-nvda-green'
  if (lower === 'bearish') return 'bg-red/15 border-red/30 text-red'
  return 'bg-amber/15 border-amber/30 text-amber'
}

function formatRoc(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface ChartTooltipPayload {
  value: number
  payload: SentimentHistoryEntry
}

interface ChartTooltipProps {
  active?: boolean
  payload?: ChartTooltipPayload[]
  label?: string
}

function ChartTooltip({ active, payload }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const entry = payload[0]
  return (
    <div className="glass-panel-inner px-3 py-2">
      <p className="font-data text-xs text-text-muted">{entry.payload.date}</p>
      <p className="font-data text-sm text-nvda-green">
        Score: {entry.value.toFixed(1)}
      </p>
      <p className="font-data text-xs text-text-muted">
        Mentions: {entry.payload.mentions.toLocaleString()}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SentimentGauge({ score }: { score: number }) {
  const pct = scoreToPercent(score)

  return (
    <div className="flex flex-col items-center gap-3">
      <span className="font-data text-3xl font-bold text-text-primary tabular-nums">
        {score > 0 ? '+' : ''}
        {score.toFixed(1)}
      </span>

      {/* Horizontal gauge bar */}
      <div className="relative h-2.5 w-full max-w-xs rounded-full overflow-hidden">
        {/* Gradient track */}
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background:
              'linear-gradient(to right, #FF3B3B 0%, #FFB800 50%, #76B900 100%)',
            opacity: 0.25,
          }}
        />
        {/* Active fill up to current value */}
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
          style={{
            width: `${pct}%`,
            background:
              'linear-gradient(to right, #FF3B3B 0%, #FFB800 50%, #76B900 100%)',
          }}
        />
        {/* Pointer dot */}
        <div
          className="absolute top-1/2 h-4 w-4 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-text-primary bg-base shadow-lg transition-all duration-700"
          style={{ left: `${pct}%` }}
        />
      </div>

      {/* Labels */}
      <div className="flex w-full max-w-xs justify-between">
        <span className="font-data text-[10px] text-red">-100</span>
        <span className="font-data text-[10px] text-amber">0</span>
        <span className="font-data text-[10px] text-nvda-green">+100</span>
      </div>
    </div>
  )
}

function RocIndicator({
  roc,
  direction,
}: {
  roc: number
  direction: string
}) {
  const isUp = direction.toLowerCase() === 'accelerating' || roc > 0
  const color = isUp ? 'text-nvda-green' : 'text-red'
  const arrow = isUp ? '\u25B2' : '\u25BC'

  return (
    <span className={`inline-flex items-center gap-1 font-data text-sm ${color}`}>
      <span className="text-xs">{arrow}</span>
      {formatRoc(roc)}
    </span>
  )
}

function VolumeBar({
  today,
  avg,
  spike,
}: {
  today: number
  avg: number
  spike: boolean
}) {
  const max = Math.max(today, avg, 1)
  const todayPct = (today / max) * 100
  const avgPct = (avg / max) * 100

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="font-body text-xs text-text-muted">Mention Volume</span>
        {spike && (
          <span className="rounded-full border border-amber/40 bg-amber/15 px-2 py-0.5 font-display text-[10px] font-bold uppercase tracking-wider text-amber">
            SPIKE
          </span>
        )}
      </div>

      {/* Today bar */}
      <div className="flex items-center gap-3">
        <span className="w-12 shrink-0 font-data text-[10px] text-text-muted">
          Today
        </span>
        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-surface">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-nvda-green/70 transition-all duration-500"
            style={{ width: `${todayPct}%` }}
          />
        </div>
        <span className="w-14 shrink-0 text-right font-data text-xs text-text-primary tabular-nums">
          {today.toLocaleString()}
        </span>
      </div>

      {/* 7d avg bar */}
      <div className="flex items-center gap-3">
        <span className="w-12 shrink-0 font-data text-[10px] text-text-muted">
          7d Avg
        </span>
        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-surface">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-text-muted/50 transition-all duration-500"
            style={{ width: `${avgPct}%` }}
          />
        </div>
        <span className="w-14 shrink-0 text-right font-data text-xs text-text-muted tabular-nums">
          {avg.toLocaleString()}
        </span>
      </div>
    </div>
  )
}

function HistoryChart({ history }: { history: SentimentHistoryEntry[] }) {
  const sorted = [...history].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  )

  return (
    <div className="mt-4">
      <p className="mb-2 font-body text-xs text-text-muted">7-Day History</p>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={sorted} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <defs>
            <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#76B900" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#76B900" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: '#6B6B7B', fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: string) => {
              const d = new Date(v)
              return `${d.getMonth() + 1}/${d.getDate()}`
            }}
          />
          <YAxis
            domain={[-100, 100]}
            tick={{ fontSize: 10, fill: '#6B6B7B', fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
            width={32}
          />
          <Tooltip content={<ChartTooltip />} />
          <Area
            type="monotone"
            dataKey="score"
            stroke="#76B900"
            strokeWidth={2}
            fill="url(#sentimentGradient)"
            animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function SentimentPanel() {
  const fetcher = useCallback(() => fetchSentiment(), [])
  const { data, error, isLoading, lastUpdated } = usePolling<SentimentData>(
    fetcher,
    { interval: 60_000 }
  )

  return (
    <GlassPanel title="SENTIMENT ENGINE">
      {isLoading && !data && <LoadingSkeleton variant="chart" />}
      {error && !data && (
        <ErrorState message="Sentiment data unavailable" />
      )}

      {data && (
        <div className="flex flex-col gap-6">
          {/* Score + Label + ROC */}
          <div className="flex flex-col items-center gap-3">
            <SentimentGauge score={data.current_score} />

            <div className="flex items-center gap-3">
              <span
                className={`rounded-full border px-3 py-0.5 font-display text-[11px] font-bold uppercase tracking-wider ${sentimentBgColor(data.sentiment_label)}`}
              >
                {data.sentiment_label}
              </span>
              <RocIndicator roc={data.rate_of_change} direction={data.roc_direction} />
            </div>
          </div>

          {/* Volume comparison */}
          <VolumeBar
            today={data.mention_volume_today}
            avg={data.mention_volume_7d_avg}
            spike={data.volume_spike}
          />

          {/* History chart */}
          {data.history.length > 0 && <HistoryChart history={data.history} />}

          {/* Footer */}
          <div className="flex items-center justify-end">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default SentimentPanel
