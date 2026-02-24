import TwitterFeed from '../panels/TwitterFeed'
import PolymarketLiveOdds from '../panels/PolymarketLiveOdds'
import NewsFeed from '../panels/NewsFeed'

function LiveFeedTab() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      {/* Left column: Twitter/News Feed — takes ~60% width (3 of 5 cols) */}
      <div className="lg:col-span-3 animate-fade-in stagger-1">
        <TwitterFeed />
      </div>

      {/* Right column: Polymarket + News — takes ~40% width (2 of 5 cols) */}
      <div className="lg:col-span-2 flex flex-col gap-6">
        <div className="animate-fade-in stagger-2">
          <PolymarketLiveOdds />
        </div>
        <div className="animate-fade-in stagger-3">
          <NewsFeed />
        </div>
      </div>
    </div>
  )
}

export default LiveFeedTab
