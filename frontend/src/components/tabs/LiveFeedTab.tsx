import TwitterFeed from '../panels/TwitterFeed'
import PolymarketLiveOdds from '../panels/PolymarketLiveOdds'
import NewsFeed from '../panels/NewsFeed'
import { ErrorBoundary } from '../ui'

function LiveFeedTab() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      {/* Left column: Twitter/News Feed — takes ~60% width (3 of 5 cols) */}
      <div className="lg:col-span-3 animate-fade-in stagger-1">
        <ErrorBoundary>
          <TwitterFeed />
        </ErrorBoundary>
      </div>

      {/* Right column: Polymarket + News — takes ~40% width (2 of 5 cols) */}
      <div className="lg:col-span-2 flex flex-col gap-6">
        <div className="animate-fade-in stagger-2">
          <ErrorBoundary>
            <PolymarketLiveOdds />
          </ErrorBoundary>
        </div>
        <div className="animate-fade-in stagger-3">
          <ErrorBoundary>
            <NewsFeed />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}

export default LiveFeedTab
