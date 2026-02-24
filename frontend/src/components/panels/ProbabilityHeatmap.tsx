import { useCallback } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts'
import { fetchHeatmap } from '../../api/client'
import usePolling from '../../hooks/usePolling'
import { GlassPanel, LoadingSkeleton, ErrorState, LastUpdated } from '../ui'
import type { PolymarketMarket } from '../../types/api'

interface ChartDatum {
  strike: string
  strikeNum: number
  probability: number
  question: string
  volume: number
  liquidity: number
}

function getProbabilityColor(probability: number): string {
  if (probability > 60) return '#76B900'
  if (probability > 30) return 'rgba(118,185,0,0.5)'
  return 'rgba(118,185,0,0.2)'
}

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toFixed(0)}`
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload: ChartDatum }>
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const datum = payload[0].payload

  return (
    <div className="glass-panel-inner px-4 py-3 border border-border-hover">
      <p className="font-body text-xs text-text-primary mb-1">{datum.question}</p>
      <div className="flex flex-col gap-1">
        <span className="font-data text-sm text-nvda-green">
          {datum.probability.toFixed(1)}%
        </span>
        <span className="font-data text-xs text-text-muted">
          Vol: {formatCurrency(datum.volume)}
        </span>
        <span className="font-data text-xs text-text-muted">
          Liq: {formatCurrency(datum.liquidity)}
        </span>
      </div>
    </div>
  )
}

function ProbabilityHeatmap() {
  const fetcher = useCallback(() => fetchHeatmap(), [])
  const { data, error, isLoading, lastUpdated } = usePolling(fetcher, {
    interval: 30000,
  })

  return (
    <GlassPanel title="PROBABILITY HEATMAP">
      {isLoading && <LoadingSkeleton variant="chart" />}

      {!isLoading && error && (
        <ErrorState message="Failed to load probability data" />
      )}

      {!isLoading && !error && data && (
        <HeatmapChart
          markets={data.markets}
          expectedLevel={data.expected_level}
          maxConviction={data.max_conviction}
          lastUpdated={lastUpdated}
        />
      )}
    </GlassPanel>
  )
}

interface HeatmapChartProps {
  markets: PolymarketMarket[]
  expectedLevel: number
  maxConviction: number
  lastUpdated: Date | null
}

function HeatmapChart({
  markets,
  expectedLevel,
  maxConviction,
  lastUpdated,
}: HeatmapChartProps) {
  const chartData: ChartDatum[] = markets
    .slice()
    .sort((a, b) => a.strike_price - b.strike_price)
    .map((m) => ({
      strike: `$${m.strike_price}`,
      strikeNum: m.strike_price,
      probability: m.probability * 100,
      question: m.question,
      volume: m.volume,
      liquidity: m.liquidity,
    }))

  const maxConvictionLabel = `$${maxConviction}`

  const chartHeight = Math.max(300, chartData.length * 40)

  return (
    <div className="flex flex-col gap-4">
      {/* Summary stats */}
      <div className="flex items-center gap-6 flex-wrap">
        <div className="flex flex-col">
          <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
            Expected Level
          </span>
          <span className="font-data text-lg text-nvda-green text-glow">
            ${expectedLevel.toLocaleString()}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
            Max Conviction
          </span>
          <span className="font-data text-lg text-nvda-green text-glow">
            ${maxConviction.toLocaleString()}
          </span>
        </div>
        <div className="ml-auto">
          <LastUpdated timestamp={lastUpdated} />
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: chartHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 8, right: 24, left: 12, bottom: 8 }}
            barCategoryGap="20%"
          >
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fill: '#6B6B7B', fontSize: 10, fontFamily: 'JetBrains Mono' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="strike"
              tick={{ fill: '#6B6B7B', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              axisLine={false}
              tickLine={false}
              width={60}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: 'rgba(118,185,0,0.04)' }}
            />
            <ReferenceLine
              y={`$${expectedLevel}`}
              stroke="rgba(118,185,0,0.4)"
              strokeDasharray="4 4"
              label={{
                value: 'EXPECTED',
                position: 'right',
                fill: '#6B6B7B',
                fontSize: 9,
                fontFamily: 'Orbitron',
              }}
            />
            <Bar dataKey="probability" radius={[0, 4, 4, 0]} maxBarSize={28}>
              {chartData.map((entry) => (
                <Cell
                  key={entry.strike}
                  fill={getProbabilityColor(entry.probability)}
                  stroke={
                    entry.strike === maxConvictionLabel
                      ? '#76B900'
                      : 'transparent'
                  }
                  strokeWidth={entry.strike === maxConvictionLabel ? 2 : 0}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-text-muted">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: '#76B900' }} />
          <span className="font-data text-[10px]">&gt;60%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: 'rgba(118,185,0,0.5)' }} />
          <span className="font-data text-[10px]">30-60%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: 'rgba(118,185,0,0.2)' }} />
          <span className="font-data text-[10px]">&lt;30%</span>
        </div>
        <div className="flex items-center gap-1.5 ml-2">
          <span className="inline-block h-0.5 w-4 border-t border-dashed border-nvda-green/40" />
          <span className="font-data text-[10px]">Expected</span>
        </div>
      </div>
    </div>
  )
}

export default ProbabilityHeatmap
