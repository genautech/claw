import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'fs'
import { join } from 'path'

const DATA_DIR = join(process.cwd(), '..', 'data')
const RECS_FILE = join(DATA_DIR, 'recommendations.jsonl')
const EXECS_FILE = join(DATA_DIR, 'executions.jsonl')
const STATUS_FILE = join(DATA_DIR, 'recommendation-status.json')

function parseJsonl(filepath: string): any[] {
  if (!existsSync(filepath)) return []
  try {
    return readFileSync(filepath, 'utf-8')
      .trim().split('\n').filter(Boolean)
      .map(line => { try { return JSON.parse(line) } catch { return null } })
      .filter(Boolean)
  } catch { return [] }
}

function getStatusMap(): Record<string, { status: string; updatedAt: string; executionResult?: any }> {
  try {
    if (existsSync(STATUS_FILE)) return JSON.parse(readFileSync(STATUS_FILE, 'utf-8'))
  } catch {}
  return {}
}

function saveStatusMap(map: Record<string, any>) {
  writeFileSync(STATUS_FILE, JSON.stringify(map, null, 2))
}

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const recs = parseJsonl(RECS_FILE)
  const execs = parseJsonl(EXECS_FILE)
  const statusMap = getStatusMap()

  // Enrich recommendations with status
  const enriched = recs.map((rec: any) => {
    const id = rec.id || rec.market_id || rec.timestamp
    const status = statusMap[id]

    // Check if already executed
    const execution = execs.find((e: any) =>
      e.details?.marketId === rec.market_id &&
      e.timestamp > rec.timestamp
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

  return NextResponse.json({
    recommendations: enriched.reverse(),
    stats: {
      total: enriched.length,
      pending: enriched.filter((r: any) => r._status === 'pending').length,
      accepted: enriched.filter((r: any) => r._status === 'accepted').length,
      executed: enriched.filter((r: any) => r._status === 'executed').length,
      rejected: enriched.filter((r: any) => r._status === 'rejected').length,
      failed: enriched.filter((r: any) => r._status === 'failed').length,
    }
  })
}

export async function POST(request: NextRequest) {
  try {
    const { id, action } = await request.json()
    if (!id || !action) return NextResponse.json({ error: 'id and action required' }, { status: 400 })

    const statusMap = getStatusMap()

    if (action === 'accept') {
      statusMap[id] = { status: 'accepted', updatedAt: new Date().toISOString() }
      // Write to executions as "recommendation_accepted"
      const recs = parseJsonl(RECS_FILE)
      const rec = recs.find((r: any) => (r.id || r.market_id || r.timestamp) === id)
      if (rec) {
        const execEntry = {
          timestamp: new Date().toISOString(),
          action: 'recommendation_accepted',
          details: {
            marketId: rec.market_id,
            outcomeId: rec.decision?.includes('YES') ? 'YES' : 'NO',
            side: 'buy',
            sizeUsd: rec.sizeUsd || 1,
            maxPrice: rec.target_price || rec.targetPrice || 0.5,
            description: rec.description,
          },
          success: true,
          error: null,
        }
        appendFileSync(EXECS_FILE, JSON.stringify(execEntry) + '\n')
      }
    } else if (action === 'reject') {
      statusMap[id] = { status: 'rejected', updatedAt: new Date().toISOString() }
    }

    saveStatusMap(statusMap)
    return NextResponse.json({ ok: true, status: statusMap[id] })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
