import HeroPrice from '../panels/HeroPrice'
import PredictionsPanel from '../panels/PredictionsPanel'
import EarningsCountdown from '../panels/EarningsCountdown'
import CorrelatedTickers from '../panels/CorrelatedTickers'
import AlertFeed from '../panels/AlertFeed'
import type { Alert } from '../panels/AlertFeed'

interface NVDACommandTabProps {
  alerts: Alert[]
}

function NVDACommandTab({ alerts }: NVDACommandTabProps) {
  return (
    <div className="flex flex-col gap-6">
      {/* Row 1: Hero price — full width */}
      <div className="animate-fade-in stagger-1">
        <HeroPrice />
      </div>

      {/* Row 2: Predictions + Earnings Countdown — side by side */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="animate-fade-in stagger-2">
          <PredictionsPanel />
        </div>
        <div className="animate-fade-in stagger-3">
          <EarningsCountdown />
        </div>
      </div>

      {/* Row 3: Correlated tickers — full width */}
      <div className="animate-fade-in stagger-4">
        <CorrelatedTickers />
      </div>

      {/* Row 4: Alert feed — full width */}
      <div className="animate-fade-in stagger-5">
        <AlertFeed alerts={alerts} />
      </div>
    </div>
  )
}

export default NVDACommandTab
