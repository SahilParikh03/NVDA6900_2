import ProbabilityHeatmap from '../panels/ProbabilityHeatmap'
import SupplementaryMarkets from '../panels/SupplementaryMarkets'

function ProbabilityFlowTab() {
  return (
    <div className="flex flex-col gap-6">
      <div className="animate-fade-in stagger-1">
        <ProbabilityHeatmap />
      </div>
      <div className="animate-fade-in stagger-2">
        <SupplementaryMarkets />
      </div>
    </div>
  )
}

export default ProbabilityFlowTab
