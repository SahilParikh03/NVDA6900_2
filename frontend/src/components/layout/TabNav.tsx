import { type FC } from 'react'

interface Tab {
  id: string
  label: string
}

interface TabNavProps {
  tabs: Tab[]
  activeTab: string
  onTabChange: (tabId: string) => void
}

const TabNav: FC<TabNavProps> = ({ tabs, activeTab, onTabChange }) => {
  return (
    <nav className="glass-panel-inner flex items-center gap-1 px-2 py-1 rounded-lg">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab

        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={[
              'relative px-4 py-2 font-display text-xs tracking-widest uppercase',
              'transition-colors duration-200 rounded-md whitespace-nowrap',
              'focus:outline-none focus-visible:ring-1 focus-visible:ring-nvda-green/40',
              isActive
                ? 'tab-active text-text-primary text-glow'
                : 'text-text-muted hover:text-text-primary/80',
            ].join(' ')}
            aria-current={isActive ? 'page' : undefined}
          >
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}

export default TabNav
