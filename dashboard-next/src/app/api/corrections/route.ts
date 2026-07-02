import { NextResponse } from 'next/server'
import { join } from 'path'
import { appendFileSync, readFileSync, writeFileSync, existsSync } from 'fs'

const PROJECT_ROOT = join(process.cwd(), '..')
const CORRECTIONS_LOG = join(PROJECT_ROOT, 'data', 'approved_corrections.jsonl')
const EXECUTED_LOG = join(PROJECT_ROOT, 'data', 'executed_corrections.jsonl')
const LEGACY_CORRECTIONS = join(PROJECT_ROOT, 'data', 'corrections.jsonl')

type CorrectionStatus = 'proposed' | 'queued' | 'applied' | 'failed' | 'partial' | 'rejected'

interface CorrectionRecord {
  id: string
  status: CorrectionStatus
  errorType: string
  severity: string
  description: string
  fix: string
  timestamp: string
  changes?: string[]
  result_message?: string
}

function parseJsonl(filepath: string): any[] {
  if (!existsSync(filepath)) return []
  return readFileSync(filepath, 'utf-8')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line)
      } catch {
        return null
      }
    })
    .filter(Boolean)
}

function mapExecutedStatus(raw: string | undefined): CorrectionStatus {
  if (raw === 'completed') return 'applied'
  if (raw === 'partial') return 'partial'
  if (raw === 'failed') return 'failed'
  return 'applied'
}

function buildCorrectionsList(): CorrectionRecord[] {
  let corrections: CorrectionRecord[] = []

  if (existsSync(CORRECTIONS_LOG)) {
    const pending = parseJsonl(CORRECTIONS_LOG).map((d) => ({
      id: d.timestamp,
      status: 'queued' as CorrectionStatus,
      errorType: d.errorName,
      severity: 'High',
      description: 'Aguardando execução do CorrectionAgent',
      fix: d.action,
      timestamp: d.timestamp,
    }))
    corrections = [...corrections, ...pending]
  }

  if (existsSync(EXECUTED_LOG)) {
    const executed = parseJsonl(EXECUTED_LOG).map((d) => ({
      id: d.timestamp,
      status: mapExecutedStatus(d.status),
      errorType: d.errorName,
      severity: 'High',
      description: d.result_message || 'Executado',
      fix: d.action,
      timestamp: d.executed_at ? new Date(d.executed_at * 1000).toISOString() : d.timestamp,
      changes: d.changes || [],
      result_message: d.result_message,
    }))

    const executedMap = new Map(executed.map((e) => [e.id, e]))
    corrections = corrections.map((c) => executedMap.get(c.id) || c)
    executed.forEach((e) => {
      if (!corrections.find((c) => c.id === e.id)) corrections.push(e)
    })
  }

  if (existsSync(LEGACY_CORRECTIONS)) {
    const legacy = parseJsonl(LEGACY_CORRECTIONS).map((d) => {
      let status: CorrectionStatus = 'proposed'
      if (d.status === 'verified' || d.status === 'applied') status = 'applied'
      else if (d.status === 'rejected') status = 'rejected'
      else if (d.status === 'approved') status = 'queued'
      else if (d.status === 'failed') status = 'failed'

      return {
        id: d.id,
        status,
        errorType: d.errorType,
        severity: d.severity || 'Medium',
        description: d.description || '',
        fix: d.fix || '',
        timestamp: d.approvedAt || d.proposedAt || d.verifiedAt || new Date().toISOString(),
        result_message: d.result_message,
      }
    })

    for (const item of legacy) {
      if (!corrections.find((c) => c.id === item.id)) {
        corrections.push(item)
      }
    }
  }

  corrections.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  )
  return corrections
}

function buildByErrorName(corrections: CorrectionRecord[]): Record<string, CorrectionRecord> {
  const byErrorName: Record<string, CorrectionRecord> = {}

  for (const c of corrections) {
    const existing = byErrorName[c.errorType]
    if (
      !existing ||
      new Date(c.timestamp).getTime() >= new Date(existing.timestamp).getTime()
    ) {
      byErrorName[c.errorType] = c
    }
  }
  return byErrorName
}

function appendApproved(payload: Record<string, unknown>) {
  appendFileSync(CORRECTIONS_LOG, JSON.stringify(payload) + '\n', 'utf-8')
}

function handleLegacyApproval(id: string, action: 'approve' | 'reject') {
  const corrections = parseJsonl(LEGACY_CORRECTIONS)
  const idx = corrections.findIndex((c) => c.id === id)
  if (idx === -1) {
    return { ok: false as const, error: 'Correction not found' }
  }

  const entry = corrections[idx]
  if (action === 'reject') {
    entry.status = 'rejected'
    entry.rejectedAt = new Date().toISOString()
  } else {
    entry.status = 'approved'
    entry.approvedAt = new Date().toISOString()
    appendApproved({
      timestamp: new Date().toISOString(),
      status: 'pending',
      errorName: entry.errorType,
      action: entry.fix,
      legacyId: entry.id,
    })
  }

  writeFileSync(
    LEGACY_CORRECTIONS,
    corrections.map((c) => JSON.stringify(c)).join('\n') + '\n',
    'utf-8'
  )
  return { ok: true as const, entry }
}

export async function GET() {
  try {
    const corrections = buildCorrectionsList()
    const byErrorName = buildByErrorName(corrections)
    return NextResponse.json({ corrections, byErrorName })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()

    if (body.id && (body.action === 'approve' || body.action === 'reject')) {
      const result = handleLegacyApproval(body.id, body.action)
      if (!result.ok) {
        return NextResponse.json({ error: result.error }, { status: 404 })
      }
      return NextResponse.json({ success: true, correction: result.entry })
    }

    if (!body.errorName || !body.action) {
      return NextResponse.json(
        { error: 'errorName and action are required' },
        { status: 400 }
      )
    }

    const payload = {
      timestamp: new Date().toISOString(),
      status: 'pending',
      errorName: body.errorName,
      action: body.action,
    }
    appendApproved(payload)

    return NextResponse.json({ success: true, correction: payload })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
