import { useState, useEffect } from 'react'
import TabNav from './components/layout/TabNav'
import NVDACommandTab from './components/tabs/NVDACommandTab'
import ProbabilityFlowTab from './components/tabs/ProbabilityFlowTab'
import EcosystemTab from './components/tabs/EcosystemTab'
import IntelligenceTab from './components/tabs/IntelligenceTab'
import LiveFeedTab from './components/tabs/LiveFeedTab'

const TABS = [
  { id: 'nvda-command', label: 'NVDA COMMAND' },
  { id: 'probability', label: 'PROBABILITY & FLOW' },
  { id: 'ecosystem', label: 'AI ECOSYSTEM' },
  { id: 'intelligence', label: 'INTELLIGENCE' },
  { id: 'live-feed', label: 'LIVE FEED' },
] as const

type TabId = (typeof TABS)[number]['id']

const TAB_LABELS: Record<TabId, string> = {
  'nvda-command': 'NVDA Command',
  probability: 'Probability & Flow',
  ecosystem: 'AI Ecosystem',
  intelligence: 'Intelligence',
  'live-feed': 'Live Feed',
}

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

  useEffect(() => {
    const interval = setInterval(() => {
      setClock(formatTime(new Date()))
    }, 1000)

    return () => clearInterval(interval)
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

      {/* Content area */}
      <main className="relative z-10 p-6">
        {activeTab === 'nvda-command' && <NVDACommandTab />}
        {activeTab === 'probability' && <ProbabilityFlowTab />}
        {activeTab === 'ecosystem' && <EcosystemTab />}
        {activeTab === 'intelligence' && <IntelligenceTab />}
        {activeTab === 'live-feed' && <LiveFeedTab />}
      </main>

      {/* Alert overlay zone — alerts will be injected here later */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2" />
    </div>
  )
}

export default App
