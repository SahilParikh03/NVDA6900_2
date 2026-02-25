import { useState, useEffect, useRef, useCallback } from 'react'
import TabNav from './components/layout/TabNav'
import NVDACommandTab from './components/tabs/NVDACommandTab'
import ProbabilityFlowTab from './components/tabs/ProbabilityFlowTab'
import EcosystemTab from './components/tabs/EcosystemTab'
import IntelligenceTab from './components/tabs/IntelligenceTab'
import LiveFeedTab from './components/tabs/LiveFeedTab'
import AlertBanner from './components/ui/AlertBanner'
import usePolling from './hooks/usePolling'
import { fetchPrice } from './api/client'
import type { Alert } from './components/panels/AlertFeed'

const TABS = [
  { id: 'nvda-command', label: 'NVDA COMMAND' },
  { id: 'probability', label: 'PROBABILITY & FLOW' },
  { id: 'ecosystem', label: 'AI ECOSYSTEM' },
  { id: 'intelligence', label: 'INTELLIGENCE' },
  { id: 'live-feed', label: 'LIVE FEED' },
] as const

type TabId = (typeof TABS)[number]['id']

const ALERT_THRESHOLD = 1.0
const MAX_FEED_ALERTS = 10
const MAX_OVERLAY_ALERTS = 3

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('nvda-command')
  const [clock, setClock] = useState<string>(() => formatTime(new Date()))
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [overlayAlerts, setOverlayAlerts] = useState<Alert[]>([])
  const alertedRef = useRef<Set<string>>(new Set())

  // Live clock
  useEffect(() => {
    const interval = setInterval(() => {
      setClock(formatTime(new Date()))
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  // Poll NVDA price for alert detection
  const { data: nvdaPrice } = usePolling(fetchPrice, { interval: 5000 })

  // Alert detection — fire when |changePercentage| crosses a new 1% threshold boundary
  useEffect(() => {
    if (!nvdaPrice) return

    const { symbol, changePercentage } = nvdaPrice
    const absChange = Math.abs(changePercentage)
    if (absChange < ALERT_THRESHOLD) return

    const direction: 'positive' | 'negative' =
      changePercentage >= 0 ? 'positive' : 'negative'
    // Key on direction + floored percentage so we alert once per threshold crossing
    const alertKey = `${symbol}-${direction}-${Math.floor(absChange)}`

    if (alertedRef.current.has(alertKey)) return
    alertedRef.current.add(alertKey)

    const dirLabel = direction === 'positive' ? 'UP' : 'DOWN'
    const newAlert: Alert = {
      id: crypto.randomUUID(),
      message: `${dirLabel} ${absChange.toFixed(1)}%`,
      type: direction,
      timestamp: new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }),
      ticker: symbol,
    }

    setAlerts((prev) => [newAlert, ...prev].slice(0, MAX_FEED_ALERTS))
    setOverlayAlerts((prev) => [newAlert, ...prev].slice(0, MAX_OVERLAY_ALERTS))
  }, [nvdaPrice])

  // Dismiss overlay alert (auto-dismiss handled by AlertBanner, this removes from state)
  const dismissOverlayAlert = useCallback((id: string) => {
    setOverlayAlerts((prev) => prev.filter((a) => a.id !== id))
  }, [])

  return (
    <div className="bg-base bg-grid bg-grain min-h-screen relative">
      {/* Top bar — sticky glass nav */}
      <header className="sticky top-0 z-40 glass-panel-inner border-b border-border px-6 py-3">
        <div className="flex items-center justify-between gap-6">
          {/* Left: Logo */}
          <div className="flex-shrink-0">
            <h1 className="font-display text-nvda-green text-glow font-bold text-lg tracking-wider select-none">
              NVDA6900
            </h1>
          </div>

          {/* Center: Tab navigation */}
          <div className="flex-1 flex justify-center overflow-x-auto scrollbar-none">
            <TabNav
              tabs={[...TABS]}
              activeTab={activeTab}
              onTabChange={(tabId) => setActiveTab(tabId as TabId)}
            />
          </div>

          {/* Right: Live clock */}
          <div className="flex-shrink-0">
            <time className="font-data text-text-muted text-sm tabular-nums">
              {clock}
            </time>
          </div>
        </div>
      </header>

      {/* Content area — key forces re-mount on tab switch, triggering crossfade animation */}
      <main key={activeTab} className="relative z-10 p-6 animate-crossfade-in">
        {activeTab === 'nvda-command' && <NVDACommandTab alerts={alerts} />}
        {activeTab === 'probability' && <ProbabilityFlowTab />}
        {activeTab === 'ecosystem' && <EcosystemTab />}
        {activeTab === 'intelligence' && <IntelligenceTab />}
        {activeTab === 'live-feed' && <LiveFeedTab />}
      </main>

      {/* Alert overlay zone — slide-in alerts stacked top-right */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {overlayAlerts.map((alert) => (
          <AlertBanner
            key={alert.id}
            message={`${alert.ticker} ${alert.message}`}
            type={alert.type}
            timestamp={alert.timestamp}
            onDismiss={() => dismissOverlayAlert(alert.id)}
          />
        ))}
      </div>
    </div>
  )
}

export default App
