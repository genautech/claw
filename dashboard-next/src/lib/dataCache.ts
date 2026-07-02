import { getFileMtime } from '@/lib/jsonl'

interface CacheEntry<T> {
  value: T
  expiresAt: number
  mtimeKey: string
}

const store = new Map<string, CacheEntry<unknown>>()

function buildMtimeKey(filepaths: string[]): string {
  return filepaths.map((p) => `${p}:${getFileMtime(p)}`).join('|')
}

/** TTL cache with optional file mtime invalidation. */
export function getCached<T>(
  key: string,
  factory: () => T,
  options?: { ttlMs?: number; filepaths?: string[] },
): T {
  const ttlMs = options?.ttlMs ?? 3000
  const mtimeKey = options?.filepaths ? buildMtimeKey(options.filepaths) : ''
  const now = Date.now()
  const existing = store.get(key) as CacheEntry<T> | undefined

  if (
    existing &&
    existing.expiresAt > now &&
    existing.mtimeKey === mtimeKey
  ) {
    return existing.value
  }

  const value = factory()
  store.set(key, { value, expiresAt: now + ttlMs, mtimeKey })
  return value
}

export function invalidateCache(prefix?: string): void {
  if (!prefix) {
    store.clear()
    return
  }
  for (const key of store.keys()) {
    if (key.startsWith(prefix)) store.delete(key)
  }
}
