import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchPredictions } from '../../api/client'
import type { PredictionsData, PredictionSignal } from '../../types/api'

function getDirectionColor(direction: PredictionSignal['direction']): string {
  if (direction === 'bullish') return 'text-nvda-green'
  if (direction === 'bearish') return 'text-red'
  return 'text-amber'
}

function getDirectionDot(direction: PredictionSignal['direction']): string {
  if (direction === 'bullish') return 'bg-nvda-green'
  if (direction === 'bearish') return 'bg-red'
  return 'bg-amber'
}

function getOutlookStyles(outlook: string): { bg: string; text: string; glow: string } {
  const lower = outlook.toLowerCase()
  if (lower === 'bullish') {
    return {
      bg: 'bg-nvda-green/15',
      text: 'text-nvda-green',
      glow: 'shadow-[0_0_20px_rgba(118,185,0,0.2)]',
    }
  }
  if (lower === 'bearish') {
    return {
      bg: 'bg-red/15',
      text: 'text-red',
      glow: 'shadow-[0_0_20px_rgba(255,59,59,0.2)]',
    }
  }
  return {
    bg: 'bg-amber/15',
    text: 'text-amber',
    glow: 'shadow-[0_0_20px_rgba(255,184,0,0.2)]',
  }
}

function getConfidenceLabel(confidence: string): string {
  const lower = confidence.toLowerCase()
  if (lower === 'high') return 'High'
  if (lower === 'moderate') return 'Moderate'
  return 'Low'
}

function PredictionsPanel() {
  const { data, error, isLoading, lastUpdated } = usePolling<PredictionsData>(
    fetchPredictions,
    { interval: 60000 }
  )

  if (isLoading && !data) {
    return (
      <GlassPanel title="PREDICTIONS">
        <LoadingSkeleton variant="line" lines={5} />
      </GlassPanel>
    )
  }

  if (error && !data) {
    return (
      <GlassPanel title="PREDICTIONS">
        <ErrorState message="Failed to load predictions" />
      </GlassPanel>
    )
  }

  if (!data) return null

  const outlookStyles = getOutlookStyles(data.outlook)

  return (
    <GlassPanel title="PREDICTIONS">
      <div className="flex flex-col gap-5">
        {/* Outlook badge */}
        <div className="flex flex-col items-center gap-2">
          <div
            className={`inline-flex rounded-lg px-6 py-2.5 ${outlookStyles.bg} ${outlookStyles.glow}`}
          >
            <span className={`font-display text-lg font-bold uppercase tracking-wider ${outlookStyles.text}`}>
              {data.outlook}
            </span>
          </div>
          <span className="font-data text-xs text-text-muted">
            Confidence: {getConfidenceLabel(data.confidence)}
          </span>
        </div>

        {/* Signals */}
        {data.signals.length > 0 ? (
          <div className="flex flex-col gap-1">
            <span className="mb-1 text-[10px] uppercase tracking-widest text-text-muted">
              Signal Breakdown
            </span>
            <div className="glass-panel-inner divide-y divide-border px-3">
              {data.signals.map((signal, i) => (
                <div key={i} className="flex items-center justify-between py-1.5">
                  <span className="text-xs uppercase tracking-wider text-text-muted">
                    {signal.factor}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className={`inline-block h-2 w-2 rounded-full ${getDirectionDot(signal.direction)}`} />
                    <span className={`font-data text-xs font-medium uppercase ${getDirectionColor(signal.direction)}`}>
                      {signal.direction}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 flex flex-col gap-1.5">
              {data.signals.map((signal, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-text-primary">
                  <span className={`mt-1.5 inline-block h-1 w-1 flex-shrink-0 rounded-full ${getDirectionDot(signal.direction)}`} />
                  <span className="text-xs text-text-secondary">{signal.detail}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1 py-4">
            <span className="text-xs text-text-muted">No signals available</span>
            <span className="text-[10px] text-text-muted/60">Waiting for data sources</span>
          </div>
        )}

        {/* Last updated */}
        <div className="flex justify-end">
          <LastUpdated timestamp={lastUpdated} />
        </div>
      </div>
    </GlassPanel>
  )
}

export default PredictionsPanel
