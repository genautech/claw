import { join } from 'path'
import { getCached } from '@/lib/dataCache'
import { readJsonlFull, type JsonlRow } from '@/lib/jsonl'

const DATA_DIR = join(process.cwd(), '..', 'data')
export const EXECS_FILE = join(DATA_DIR, 'executions.jsonl')
export const RECS_FILE = join(DATA_DIR, 'recommendations.jsonl')
export const SIMS_FILE = join(DATA_DIR, 'simulated_trades.jsonl')
export const RISK_FILE = join(DATA_DIR, 'risk-events.jsonl')

export interface ExecutionStats {
  total: number
  success: number
  errors: number
  dryRun: number
  live: number
  won: number
  lost: number
  pending: number
  errorTypes: Record<string, number>
  hourly: Record<number, number>
  totalPnl: number
}

export interface RecommendationStats {
  total: number
  decisions: Record<string, number>
  confidence: Record<string, number>
  strategies: Record<string, number>
}

export function getExecutionStats(executions: JsonlRow[]): ExecutionStats {
  const total = executions.length
  const success = executions.filter((e) => e.success).length
  const errors = total - success
  const dryRun = executions.filter((e) => String(e.action || '').includes('dry-run')).length
  const live = executions.filter((e) => e.success && !String(e.action || '').includes('dry-run')).length

  const trades = executions.filter(
    (e) => String(e.action || '').includes('executed') && !String(e.action || '').includes('dry-run'),
  )
  const won = trades.filter((e) => {
    const result = e.result as Record<string, unknown> | undefined
    return e.success && Number(result?.pnl ?? 0) > 0
  }).length
  const lost = trades.filter((e) => {
    const result = e.result as Record<string, unknown> | undefined
    return e.success && Number(result?.pnl ?? 0) <= 0
  }).length
  const pending = trades.filter((e) => {
    const result = e.result as Record<string, unknown> | undefined
    return e.success && result?.pnl === undefined
  }).length

  const errorTypes: Record<string, number> = {}
  executions.filter((e) => !e.success && e.error).forEach((e) => {
    const err = String(e.error)
    let type = 'Other'
    if (err.includes('balance') || err.includes('allowance')) type = 'Balance/Allowance'
    else if (err.includes('Invalid market')) type = 'Invalid Market ID'
    else if (err.includes('invalid signature')) type = 'Invalid Signature'
    else if (err.includes('POLYMARKET_PK')) type = 'Missing Config'
    else if (err.includes('division by zero')) type = 'Division by Zero'
    else if (err.includes('api_key') || err.includes('Unauthorized')) type = 'Auth Error'
    else if (err.includes('size lower')) type = 'Size Too Small'
    errorTypes[type] = (errorTypes[type] || 0) + 1
  })

  const hourly: Record<number, number> = {}
  executions.forEach((e) => {
    try {
      const h = new Date(String(e.timestamp)).getHours()
      hourly[h] = (hourly[h] || 0) + 1
    } catch {
      // skip
    }
  })

  const totalPnl = executions
    .filter((e) => {
      const result = e.result as Record<string, unknown> | undefined
      return result?.pnl !== undefined
    })
    .reduce((sum, e) => {
      const result = e.result as Record<string, unknown>
      return sum + Number(result.pnl || 0)
    }, 0)

  return { total, success, errors, dryRun, live, won, lost, pending, errorTypes, hourly, totalPnl }
}

export function getRecommendationStats(recs: JsonlRow[]): RecommendationStats {
  const total = recs.length
  const decisions: Record<string, number> = {}
  const confidence: Record<string, number> = {}
  const strategies: Record<string, number> = {}
  recs.forEach((r) => {
    const decision = String(r.decision || 'unknown')
    const conf = String(r.confidence || 'unknown')
    decisions[decision] = (decisions[decision] || 0) + 1
    confidence[conf] = (confidence[conf] || 0) + 1
    if (r.strategy) strategies[String(r.strategy)] = (strategies[String(r.strategy)] || 0) + 1
  })
  return { total, decisions, confidence, strategies }
}

export function getExecutionsCached(): { all: JsonlRow[]; stats: ExecutionStats } {
  return getCached(
    'executions',
    () => {
      const all = readJsonlFull(EXECS_FILE)
      return { all, stats: getExecutionStats(all) }
    },
    { filepaths: [EXECS_FILE], ttlMs: 3000 },
  )
}

export function getRecommendationsCached(): { all: JsonlRow[]; stats: RecommendationStats } {
  return getCached(
    'recommendations',
    () => {
      const all = readJsonlFull(RECS_FILE)
      return { all, stats: getRecommendationStats(all) }
    },
    { filepaths: [RECS_FILE], ttlMs: 3000 },
  )
}

export function getSimulatedCached(): { all: JsonlRow[]; total: number } {
  return getCached(
    'simulated',
    () => {
      const all = readJsonlFull(SIMS_FILE)
      return { all, total: all.length }
    },
    { filepaths: [SIMS_FILE], ttlMs: 3000 },
  )
}

export function getRiskEventsCached(): { all: JsonlRow[]; total: number } {
  return getCached(
    'risk-events',
    () => {
      const all = readJsonlFull(RISK_FILE)
      return { all, total: all.length }
    },
    { filepaths: [RISK_FILE], ttlMs: 3000 },
  )
}

export function buildExecutionsByMarket(execs: JsonlRow[]): Map<string, JsonlRow[]> {
  const map = new Map<string, JsonlRow[]>()
  for (const e of execs) {
    const details = e.details as Record<string, unknown> | undefined
    const marketId = String(details?.marketId || '')
    if (!marketId) continue
    const list = map.get(marketId) || []
    list.push(e)
    map.set(marketId, list)
  }
  return map
}

const RECOMMENDED_FIXES: Record<string, string> = {
  'Balance/Allowance': 'Auto-approve USDC and pause agent if balance < reserve',
  'Size Too Small': 'Enforce minimum order size of 5 USDC in settings',
  'Invalid Market ID': 'Pre-validate market ID format against API schema',
  'Auth/Config Error': 'Agent should test credentials and prompt on startup',
  'Division by Zero': 'Guard against currentPrice = 0 or null',
  'Invalid Signature': 'Sync server time and verify L1 wallet state',
  'Price Error': 'Adjust slippage max and implement retry with backoff',
  Other: 'Inspect raw logs to identify root cause',
}

export function buildErrorAnalysis(execs: JsonlRow[]) {
  const errors = execs.filter((e) => !e.success && e.error)
  const now = new Date()
  const typeMap: Record<string, { count: number; lastSeen: string; impact: string; trend: number }> = {}

  errors.forEach((e) => {
    const err = String(e.error)
    let type = 'Other'
    let impact = 'Low'

    if (err.includes('balance') || err.includes('allowance')) {
      type = 'Balance/Allowance'
      impact = 'High - Trade blocked'
    } else if (err.includes('Invalid market') || err.includes('Unknown market')) {
      type = 'Invalid Market ID'
      impact = 'Medium - Skipped order'
    } else if (err.includes('invalid signature') || err.includes('signature validation failed')) {
      type = 'Invalid Signature'
      impact = 'High - Auth failure'
    } else if (err.includes('size lower') || err.includes('lower than the minimum')) {
      type = 'Size Too Small'
      impact = 'Medium - Order rejected'
    } else if (err.includes('POLYMARKET_PK') || err.includes('api_key') || err.includes('Unauthorized')) {
      type = 'Auth/Config Error'
      impact = 'Critical - System down'
    } else if (err.includes('division by zero')) {
      type = 'Division by Zero'
      impact = 'Medium - Calculation error'
    } else if (err.includes('price')) {
      type = 'Price Error'
      impact = 'Medium - Execution blocked'
    }

    if (!typeMap[type]) typeMap[type] = { count: 0, lastSeen: String(e.timestamp), impact, trend: 0 }
    typeMap[type].count += 1

    if (new Date(String(e.timestamp)) > new Date(typeMap[type].lastSeen)) {
      typeMap[type].lastSeen = String(e.timestamp)
    }

    const ts = new Date(String(e.timestamp))
    if (now.getTime() - ts.getTime() < 24 * 60 * 60 * 1000) {
      typeMap[type].trend += 1
    }
  })

  const analysis = Object.entries(typeMap).map(([type, data]) => {
    const severityScore = data.count * (data.impact.includes('High') || data.impact.includes('Critical') ? 3 : 1)
    let severity = 'Low'
    if (severityScore > 20) severity = 'Critical'
    else if (severityScore > 10) severity = 'High'
    else if (severityScore > 5) severity = 'Medium'

    return {
      type,
      ...data,
      severity,
      severityScore,
      recommendedFix: RECOMMENDED_FIXES[type] || RECOMMENDED_FIXES.Other,
    }
  }).sort((a, b) => b.severityScore - a.severityScore)

  return { totalErrors: errors.length, analysis }
}
