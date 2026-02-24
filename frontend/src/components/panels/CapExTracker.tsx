import { useCallback, useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchCapex } from '../../api/client'
import type { CapexData, CapexCompany } from '../../types/api'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Distinct shades for each company — greens, teals, cyans */
const COMPANY_COLORS: Record<string, string> = {
  GOOGL: '#76B900',
  MSFT: '#4CAF50',
  AAPL: '#00BFA5',
  AMZN: '#26C6DA',
  META: '#66BB6A',
}

const DEFAULT_COLORS = [
  '#76B900',
  '#4CAF50',
  '#00BFA5',
  '#26C6DA',
  '#66BB6A',
  '#81C784',
  '#00E5FF',
  '#A5D6A7',
]

function getCompanyColor(symbol: string, index: number): string {
  return COMPANY_COLORS[symbol] ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function trendBadgeClass(trend: string): string {
  const lower = trend.toLowerCase()
  if (lower === 'increasing') return 'bg-nvda-green/15 border-nvda-green/30 text-nvda-green'
  if (lower === 'decreasing') return 'bg-red/15 border-red/30 text-red'
  return 'bg-amber/15 border-amber/30 text-amber'
}

function formatQoQ(value: number | null): string {
  if (value === null) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function qoqColor(value: number | null): string {
  if (value === null) return 'text-text-muted'
  return value >= 0 ? 'text-nvda-green' : 'text-red'
}

// ---------------------------------------------------------------------------
// Chart data transform
// ---------------------------------------------------------------------------

interface ChartRow {
  quarter: string
  [symbol: string]: string | number
}

function buildChartData(companies: CapexCompany[]): ChartRow[] {
  // Collect all unique quarters across companies
  const quarterSet = new Set<string>()
  for (const company of companies) {
    for (const q of company.quarters) {
      quarterSet.add(q.period)
    }
  }

  const quarters = [...quarterSet].sort()

  return quarters.map((quarter) => {
    const row: ChartRow = { quarter }
    for (const company of companies) {
      const match = company.quarters.find((q) => q.period === quarter)
      row[company.symbol] = match ? match.capex_to_revenue : 0
    }
    return row
  })
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface TooltipEntry {
  value: number
  name: string
  color: string
}

interface ChartTooltipProps {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div className="glass-panel-inner px-3 py-2">
      <p className="mb-1 font-data text-xs text-text-muted">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-sm"
            style={{ backgroundColor: entry.color }}
          />
          <span className="font-data text-xs text-text-primary">
            {entry.name}:
          </span>
          <span className="font-data text-xs text-nvda-green tabular-nums">
            {(entry.value * 100).toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function CapExTracker() {
  const fetcher = useCallback(() => fetchCapex(), [])
  const { data, error, isLoading, lastUpdated } = usePolling<CapexData>(
    fetcher,
    { interval: 86_400_000 }
  )

  const chartData = useMemo(
    () => (data ? buildChartData(data.companies) : []),
    [data]
  )

  const symbols = useMemo(
    () => (data ? data.companies.map((c) => c.symbol) : []),
    [data]
  )

  return (
    <GlassPanel title="HYPERSCALER CAPEX">
      {isLoading && !data && <LoadingSkeleton variant="chart" />}
      {error && !data && (
        <ErrorState message="CapEx data unavailable" />
      )}

      {data && (
        <div className="flex flex-col gap-5">
          {/* Aggregate trend badge */}
          <div className="flex items-center gap-3">
            <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
              Aggregate Trend
            </span>
            <span
              className={`rounded-full border px-3 py-0.5 font-display text-[11px] font-bold uppercase tracking-wider ${trendBadgeClass(data.aggregate_trend)}`}
            >
              {data.aggregate_trend}
            </span>
          </div>

          {/* Grouped bar chart */}
          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={chartData}
                margin={{ top: 8, right: 8, bottom: 8, left: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(118,185,0,0.06)"
                  vertical={false}
                />
                <XAxis
                  dataKey="quarter"
                  tick={{
                    fontSize: 10,
                    fill: '#6B6B7B',
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{
                    fontSize: 10,
                    fill: '#6B6B7B',
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                  width={40}
                  tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono' }}
                  iconSize={8}
                />
                {symbols.map((symbol, idx) => (
                  <Bar
                    key={symbol}
                    dataKey={symbol}
                    fill={getCompanyColor(symbol, idx)}
                    radius={[2, 2, 0, 0]}
                    maxBarSize={24}
                    animationDuration={600}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}

          {/* QoQ growth indicators */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-5">
            {data.companies.map((company, idx) => {
              const latestQ =
                company.quarters.length > 0
                  ? company.quarters[company.quarters.length - 1]
                  : null
              return (
                <div
                  key={company.symbol}
                  className="flex items-center gap-2"
                >
                  <span
                    className="inline-block h-2 w-2 rounded-sm"
                    style={{ backgroundColor: getCompanyColor(company.symbol, idx) }}
                  />
                  <span className="font-data text-xs text-text-primary">
                    {company.symbol}
                  </span>
                  <span
                    className={`font-data text-xs tabular-nums ${qoqColor(latestQ?.capex_qoq_growth ?? null)}`}
                  >
                    {formatQoQ(latestQ?.capex_qoq_growth ?? null)}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default CapExTracker
