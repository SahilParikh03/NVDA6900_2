import { useState, useCallback, useMemo } from 'react'
import { fetchPriceChange } from '../../api/client'
import usePolling from '../../hooks/usePolling'
import { GlassPanel, LoadingSkeleton, ErrorState, LastUpdated } from '../ui'
import type { PriceChange } from '../../types/api'

// TODO: extend /api/price/change endpoint for multi-symbol support

type PeriodKey = '1D' | '5D' | '1M' | '3M' | 'ytd'

interface ColumnDef {
  key: PeriodKey
  label: string
}

const COLUMNS: ColumnDef[] = [
  { key: '1D', label: '1D' },
  { key: '5D', label: '5D' },
  { key: '1M', label: '1M' },
  { key: '3M', label: '3M' },
  { key: 'ytd', label: 'YTD' },
]

interface TickerRow {
  symbol: string
  displayName?: string
  category: string
}

const TICKERS: TickerRow[] = [
  { symbol: 'NVDA', category: 'PRIMARY' },
  { symbol: 'GOOGL', category: 'HYPERSCALER' },
  { symbol: 'MSFT', category: 'HYPERSCALER' },
  { symbol: 'AAPL', category: 'HYPERSCALER' },
  { symbol: 'AMZN', category: 'HYPERSCALER' },
  { symbol: 'META', category: 'HYPERSCALER' },
  { symbol: 'AMD', category: 'SEMICONDUCTOR' },
  { symbol: 'INTC', category: 'SEMICONDUCTOR' },
  { symbol: 'TSM', category: 'MANUFACTURING' },
  { symbol: '005930.KS', displayName: 'Samsung', category: 'MANUFACTURING' },
  { symbol: 'BTC-USD', displayName: 'BTC', category: 'CRYPTO' },
]

type SortDir = 'asc' | 'desc'

interface SortState {
  key: PeriodKey | 'symbol'
  dir: SortDir
}

function getCellColor(value: number | null): string {
  if (value === null) return 'text-text-muted'
  if (value > 0) {
    const intensity = Math.min(value / 20, 1)
    return intensity > 0.5 ? 'text-nvda-green text-glow' : 'text-nvda-green'
  }
  if (value < 0) {
    const intensity = Math.min(Math.abs(value) / 20, 1)
    return intensity > 0.5 ? 'text-red' : 'text-red/80'
  }
  return 'text-text-muted'
}

function getCellBg(value: number | null): string {
  if (value === null) return ''
  if (value > 0) {
    const alpha = Math.min(value / 30, 0.15)
    return `rgba(118,185,0,${alpha.toFixed(3)})`
  }
  if (value < 0) {
    const alpha = Math.min(Math.abs(value) / 30, 0.15)
    return `rgba(255,59,59,${alpha.toFixed(3)})`
  }
  return ''
}

function formatChange(value: number | null): string {
  if (value === null) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function getValue(
  symbol: string,
  key: PeriodKey,
  nvdaData: PriceChange | null
): number | null {
  if (symbol !== 'NVDA' || !nvdaData) return null
  return nvdaData[key]
}

function PerformanceTable() {
  const fetcher = useCallback(() => fetchPriceChange(), [])
  const { data: nvdaChange, error, isLoading, lastUpdated } = usePolling(fetcher, {
    interval: 60000,
  })

  const [sort, setSort] = useState<SortState>({ key: 'symbol', dir: 'asc' })

  const sortedTickers = useMemo(() => {
    const rows = [...TICKERS]

    if (sort.key === 'symbol') {
      rows.sort((a, b) => {
        const nameA = a.displayName ?? a.symbol
        const nameB = b.displayName ?? b.symbol
        return sort.dir === 'asc'
          ? nameA.localeCompare(nameB)
          : nameB.localeCompare(nameA)
      })
    } else {
      const periodKey = sort.key
      rows.sort((a, b) => {
        const aVal = getValue(a.symbol, periodKey, nvdaChange)
        const bVal = getValue(b.symbol, periodKey, nvdaChange)
        if (aVal === null && bVal === null) return 0
        if (aVal === null) return 1
        if (bVal === null) return -1
        return sort.dir === 'asc' ? aVal - bVal : bVal - aVal
      })
    }

    return rows
  }, [sort, nvdaChange])

  function handleSort(key: PeriodKey | 'symbol') {
    setSort((prev) => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }))
  }

  function renderSortIndicator(key: PeriodKey | 'symbol') {
    if (sort.key !== key) return null
    return (
      <span className="ml-1 text-nvda-green">
        {sort.dir === 'asc' ? '\u25B2' : '\u25BC'}
      </span>
    )
  }

  return (
    <GlassPanel title="PERFORMANCE COMPARISON">
      {isLoading && <LoadingSkeleton variant="chart" />}

      {!isLoading && error && (
        <ErrorState message="Failed to load performance data" />
      )}

      {!isLoading && !error && (
        <div className="flex flex-col gap-4">
          <div className="glass-panel-inner overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th
                    className="px-4 py-3 text-left font-display text-[10px] uppercase tracking-wider text-text-muted cursor-pointer hover:text-text-primary transition-colors select-none"
                    onClick={() => handleSort('symbol')}
                  >
                    Symbol{renderSortIndicator('symbol')}
                  </th>
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      className="px-4 py-3 text-right font-display text-[10px] uppercase tracking-wider text-text-muted cursor-pointer hover:text-text-primary transition-colors select-none"
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}{renderSortIndicator(col.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedTickers.map((ticker) => (
                  <tr
                    key={ticker.symbol}
                    className="border-b border-border/50 hover:bg-surface-hover transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-display text-xs tracking-wider text-text-primary">
                        {ticker.displayName ?? ticker.symbol}
                      </span>
                    </td>
                    {COLUMNS.map((col) => {
                      const value = getValue(ticker.symbol, col.key, nvdaChange)
                      const bg = getCellBg(value)
                      return (
                        <td
                          key={col.key}
                          className={`px-4 py-2.5 text-right font-data text-xs ${getCellColor(value)}`}
                          style={bg ? { backgroundColor: bg } : undefined}
                        >
                          {formatChange(value)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default PerformanceTable
