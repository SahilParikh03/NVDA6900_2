import TickerDashboard from '../panels/TickerDashboard'
import PerformanceTable from '../panels/PerformanceTable'

function EcosystemTab() {
  return (
    <div className="flex flex-col gap-6">
      <div className="animate-fade-in stagger-1">
        <TickerDashboard />
      </div>
      <div className="animate-fade-in stagger-2">
        <PerformanceTable />
      </div>
    </div>
  )
}

export default EcosystemTab
