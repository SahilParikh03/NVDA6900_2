import GlassPanel from '../ui/GlassPanel'
import AlertBanner from '../ui/AlertBanner'

export interface Alert {
  id: string
  message: string
  type: 'positive' | 'negative'
  timestamp: string
  ticker: string
}

const MAX_ALERTS = 10

interface AlertFeedProps {
  alerts: Alert[]
}

function AlertFeed({ alerts }: AlertFeedProps) {
  const visibleAlerts = alerts.slice(0, MAX_ALERTS)

  return (
    <GlassPanel title="LIVE ALERTS">
      {visibleAlerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface">
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M9 2.25C9 2.25 3 6.75 3 10.5C3 13.8137 5.68629 15.75 9 15.75C12.3137 15.75 15 13.8137 15 10.5C15 6.75 9 2.25 9 2.25Z"
                stroke="#6B6B7B"
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <p className="text-sm text-text-muted">No alerts yet</p>
          <p className="mt-1 text-xs text-text-muted/60">
            Alerts will appear when significant price moves are detected
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {visibleAlerts.map((alert) => (
            <AlertBanner
              key={alert.id}
              message={`[${alert.ticker}] ${alert.message}`}
              type={alert.type}
              timestamp={alert.timestamp}
            />
          ))}
        </div>
      )}
    </GlassPanel>
  )
}

export default AlertFeed
