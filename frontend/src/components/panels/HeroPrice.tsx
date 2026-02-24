import { useRef, useEffect, useState, useCallback } from 'react'
import { createChart, CandlestickData, IChartApi, ISeriesApi, Time } from 'lightweight-charts'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchPrice, fetchPriceHistory } from '../../api/client'
import type { PriceQuote, PriceHistoryEntry } from '../../types/api'

function formatVolume(vol: number): string {
  if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(2)}B`
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(2)}M`
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`
  return vol.toLocaleString()
}

function formatMarketCap(cap: number): string {
  if (cap >= 1_000_000_000_000) return `$${(cap / 1_000_000_000_000).toFixed(2)}T`
  if (cap >= 1_000_000_000) return `$${(cap / 1_000_000_000).toFixed(2)}B`
  return `$${(cap / 1_000_000).toFixed(2)}M`
}

function mapHistoryToCandles(entries: PriceHistoryEntry[]): CandlestickData<Time>[] {
  return entries
    .map((entry) => ({
      time: entry.date as Time,
      open: entry.open,
      high: entry.high,
      low: entry.low,
      close: entry.close,
    }))
    .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
}

function HeroPrice() {
  const { data: price, error: priceError, isLoading: priceLoading, lastUpdated } = usePolling<PriceQuote>(
    fetchPrice,
    { interval: 5000 }
  )

  const [history, setHistory] = useState<PriceHistoryEntry[] | null>(null)
  const [historyError, setHistoryError] = useState<Error | null>(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [prevPrice, setPrevPrice] = useState<number | null>(null)
  const [flashClass, setFlashClass] = useState('')

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  // Track price changes for flash animation
  useEffect(() => {
    if (price && prevPrice !== null && price.price !== prevPrice) {
      const cls = price.price > prevPrice ? 'price-flash-green' : 'price-flash-red'
      setFlashClass(cls)
      const timer = setTimeout(() => setFlashClass(''), 600)
      return () => clearTimeout(timer)
    }
    if (price) {
      setPrevPrice(price.price)
    }
  }, [price, prevPrice])

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const data = await fetchPriceHistory()
      setHistory(data)
      setHistoryError(null)
    } catch (err) {
      setHistoryError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  // Load history once
  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 320,
      layout: {
        background: { color: 'transparent' },
        textColor: '#6B6B7B',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(118, 185, 0, 0.04)' },
        horzLines: { color: 'rgba(118, 185, 0, 0.04)' },
      },
      crosshair: {
        vertLine: { color: 'rgba(118, 185, 0, 0.2)', width: 1 },
        horzLine: { color: 'rgba(118, 185, 0, 0.2)', width: 1 },
      },
      rightPriceScale: {
        borderColor: 'rgba(118, 185, 0, 0.08)',
      },
      timeScale: {
        borderColor: 'rgba(118, 185, 0, 0.08)',
        timeVisible: false,
      },
    })

    const series = chart.addCandlestickSeries({
      upColor: '#76B900',
      downColor: '#FF3B3B',
      borderUpColor: '#76B900',
      borderDownColor: '#FF3B3B',
      wickUpColor: '#76B900',
      wickDownColor: '#FF3B3B',
    })

    chartRef.current = chart
    seriesRef.current = series

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  // Update chart data when history loads
  useEffect(() => {
    if (history && seriesRef.current) {
      const candles = mapHistoryToCandles(history)
      seriesRef.current.setData(candles)
      chartRef.current?.timeScale().fitContent()
    }
  }, [history])

  const isLoading = priceLoading && !price
  const error = priceError || historyError

  if (isLoading) {
    return (
      <GlassPanel>
        <LoadingSkeleton variant="chart" />
      </GlassPanel>
    )
  }

  if (error && !price) {
    return (
      <GlassPanel>
        <ErrorState
          message={error.message || 'Failed to load price data'}
          onRetry={loadHistory}
        />
      </GlassPanel>
    )
  }

  const isPositive = price ? price.change >= 0 : true
  const changeColor = isPositive ? 'text-nvda-green' : 'text-red'
  const changeSign = isPositive ? '+' : ''

  return (
    <GlassPanel className="relative">
      <div className="flex flex-col gap-6">
        {/* Price header row */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          {/* Left: ticker + price */}
          <div className="flex flex-col gap-1">
            <span className="font-display text-sm font-bold uppercase tracking-wider text-nvda-green text-glow">
              NVDA
            </span>
            <div className="flex items-baseline gap-4">
              <span className={`font-data text-5xl font-bold text-text-primary ${flashClass}`}>
                ${price?.price.toFixed(2) ?? '—'}
              </span>
              <div className="flex items-baseline gap-2">
                <span className={`font-data text-lg font-semibold ${changeColor}`}>
                  {changeSign}{price?.change.toFixed(2) ?? '—'}
                </span>
                <span className={`font-data text-lg ${changeColor}`}>
                  ({changeSign}{price?.changePercentage.toFixed(2) ?? '—'}%)
                </span>
              </div>
            </div>
          </div>

          {/* Right: volume + metrics */}
          <div className="flex flex-wrap items-end gap-6">
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-wider text-text-muted">Volume</span>
              <span className="font-data text-sm text-text-primary">
                {price ? formatVolume(price.volume) : '—'}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-wider text-text-muted">Mkt Cap</span>
              <span className="font-data text-sm text-text-primary">
                {price ? formatMarketCap(price.marketCap) : '—'}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-wider text-text-muted">Day Range</span>
              <span className="font-data text-sm text-text-primary">
                ${price?.dayLow.toFixed(2) ?? '—'} — ${price?.dayHigh.toFixed(2) ?? '—'}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase tracking-wider text-text-muted">Open</span>
              <span className="font-data text-sm text-text-primary">
                ${price?.open.toFixed(2) ?? '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Candlestick chart */}
        <div className="relative">
          {historyLoading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <LoadingSkeleton variant="chart" />
            </div>
          )}
          <div
            ref={chartContainerRef}
            className={`w-full ${historyLoading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
          />
          {historyError && !historyLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <ErrorState
                message="Failed to load chart data"
                onRetry={loadHistory}
              />
            </div>
          )}
        </div>
      </div>

      {/* Last updated indicator */}
      <div className="mt-4 flex justify-end">
        <LastUpdated timestamp={lastUpdated} />
      </div>
    </GlassPanel>
  )
}

export default HeroPrice
