interface TickerCardProps {
  symbol: string
  price: number
  changePercent: number
  className?: string
}

function TickerCard({ symbol, price, changePercent, className = '' }: TickerCardProps) {
  const isPositive = changePercent >= 0
  const changeColor = isPositive ? 'text-nvda-green' : 'text-red'
  const borderColor = isPositive ? 'border-l-nvda-green' : 'border-l-red'
  const arrow = isPositive ? '\u25B2' : '\u25BC'
  const sign = isPositive ? '+' : ''

  return (
    <div
      className={`glass-panel-inner flex flex-col gap-1 border-l-[3px] ${borderColor} px-4 py-3 ${className}`}
    >
      <span className="font-display text-[10px] font-bold uppercase tracking-wider text-text-muted">
        {symbol}
      </span>
      <span className="font-data text-lg font-semibold text-text-primary">
        ${price.toFixed(2)}
      </span>
      <span className={`font-data text-xs font-medium ${changeColor}`}>
        {arrow} {sign}{changePercent.toFixed(2)}%
      </span>
    </div>
  )
}

export default TickerCard
