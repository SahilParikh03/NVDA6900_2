import React, { useEffect, useState } from 'react'

interface LastUpdatedProps {
  timestamp: Date | null
  className?: string
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) {
    return `${seconds}s ago`
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    return `${minutes}m ago`
  }
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}

function LastUpdated({ timestamp, className = '' }: LastUpdatedProps) {
  const [, setTick] = useState(0)

  useEffect(() => {
    if (!timestamp) return

    const interval = setInterval(() => {
      setTick((prev) => prev + 1)
    }, 1000)

    return () => clearInterval(interval)
  }, [timestamp])

  if (!timestamp) return null

  const elapsed = Date.now() - timestamp.getTime()
  const label = `Updated ${formatElapsed(elapsed)}`

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-data text-xs text-text-muted ${className}`}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-nvda-green/60" />
      {label}
    </span>
  )
}

export default LastUpdated
