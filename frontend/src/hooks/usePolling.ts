import { useEffect, useRef, useCallback, useState } from 'react'

interface UsePollingOptions {
  interval: number
  enabled?: boolean
}

interface UsePollingResult<T> {
  data: T | null
  error: Error | null
  isLoading: boolean
  lastUpdated: Date | null
}

function usePolling<T>(
  fetcher: () => Promise<T>,
  options: UsePollingOptions
): UsePollingResult<T> {
  const { interval, enabled = true } = options
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const result = await fetcher()
      setData(result)
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setIsLoading(false)
    }
  }, [fetcher])

  useEffect(() => {
    if (!enabled) return

    fetchData()

    intervalRef.current = setInterval(fetchData, interval)

    const handleVisibilityChange = () => {
      if (document.hidden) {
        if (intervalRef.current) clearInterval(intervalRef.current)
      } else {
        fetchData()
        intervalRef.current = setInterval(fetchData, interval)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [fetchData, interval, enabled])

  return { data, error, isLoading, lastUpdated }
}

export default usePolling
