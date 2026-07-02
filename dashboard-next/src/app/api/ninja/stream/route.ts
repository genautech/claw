import { NextRequest } from 'next/server'
import { watch, existsSync, statSync } from 'fs'
import { join } from 'path'
import { getCached } from '@/lib/dataCache'
import { readJsonlTail } from '@/lib/jsonl'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

const NINJA_FILE = join(process.cwd(), '..', 'data', 'ninja_trades.jsonl')

function readTailCached(limit: number): unknown[] {
  return getCached(
    `ninja-stream-tail-${limit}`,
    () => readJsonlTail(NINJA_FILE, limit),
    { filepaths: [NINJA_FILE], ttlMs: 1000 },
  )
}

export async function GET(request: NextRequest) {
  const limit = Math.min(parseInt(request.nextUrl.searchParams.get('limit') || '20', 10), 100)

  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder()
      let closed = false
      let watcher: ReturnType<typeof watch> | null = null
      let lastMtime = existsSync(NINJA_FILE) ? statSync(NINJA_FILE).mtimeMs : 0

      const send = (event: string, data: unknown) => {
        if (closed) return
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`))
      }

      send('init', { trades: readTailCached(limit), mtime: lastMtime })

      const pushIfChanged = () => {
        if (!existsSync(NINJA_FILE)) return
        const mtime = statSync(NINJA_FILE).mtimeMs
        if (mtime !== lastMtime) {
          lastMtime = mtime
          send('update', { trades: readTailCached(limit), mtime })
        }
      }

      try {
        watcher = watch(NINJA_FILE, pushIfChanged)
      } catch {
        // file may not exist yet
      }

      request.signal.addEventListener('abort', () => {
        closed = true
        if (watcher) watcher.close()
        try {
          controller.close()
        } catch {
          // already closed
        }
      })
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
    },
  })
}
