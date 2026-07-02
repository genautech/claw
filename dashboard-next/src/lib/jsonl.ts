import { existsSync, readFileSync, openSync, readSync, closeSync, statSync } from 'fs'

export type JsonlRow = Record<string, unknown>

function parseLine(line: string): JsonlRow | null {
  const trimmed = line.trim()
  if (!trimmed) return null
  try {
    if (trimmed.startsWith('[')) return null
    if (trimmed.startsWith(']')) return null
    const cleaned = trimmed.replace(/^\[?\s*/, '').replace(/\s*\]?\s*$/, '').replace(/,\s*$/, '')
    if (!cleaned) return null
    return JSON.parse(cleaned) as JsonlRow
  } catch {
    return null
  }
}

function parseLines(lines: string[]): JsonlRow[] {
  const results: JsonlRow[] = []
  for (const line of lines) {
    const row = parseLine(line)
    if (row) results.push(row)
  }
  return results
}

export function getFileMtime(filepath: string): number {
  if (!existsSync(filepath)) return 0
  try {
    return statSync(filepath).mtimeMs
  } catch {
    return 0
  }
}

/** Read and parse entire JSONL file. */
export function readJsonlFull(filepath: string): JsonlRow[] {
  if (!existsSync(filepath)) return []
  try {
    const content = readFileSync(filepath, 'utf-8')
    return parseLines(content.split('\n'))
  } catch {
    return []
  }
}

/**
 * Read last N lines efficiently for larger files.
 * Falls back to full read for small files.
 */
export function readJsonlTail(filepath: string, limit: number): JsonlRow[] {
  if (!existsSync(filepath) || limit <= 0) return []
  try {
    const stat = statSync(filepath)
    if (stat.size === 0) return []

    const chunkSize = Math.min(stat.size, Math.max(64 * 1024, limit * 512))
    const fd = openSync(filepath, 'r')
    const start = Math.max(0, stat.size - chunkSize)
    const buffer = Buffer.alloc(stat.size - start)
    readSync(fd, buffer, 0, buffer.length, start)
    closeSync(fd)

    const text = buffer.toString('utf-8')
    const lines = text.split('\n').filter(Boolean)
    if (start > 0 && lines.length > 0) lines.shift()

    const tailLines = lines.slice(-limit - 2)
    const parsed = parseLines(tailLines)
    return parsed.slice(-limit)
  } catch {
    const all = readJsonlFull(filepath)
    return all.slice(-limit)
  }
}

export function readJsonlWithMeta(filepath: string, tailLimit?: number): {
  all: JsonlRow[]
  tail: JsonlRow[]
  total: number
  mtime: number
} {
  const mtime = getFileMtime(filepath)
  const all = readJsonlFull(filepath)
  const tail = tailLimit != null ? all.slice(-tailLimit) : all
  return { all, tail, total: all.length, mtime }
}
