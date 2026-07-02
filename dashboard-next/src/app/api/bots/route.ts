import { NextResponse } from 'next/server'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'
import { getCached } from '@/lib/dataCache'
import { readJsonlFull, type JsonlRow } from '@/lib/jsonl'

const DATA_DIR = join(process.cwd(), '..', 'data')
const ANALYSES_FILE = join(DATA_DIR, 'bot_analyses.jsonl')
const WATCHLIST_FILE = join(DATA_DIR, 'bot_watchlist.json')

function buildBotsPayload() {
  const all = readJsonlFull(ANALYSES_FILE)
  const latestByWallet = new Map<string, JsonlRow>()
  for (const row of all) {
    const wallet = String(row.wallet || '')
    if (!wallet) continue
    const prev = latestByWallet.get(wallet)
    const ts = String(row.analyzed_at || '')
    if (!prev || ts > String(prev.analyzed_at || '')) {
      latestByWallet.set(wallet, row)
    }
  }

  let watchlist: { enabled?: boolean; wallets?: string[]; notes?: string } = {}
  if (existsSync(WATCHLIST_FILE)) {
    try {
      watchlist = JSON.parse(readFileSync(WATCHLIST_FILE, 'utf-8'))
    } catch {
      watchlist = {}
    }
  }

  const analyses = Array.from(latestByWallet.values()).sort(
    (a, b) => String(b.analyzed_at || '').localeCompare(String(a.analyzed_at || '')),
  )

  const strategies: Record<string, number> = {}
  for (const a of analyses) {
    const s = String(a.strategy || 'unknown')
    strategies[s] = (strategies[s] || 0) + 1
  }

  return {
    watchlist,
    analyses,
    history: all.slice(-50).reverse(),
    stats: {
      total: all.length,
      wallets: analyses.length,
      strategies,
      botCount: analyses.filter((a) => a.is_bot).length,
    },
  }
}

export const dynamic = 'force-dynamic'

export async function GET() {
  const payload = getCached(
    'bots',
    buildBotsPayload,
    { filepaths: [ANALYSES_FILE, WATCHLIST_FILE], ttlMs: 5000 },
  )
  return NextResponse.json(payload)
}
