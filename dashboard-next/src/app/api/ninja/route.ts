import { NextResponse } from 'next/server'
import { join } from 'path'
import { getCached } from '@/lib/dataCache'
import { readJsonlTail } from '@/lib/jsonl'

const NINJA_LOG = join(process.cwd(), '..', 'data', 'ninja_trades.jsonl')

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const limit = Math.min(parseInt(searchParams.get('limit') || '100', 10), 100)

  const trades = getCached(
    `ninja-tail-${limit}`,
    () => readJsonlTail(NINJA_LOG, limit).reverse(),
    { filepaths: [NINJA_LOG], ttlMs: 2000 },
  )

  return NextResponse.json(trades)
}
