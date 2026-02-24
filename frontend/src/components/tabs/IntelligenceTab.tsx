import SentimentPanel from '../panels/SentimentPanel'
import EarningsConsensus from '../panels/EarningsConsensus'
import CapExTracker from '../panels/CapExTracker'
import AIKeywordScores from '../panels/AIKeywordScores'

function IntelligenceTab() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Row 1 */}
      <div className="animate-fade-in stagger-1">
        <SentimentPanel />
      </div>
      <div className="animate-fade-in stagger-2">
        <EarningsConsensus />
      </div>

      {/* Row 2 */}
      <div className="animate-fade-in stagger-3">
        <CapExTracker />
      </div>
      <div className="animate-fade-in stagger-4">
        <AIKeywordScores />
      </div>
    </div>
  )
}

export default IntelligenceTab
