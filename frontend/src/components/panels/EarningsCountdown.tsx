import { useState, useEffect, useMemo } from 'react'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import usePolling from '../../hooks/usePolling'
import { fetchEarningsCalendar } from '../../api/client'
import type { EarningsCalendarEntry } from '../../types/api'

interface TimeRemaining {
  days: number
  hours: number
  minutes: number
  seconds: number
  total: number
}

function computeTimeRemaining(targetDate: Date): TimeRemaining {
  const now = Date.now()
  const diff = targetDate.getTime() - now

  if (diff <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, total: diff }
  }

  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((diff % (1000 * 60)) / 1000)

  return { days, hours, minutes, seconds, total: diff }
}

function padTwo(n: number): string {
  return n.toString().padStart(2, '0')
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T17:00:00-05:00')
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

interface CountdownUnitProps {
  value: string
  label: string
}

function CountdownUnit({ value, label }: CountdownUnitProps) {
  return (
    <div className="glass-panel-inner flex flex-col items-center px-4 py-3">
      <span className="font-data text-3xl font-bold text-text-primary">
        {value}
      </span>
      <span className="mt-1 text-[10px] uppercase tracking-widest text-text-muted">
        {label}
      </span>
    </div>
  )
}

function EarningsCountdown() {
  const { data, error, isLoading } = usePolling<EarningsCalendarEntry | null>(
    fetchEarningsCalendar,
    { interval: 86400000 }
  )

  const [timeRemaining, setTimeRemaining] = useState<TimeRemaining | null>(null)

  // Earnings release: 2:00 PM PT / 5:00 PM ET (right after NYSE close)
  const earningsDate = useMemo(() => {
    if (!data?.date) return null
    return new Date(data.date + 'T17:00:00-05:00')
  }, [data?.date])

  useEffect(() => {
    if (!earningsDate) return

    const update = () => {
      setTimeRemaining(computeTimeRemaining(earningsDate))
    }

    update()
    const interval = setInterval(update, 1000)

    return () => clearInterval(interval)
  }, [earningsDate])

  if (isLoading && !data) {
    return (
      <GlassPanel title="EARNINGS COUNTDOWN">
        <LoadingSkeleton variant="line" lines={3} />
      </GlassPanel>
    )
  }

  if (error && !data) {
    return (
      <GlassPanel title="EARNINGS COUNTDOWN">
        <ErrorState message="Failed to load earnings calendar" />
      </GlassPanel>
    )
  }

  if (!isLoading && !data) {
    return (
      <GlassPanel title="EARNINGS COUNTDOWN">
        <div className="flex flex-col items-center gap-2 py-4">
          <span className="text-xs uppercase tracking-wider text-text-muted">
            No upcoming NVDA earnings date available
          </span>
        </div>
      </GlassPanel>
    )
  }

  // Earnings date has passed
  const isPast = timeRemaining !== null && timeRemaining.total <= 0

  if (isPast && data) {
    const hasBeatData = data.eps !== null && data.epsEstimated !== null
    const beat = hasBeatData ? (data.eps as number) > (data.epsEstimated as number) : null

    return (
      <GlassPanel title="EARNINGS COUNTDOWN">
        <div className="flex flex-col items-center gap-4 py-2">
          <span className="text-xs uppercase tracking-wider text-text-muted">
            Last Reported
          </span>
          <span className="font-data text-sm text-text-primary">
            {formatDate(data.date)}
          </span>
          {hasBeatData && (
            <div className="flex flex-col items-center gap-2">
              <span
                className={`font-display text-sm font-bold uppercase tracking-wider ${
                  beat ? 'text-nvda-green' : 'text-red'
                }`}
              >
                {beat ? 'BEAT' : 'MISS'}
              </span>
              <div className="flex gap-6 text-center">
                <div className="flex flex-col">
                  <span className="text-[10px] uppercase tracking-wider text-text-muted">
                    Actual EPS
                  </span>
                  <span className="font-data text-sm text-text-primary">
                    {data.eps != null ? `$${(data.eps as number).toFixed(2)}` : '—'}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] uppercase tracking-wider text-text-muted">
                    Estimated EPS
                  </span>
                  <span className="font-data text-sm text-text-primary">
                    {data.epsEstimated != null ? `$${(data.epsEstimated as number).toFixed(2)}` : '—'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </GlassPanel>
    )
  }

  return (
    <GlassPanel title="EARNINGS COUNTDOWN">
      <div className="flex flex-col items-center gap-4">
        {data?.date && (
          <span className="text-xs text-text-muted">
            {formatDate(data.date)}
          </span>
        )}
        <div className="grid grid-cols-4 gap-3">
          <CountdownUnit value={padTwo(timeRemaining?.days ?? 0)} label="Days" />
          <CountdownUnit value={padTwo(timeRemaining?.hours ?? 0)} label="Hours" />
          <CountdownUnit value={padTwo(timeRemaining?.minutes ?? 0)} label="Min" />
          <CountdownUnit value={padTwo(timeRemaining?.seconds ?? 0)} label="Sec" />
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-surface">
          <div
            className="h-full rounded-full bg-nvda-green/40 transition-all duration-1000"
            style={{
              width: timeRemaining && earningsDate
                ? `${Math.max(0, Math.min(100, 100 - (timeRemaining.total / (30 * 24 * 60 * 60 * 1000)) * 100))}%`
                : '0%',
            }}
          />
        </div>
      </div>
    </GlassPanel>
  )
}

export default EarningsCountdown
