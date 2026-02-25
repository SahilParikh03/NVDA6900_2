import React from 'react'

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[ErrorBoundary] Render error caught:', error)
    console.error('[ErrorBoundary] Component stack:', info.componentStack)
  }

  handleRetry = (): void => {
    this.setState({ hasError: false })
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="glass-panel-inner flex flex-col items-center justify-center gap-4 px-6 py-8">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-red-500/30 bg-red-500/10">
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <circle cx="10" cy="10" r="8" stroke="#EF4444" strokeWidth="1.25" />
              <path d="M7 7l6 6M13 7l-6 6" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>

          <p className="font-display text-xs uppercase tracking-wider text-text-muted">
            Panel Error
          </p>
          <p className="text-center text-sm text-text-muted">
            This panel encountered an error and couldn&apos;t render.
          </p>

          <button
            type="button"
            onClick={this.handleRetry}
            className="rounded-lg border border-nvda-green/40 bg-transparent px-4 py-1.5 text-xs font-medium text-nvda-green transition-colors duration-200 hover:bg-green-dim"
          >
            Retry
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
