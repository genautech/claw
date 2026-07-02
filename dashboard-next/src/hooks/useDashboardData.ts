'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

interface UseDashboardDataOptions<T> {
  intervalMs?: number
  staleTimeMs?: number
  enabled?: boolean
  pauseWhenHidden?: boolean
  initialData?: T | null
}

const inflight = new Map<string, Promise<unknown>>()
const memoryCache = new Map<string, { data: unknown; fetchedAt: number }>()

async function fetchDeduped<T>(url: string): Promise<T> {
  const existing = inflight.get(url)
  if (existing) return existing as Promise<T>

  const promise = fetch(url)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json() as Promise<T>
    })
    .finally(() => {
      inflight.delete(url)
    })

  inflight.set(url, promise)
  return promise
}

export function useDashboardData<T>(
  url: string,
  options: UseDashboardDataOptions<T> = {},
) {
  const {
    intervalMs = 0,
    staleTimeMs = 3000,
    enabled = true,
    pauseWhenHidden = true,
    initialData = null,
  } = options

  const [data, setData] = useState<T | null>(initialData)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!initialData)
  const mountedRef = useRef(true)

  const refresh = useCallback(async (force = false) => {
    if (!enabled) return

    const cached = memoryCache.get(url)
    const now = Date.now()
    if (!force && cached && now - cached.fetchedAt < staleTimeMs) {
      setData(cached.data as T)
      setLoading(false)
      return cached.data as T
    }

    try {
      const json = await fetchDeduped<T>(url)
      if (!mountedRef.current) return json
      memoryCache.set(url, { data: json, fetchedAt: Date.now() })
      setData(json)
      setError(null)
      return json
    } catch (e: unknown) {
      if (!mountedRef.current) return null
      const message = e instanceof Error ? e.message : 'fetch failed'
      setError(message)
      return null
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [url, enabled, staleTimeMs])

  useEffect(() => {
    mountedRef.current = true
    refresh(true)

    if (!intervalMs || !enabled) {
      return () => {
        mountedRef.current = false
      }
    }

    const tick = () => {
      if (pauseWhenHidden && typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return
      }
      refresh(false)
    }

    const id = setInterval(tick, intervalMs)
    return () => {
      mountedRef.current = false
      clearInterval(id)
    }
  }, [refresh, intervalMs, enabled, pauseWhenHidden])

  return { data, error, loading, refresh }
}

export function invalidateClientCache(prefix?: string) {
  if (!prefix) {
    memoryCache.clear()
    return
  }
  for (const key of memoryCache.keys()) {
    if (key.startsWith(prefix)) memoryCache.delete(key)
  }
}
