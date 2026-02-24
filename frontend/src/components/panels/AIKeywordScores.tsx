import { useCallback, useState, useMemo } from 'react'
import GlassPanel from '../ui/GlassPanel'
import LoadingSkeleton from '../ui/LoadingSkeleton'
import ErrorState from '../ui/ErrorState'
import LastUpdated from '../ui/LastUpdated'
import usePolling from '../../hooks/usePolling'
import { fetchTranscripts } from '../../api/client'
import type { TranscriptData, TranscriptEntry } from '../../types/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function trendBadgeClass(trend: string): string {
  const lower = trend.toLowerCase()
  if (lower === 'increasing') return 'bg-nvda-green/15 border-nvda-green/30 text-nvda-green'
  if (lower === 'decreasing') return 'bg-red/15 border-red/30 text-red'
  return 'bg-amber/15 border-amber/30 text-amber'
}

type SortField = 'symbol' | 'ai_score'
type SortDir = 'asc' | 'desc'

function sortTranscripts(
  entries: TranscriptEntry[],
  field: SortField,
  dir: SortDir
): TranscriptEntry[] {
  const sorted = [...entries]
  sorted.sort((a, b) => {
    let cmp: number
    if (field === 'symbol') {
      cmp = a.symbol.localeCompare(b.symbol)
    } else {
      cmp = a.total_ai_score - b.total_ai_score
    }
    return dir === 'asc' ? cmp : -cmp
  })
  return sorted
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SortHeader({
  label,
  field,
  currentField,
  currentDir,
  onSort,
  className,
}: {
  label: string
  field: SortField
  currentField: SortField
  currentDir: SortDir
  onSort: (field: SortField) => void
  className?: string
}) {
  const isActive = field === currentField
  const arrow = isActive ? (currentDir === 'asc' ? '\u25B2' : '\u25BC') : ''

  return (
    <button
      type="button"
      onClick={() => onSort(field)}
      className={`flex items-center gap-1 font-display text-[10px] uppercase tracking-wider text-text-muted transition-colors hover:text-text-primary ${className ?? ''}`}
    >
      {label}
      {arrow && (
        <span className="text-nvda-green text-[8px]">{arrow}</span>
      )}
    </button>
  )
}

function KeywordPill({ keyword, count }: { keyword: string; count: number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 font-data text-[10px] text-text-muted">
      {keyword}
      <span className="text-nvda-green">{count}</span>
    </span>
  )
}

function ScoreBar({ score, maxScore }: { score: number; maxScore: number }) {
  const pct = maxScore > 0 ? (score / maxScore) * 100 : 0
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-16 overflow-hidden rounded-full bg-surface">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-nvda-green/60 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-data text-sm text-nvda-green tabular-nums">
        {score.toFixed(1)}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function AIKeywordScores() {
  const fetcher = useCallback(() => fetchTranscripts(), [])
  const { data, error, isLoading, lastUpdated } = usePolling<TranscriptData>(
    fetcher,
    { interval: 86_400_000 }
  )

  const [sortField, setSortField] = useState<SortField>('ai_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const handleSort = useCallback(
    (field: SortField) => {
      if (field === sortField) {
        setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortField(field)
        setSortDir('desc')
      }
    },
    [sortField]
  )

  const sortedTranscripts = useMemo(
    () => (data ? sortTranscripts(data.transcripts, sortField, sortDir) : []),
    [data, sortField, sortDir]
  )

  const maxScore = useMemo(
    () =>
      data
        ? Math.max(...data.transcripts.map((t) => t.total_ai_score), 1)
        : 1,
    [data]
  )

  return (
    <GlassPanel title="AI KEYWORD SCORES">
      {isLoading && !data && <LoadingSkeleton variant="line" lines={6} />}
      {error && !data && (
        <ErrorState message="Transcript data unavailable" />
      )}

      {data && (
        <div className="flex flex-col gap-4">
          {/* Trend badge */}
          <div className="flex items-center gap-3">
            <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
              AI Mention Trend
            </span>
            <span
              className={`rounded-full border px-3 py-0.5 font-display text-[11px] font-bold uppercase tracking-wider ${trendBadgeClass(data.trend)}`}
            >
              {data.trend}
            </span>
          </div>

          {/* Table */}
          <div className="glass-panel-inner overflow-x-auto">
            <table className="w-full min-w-[480px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-2.5 text-left">
                    <SortHeader
                      label="Symbol"
                      field="symbol"
                      currentField={sortField}
                      currentDir={sortDir}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-4 py-2.5 text-left">
                    <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
                      Quarter
                    </span>
                  </th>
                  <th className="px-4 py-2.5 text-left">
                    <SortHeader
                      label="AI Score"
                      field="ai_score"
                      currentField={sortField}
                      currentDir={sortDir}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-4 py-2.5 text-left">
                    <span className="font-display text-[10px] uppercase tracking-wider text-text-muted">
                      Top Keywords
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedTranscripts.map((entry) => (
                  <tr
                    key={`${entry.symbol}-${entry.quarter}`}
                    className="transition-colors hover:bg-surface-hover"
                  >
                    <td className="px-4 py-3">
                      <span className="font-data text-sm font-semibold text-text-primary">
                        {entry.symbol}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-data text-xs text-text-muted">
                        {entry.quarter}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBar
                        score={entry.total_ai_score}
                        maxScore={maxScore}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {entry.top_keywords.slice(0, 5).map((kw) => (
                          <KeywordPill
                            key={kw.keyword}
                            keyword={kw.keyword}
                            count={kw.count}
                          />
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end">
            <LastUpdated timestamp={lastUpdated} />
          </div>
        </div>
      )}
    </GlassPanel>
  )
}

export default AIKeywordScores
