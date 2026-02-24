import { useCallback } from 'react'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchNews } from '../../api/client'
import type { NewsArticle } from '../../types/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).trimEnd() + '...'
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ArticleCard({ article }: { article: NewsArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="glass-panel-inner flex gap-3 p-4 transition-colors hover:bg-surface-hover"
    >
      {/* Thumbnail */}
      {article.image && (
        <div className="h-16 w-20 flex-shrink-0 overflow-hidden rounded-lg bg-surface">
          <img
            src={article.image}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <h4 className="font-body text-sm font-semibold text-text-primary leading-tight">
          {article.title}
        </h4>

        <div className="mt-1.5 flex items-center gap-2">
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 font-data text-[10px] text-text-muted">
            {article.site}
          </span>
          <span className="font-data text-[10px] text-text-muted">
            {relativeTime(article.publishedDate)}
          </span>
        </div>

        <p className="mt-2 font-body text-xs leading-relaxed text-text-muted">
          {truncate(article.text, 200)}
        </p>
      </div>

      {/* External link icon */}
      <div className="mt-0.5 flex-shrink-0 text-text-muted">
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M5.5 2.5H3C2.72386 2.5 2.5 2.72386 2.5 3V11C2.5 11.2761 2.72386 11.5 3 11.5H11C11.2761 11.5 11.5 11.2761 11.5 11V8.5"
            stroke="currentColor"
            strokeWidth="1"
            strokeLinecap="round"
          />
          <path
            d="M8.5 2.5H11.5V5.5"
            stroke="currentColor"
            strokeWidth="1"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M11.5 2.5L6.5 7.5"
            stroke="currentColor"
            strokeWidth="1"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </a>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function NewsFeed() {
  const fetcher = useCallback(() => fetchNews(), [])
  const { data, error, isLoading, lastUpdated } = usePolling<NewsArticle[]>(
    fetcher,
    { interval: 60_000 }
  )

  const sortedArticles = data
    ? [...data].sort(
        (a, b) =>
          new Date(b.publishedDate).getTime() -
          new Date(a.publishedDate).getTime()
      )
    : []

  return (
    <GlassPanel title="NEWS FEED" className="flex flex-col h-full">
      {isLoading && !data && <LoadingSkeleton variant="line" lines={6} />}
      {error && !data && (
        <ErrorState message="News data unavailable" />
      )}

      {data && (
        <div className="flex flex-1 flex-col gap-3 min-h-0">
          {/* Scrollable container */}
          <div className="flex-1 space-y-3 overflow-y-auto max-h-[600px] pr-1">
            {sortedArticles.length === 0 && (
              <p className="py-8 text-center font-body text-sm text-text-muted">
                No articles available
              </p>
            )}
            {sortedArticles.map((article, idx) => (
              <ArticleCard key={`${article.url}-${idx}`} article={article} />
            ))}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end pt-2">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default NewsFeed
