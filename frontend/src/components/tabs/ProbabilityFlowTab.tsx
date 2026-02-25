import ProbabilityHeatmap from '../panels/ProbabilityHeatmap'
import SupplementaryMarkets from '../panels/SupplementaryMarkets'
import { ErrorBoundary } from '../ui'

function ProbabilityFlowTab() {
  return (
    <div className="flex flex-col gap-6">
      <div className="animate-fade-in stagger-1">
        <ErrorBoundary>
          <ProbabilityHeatmap />
        </ErrorBoundary>
      </div>
      <div className="animate-fade-in stagger-2">
        <ErrorBoundary>
          <SupplementaryMarkets />
        </ErrorBoundary>
      </div>
    </div>
  )
}

export default ProbabilityFlowTab
