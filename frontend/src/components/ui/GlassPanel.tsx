import React from 'react'

interface GlassPanelProps {
  children: React.ReactNode
  title?: string
  padding?: 'sm' | 'md' | 'lg'
  className?: string
  hover?: boolean
}

const paddingMap: Record<NonNullable<GlassPanelProps['padding']>, string> = {
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
}

function GlassPanel({
  children,
  title,
  padding = 'md',
  className = '',
  hover = true,
}: GlassPanelProps) {
  const pad = paddingMap[padding]
  const hoverClass = hover ? '' : 'hover:border-border hover:shadow-glass'

  return (
    <div
      className={[
        'glass-panel',
        pad,
        hoverClass,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {title && (
        <div className="mb-4 border-b border-border pb-3">
          <h3 className="font-display text-xs uppercase tracking-wider text-text-muted">
            {title}
          </h3>
        </div>
      )}
      {children}
    </div>
  )
}

export default GlassPanel
