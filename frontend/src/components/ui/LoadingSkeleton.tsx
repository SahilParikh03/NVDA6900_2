import React from 'react'

interface LoadingSkeletonProps {
  variant: 'line' | 'card' | 'chart'
  lines?: number
  className?: string
}

const LINE_WIDTHS = ['w-full', 'w-4/5', 'w-3/5', 'w-full', 'w-4/5', 'w-3/5']

function getLineWidth(index: number): string {
  return LINE_WIDTHS[index % LINE_WIDTHS.length]
}

function LoadingSkeleton({
  variant,
  lines = 3,
  className = '',
}: LoadingSkeletonProps) {
  if (variant === 'line') {
    return (
      <div className={`flex flex-col gap-3 ${className}`}>
        {Array.from({ length: lines }, (_, i) => (
          <div
            key={i}
            className={`skeleton h-4 ${getLineWidth(i)}`}
          />
        ))}
      </div>
    )
  }

  if (variant === 'card') {
    return (
      <div className={`skeleton h-32 w-full ${className}`} />
    )
  }

  // variant === 'chart'
  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      <div className="skeleton h-64 w-full" />
      <div className="skeleton h-4 w-full" />
      <div className="skeleton h-4 w-4/5" />
      <div className="skeleton h-4 w-3/5" />
    </div>
  )
}

export default LoadingSkeleton
