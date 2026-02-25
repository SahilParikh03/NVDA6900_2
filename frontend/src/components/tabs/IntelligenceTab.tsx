import SentimentPanel from '../panels/SentimentPanel'
import EarningsConsensus from '../panels/EarningsConsensus'
import CapExTracker from '../panels/CapExTracker'
import AIKeywordScores from '../panels/AIKeywordScores'
import { ErrorBoundary } from '../ui'

function IntelligenceTab() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Row 1 */}
      <div className="animate-fade-in stagger-1">
        <ErrorBoundary>
          <SentimentPanel />
        </ErrorBoundary>
      </div>
      <div className="animate-fade-in stagger-2">
        <ErrorBoundary>
          <EarningsConsensus />
        </ErrorBoundary>
      </div>

      {/* Row 2 */}
      <div className="animate-fade-in stagger-3">
        <ErrorBoundary>
          <CapExTracker />
        </ErrorBoundary>
      </div>
      <div className="animate-fade-in stagger-4">
        <ErrorBoundary>
          <AIKeywordScores />
        </ErrorBoundary>
      </div>
    </div>
  )
}

export default IntelligenceTab
