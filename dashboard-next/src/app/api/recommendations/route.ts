import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'fs'
import { join } from 'path'
import { spawnBackground } from '@/lib/spawnBackground'
import { getCached } from '@/lib/dataCache'
import { getDashboardConfig } from '@/lib/configSync'
import {
  buildExecutionsByMarket,
  getExecutionsCached,
  getRecommendationsCached,
  EXECS_FILE,
  RECS_FILE,
} from '@/lib/aggregates'

const DATA_DIR = join(process.cwd(), '..', 'data')
const STATUS_FILE = join(DATA_DIR, 'recommendation-status.json')

function getStatusMap(): Record<string, { status: string; updatedAt: string; executionResult?: unknown }> {
  try {
    if (existsSync(STATUS_FILE)) return JSON.parse(readFileSync(STATUS_FILE, 'utf-8'))
  } catch {
    // ignore
  }
  return {}
}

function saveStatusMap(map: Record<string, unknown>) {
  writeFileSync(STATUS_FILE, JSON.stringify(map, null, 2))
}

function spawnProcessRecs() {
  spawnBackground('python3', ['scripts/polymarket-exec.py', '--process-recs'], '/tmp/process-recs-accept.log')
}

function enrichRecommendations(limit: number) {
  return getCached(
    `recommendations-enriched-${limit}`,
    () => {
      const { all: recs } = getRecommendationsCached()
      const { all: execs } = getExecutionsCached()
      const statusMap = getStatusMap()
      const execByMarket = buildExecutionsByMarket(execs)

      const slice = recs.slice(-limit)
      const enriched = slice.map((rec) => {
        const id = String(rec.id || rec.market_id || rec.timestamp)
        const status = statusMap[id]
        const marketId = String(rec.market_id || '')
        const candidates = execByMarket.get(marketId) || []
        const execution = candidates.find(
          (e) => String(e.timestamp) > String(rec.timestamp),
        )

        let currentStatus = status?.status || 'pending'
        if (execution && currentStatus !== 'rejected') {
          currentStatus = execution.success ? 'executed' : 'failed'
        }

        return {
          ...rec,
          _id: id,
          _status: currentStatus,
          _execution: execution || null,
          _updatedAt: status?.updatedAt || rec.timestamp,
        }
      })

      return {
        recommendations: enriched.reverse(),
        stats: {
          total: enriched.length,
          pending: enriched.filter((r) => r._status === 'pending').length,
          accepted: enriched.filter((r) => r._status === 'accepted').length,
          executed: enriched.filter((r) => r._status === 'executed').length,
          rejected: enriched.filter((r) => r._status === 'rejected').length,
          failed: enriched.filter((r) => r._status === 'failed').length,
        },
      }
    },
    { filepaths: [RECS_FILE, EXECS_FILE, STATUS_FILE], ttlMs: 3000 },
  )
}

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const limit = Math.min(parseInt(request.nextUrl.searchParams.get('limit') || '50', 10), 200)
  return NextResponse.json(enrichRecommendations(limit))
}

export async function POST(request: NextRequest) {
  try {
    const { id, action } = await request.json()
    if (!id || !action) return NextResponse.json({ error: 'id and action required' }, { status: 400 })

    const statusMap = getStatusMap()

    if (action === 'accept') {
      statusMap[id] = { status: 'accepted', updatedAt: new Date().toISOString() }
      const config = getDashboardConfig()
      const tradeSize = Number(config.maxTrade || 5)
      const { all: recs } = getRecommendationsCached()
      const rec = recs.find((r) => String(r.id || r.market_id || r.timestamp) === id)
      if (rec) {
        const execEntry = {
          timestamp: new Date().toISOString(),
          action: 'recommendation_accepted',
          details: {
            marketId: rec.market_id,
            outcomeId: String(rec.decision || '').includes('YES') ? 'YES' : 'NO',
            side: 'buy',
            sizeUsd: rec.sizeUsd ?? tradeSize,
            maxPrice: rec.target_price || rec.targetPrice || 0.5,
            description: rec.description,
            recId: id,
          },
          success: true,
          error: null,
        }
        appendFileSync(EXECS_FILE, JSON.stringify(execEntry) + '\n')
      }
      spawnProcessRecs()
    } else if (action === 'reject') {
      statusMap[id] = { status: 'rejected', updatedAt: new Date().toISOString() }
    }

    saveStatusMap(statusMap)
    return NextResponse.json({ ok: true, status: statusMap[id] })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
