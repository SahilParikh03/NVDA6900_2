import React, { useEffect, useCallback, useRef, useState } from 'react'

interface AlertBannerProps {
  message: string
  type: 'positive' | 'negative'
  timestamp?: string
  onDismiss?: () => void
}

function AlertBanner({ message, type, timestamp, onDismiss }: AlertBannerProps) {
  const [dismissing, setDismissing] = useState(false)
  const animationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleDismiss = useCallback(() => {
    setDismissing(true)
    // Wait for the slide-out animation (300ms) to finish before calling onDismiss
    animationTimerRef.current = setTimeout(() => {
      onDismiss?.()
    }, 300)
  }, [onDismiss])

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    if (!onDismiss) return

    const autoTimeout = setTimeout(() => {
      handleDismiss()
    }, 5000)

    return () => clearTimeout(autoTimeout)
  }, [onDismiss, handleDismiss])

  // Cleanup animation timer on unmount
  useEffect(() => {
    return () => {
      if (animationTimerRef.current) {
        clearTimeout(animationTimerRef.current)
      }
    }
  }, [])

  const borderColor = type === 'positive' ? 'border-l-nvda-green' : 'border-l-red'
  const animationClass = dismissing
    ? 'animate-slide-out-right'
    : 'animate-slide-in-right'

  return (
    <div
      className={`glass-panel-inner flex items-center justify-between border-l-[3px] ${borderColor} px-4 py-2 ${animationClass}`}
      role="alert"
    >
      <p className="text-sm text-text-primary">{message}</p>

      <div className="flex items-center gap-3">
        {timestamp && (
          <span className="whitespace-nowrap font-data text-xs text-text-muted">
            {timestamp}
          </span>
        )}

        {onDismiss && (
          <button
            type="button"
            onClick={handleDismiss}
            className="ml-1 text-text-muted transition-colors duration-150 hover:text-text-primary"
            aria-label="Dismiss alert"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5"
                stroke="currentColor"
                strokeWidth="1.25"
                strokeLinecap="round"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

export default AlertBanner
