import React from 'react'

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
  className?: string
}

function ErrorState({
  message = 'Data temporarily unavailable',
  onRetry,
  className = '',
}: ErrorStateProps) {
  return (
    <div
      className={`glass-panel-inner flex flex-col items-center justify-center gap-4 px-6 py-8 ${className}`}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-amber/30 bg-amber/10">
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M10 6V10.5"
            stroke="#FFB800"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <circle cx="10" cy="13.5" r="0.75" fill="#FFB800" />
          <path
            d="M8.862 3.154a1.25 1.25 0 0 1 2.276 0l5.541 11.75A1.25 1.25 0 0 1 15.541 16.5H4.459a1.25 1.25 0 0 1-1.138-1.596l5.541-11.75Z"
            stroke="#FFB800"
            strokeWidth="1.25"
          />
        </svg>
      </div>

      <p className="text-center text-sm text-text-muted">{message}</p>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg border border-nvda-green/40 bg-transparent px-4 py-1.5 text-xs font-medium text-nvda-green transition-colors duration-200 hover:bg-green-dim"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export default ErrorState
