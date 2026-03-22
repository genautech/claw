import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const DATA_DIR = join(process.cwd(), '..', 'data')
const EXECUTOR_URL = process.env.EXECUTOR_URL || 'http://127.0.0.1:8789'
const EXEC_TOKEN = process.env.EXEC_API_TOKEN || 'change-me-in-production'

function parseJsonl(filepath: string): any[] {
  if (!existsSync(filepath)) return []
  try {
    const content = readFileSync(filepath, 'utf-8')
    const lines = content.trim().split('\n').filter(Boolean)
    const results: any[] = []
    for (const line of lines) {
      try {
        if (line.startsWith('[')) {
          const arr = JSON.parse(line + (line.endsWith(']') ? '' : ']'))
          results.push(...arr)
          continue
        }
        if (line.startsWith(']')) continue
        const cleaned = line.replace(/^\[?\s*/, '').replace(/\s*\]?\s*$/, '').replace(/,\s*$/, '')
        if (cleaned) results.push(JSON.parse(cleaned))
      } catch {}
    }
    return results
  } catch { return [] }
}

async function proxyExecutor(path: string): Promise<any> {
  try {
    const res = await fetch(`${EXECUTOR_URL}${path}`, {
      headers: { Authorization: `Bearer ${EXEC_TOKEN}` },
      signal: AbortSignal.timeout(5000),
    })
    if (!res.ok) return { error: `Executor returned ${res.status}`, offline: true }
    return await res.json()
  } catch (e: any) {
    return { error: e.message, offline: true }
  }
}

function getExecutionStats(executions: any[]) {
  const total = executions.length
  const success = executions.filter(e => e.success).length
  const errors = total - success
  const dryRun = executions.filter(e => e.action?.includes('dry-run')).length
  const live = executions.filter(e => e.success && !e.action?.includes('dry-run')).length

  // Won/Lost based on actual trades (not recommendations)
  const trades = executions.filter(e =>
    e.action?.includes('executed') && !e.action?.includes('dry-run')
  )
  const won = trades.filter(e => e.success && e.result?.pnl > 0).length
  const lost = trades.filter(e => e.success && e.result?.pnl <= 0).length
  const pending = trades.filter(e => e.success && e.result?.pnl === undefined).length

  // Error breakdown
  const errorTypes: Record<string, number> = {}
  executions.filter(e => !e.success && e.error).forEach(e => {
    const err = e.error as string
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

  // Hourly distribution
  const hourly: Record<number, number> = {}
  executions.forEach(e => {
    try { hourly[new Date(e.timestamp).getHours()] = (hourly[new Date(e.timestamp).getHours()] || 0) + 1 } catch {}
  })

  // PnL calculation
  const totalPnl = executions
    .filter(e => e.result?.pnl !== undefined)
    .reduce((sum, e) => sum + (e.result.pnl || 0), 0)

  return { total, success, errors, dryRun, live, won, lost, pending, errorTypes, hourly, totalPnl }
}

function getRecommendationStats(recs: any[]) {
  const total = recs.length
  const decisions: Record<string, number> = {}
  const confidence: Record<string, number> = {}
  const strategies: Record<string, number> = {}
  recs.forEach(r => {
    decisions[r.decision] = (decisions[r.decision] || 0) + 1
    confidence[r.confidence] = (confidence[r.confidence] || 0) + 1
    if (r.strategy) strategies[r.strategy] = (strategies[r.strategy] || 0) + 1
  })
  return { total, decisions, confidence, strategies }
}

function getCostData(executions: any[], recs: any[]) {
  const tradingFees = executions.filter(e => e.success && !e.action?.includes('dry-run')).length * 0.02
  const apiCalls = executions.length + recs.length
  const modelCosts: Record<string, { input: number; output: number; callsEstimate: number }> = {
    'gemini-2.5-flash': { input: 0.00015, output: 0.0006, callsEstimate: Math.round(apiCalls * 0.5) },
    'claude-sonnet-4-5': { input: 0.003, output: 0.015, callsEstimate: Math.round(apiCalls * 0.1) },
    'gpt-4o': { input: 0.0025, output: 0.01, callsEstimate: Math.round(apiCalls * 0.15) },
    'grok': { input: 0.005, output: 0.015, callsEstimate: Math.round(apiCalls * 0.05) },
    'deepseek': { input: 0.00014, output: 0.00028, callsEstimate: Math.round(apiCalls * 0.15) },
    'r1': { input: 0.0008, output: 0.0016, callsEstimate: Math.round(apiCalls * 0.05) },
  }
  const avgTokensPerCall = 800
  const tokenBreakdown = Object.entries(modelCosts).map(([model, cost]) => ({
    model, calls: cost.callsEstimate, tokensUsed: cost.callsEstimate * avgTokensPerCall,
    costInput: (cost.callsEstimate * avgTokensPerCall * cost.input) / 1000,
    costOutput: (cost.callsEstimate * avgTokensPerCall * cost.output) / 1000,
    totalCost: (cost.callsEstimate * avgTokensPerCall * (cost.input + cost.output)) / 1000,
  }))
  const totalApiCost = tokenBreakdown.reduce((sum, t) => sum + t.totalCost, 0)
  const totalTokens = tokenBreakdown.reduce((sum, t) => sum + t.tokensUsed, 0)
  const dailyCosts = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(); date.setDate(date.getDate() - (6 - i))
    return {
      date: date.toISOString().split('T')[0],
      tradingFees: tradingFees / 7 + Math.random() * 0.01,
      apiCost: totalApiCost / 7 + Math.random() * 0.05,
      gasFees: 0.001 + Math.random() * 0.003,
    }
  })
  return { tradingFees, totalApiCost, totalTokens, tokenBreakdown, dailyCosts, costPerTrade: executions.length > 0 ? (tradingFees + totalApiCost) / executions.length : 0 }
}

export async function GET(request: NextRequest) {
  const type = request.nextUrl.searchParams.get('type') || 'executions'

  switch (type) {
    case 'executions': {
      const data = parseJsonl(join(DATA_DIR, 'executions.jsonl'))
      const stats = getExecutionStats(data)
      return NextResponse.json({ data: data.slice(-100), stats, total: data.length })
    }
    case 'recommendations': {
      const data = parseJsonl(join(DATA_DIR, 'recommendations.jsonl'))
      const stats = getRecommendationStats(data)
      return NextResponse.json({ data, stats })
    }
    case 'simulated': {
      const data = parseJsonl(join(DATA_DIR, 'simulated_trades.jsonl'))
      return NextResponse.json({ data: data.slice(-100), total: data.length })
    }
    case 'costs': {
      const execs = parseJsonl(join(DATA_DIR, 'executions.jsonl'))
      const recs = parseJsonl(join(DATA_DIR, 'recommendations.jsonl'))
      return NextResponse.json(getCostData(execs, recs))
    }
    case 'balance': {
      const result = await proxyExecutor('/balance')
      return NextResponse.json(result)
    }
    case 'positions': {
      const result = await proxyExecutor('/positions')
      return NextResponse.json(result)
    }
    case 'health': {
      const result = await proxyExecutor('/health')
      return NextResponse.json(result)
    }
    case 'risk-events': {
      const data = parseJsonl(join(DATA_DIR, 'risk-events.jsonl'))
      return NextResponse.json({ events: data.slice(-50), total: data.length })
    }
    case 'risk-status': {
      const result = await proxyExecutor('/risk/status')
      return NextResponse.json(result)
    }
    case 'all': {
      const execs = parseJsonl(join(DATA_DIR, 'executions.jsonl'))
      const recs = parseJsonl(join(DATA_DIR, 'recommendations.jsonl'))
      const sims = parseJsonl(join(DATA_DIR, 'simulated_trades.jsonl'))
      const riskEvents = parseJsonl(join(DATA_DIR, 'risk-events.jsonl'))
      const [balance, positions, health] = await Promise.all([
        proxyExecutor('/balance'), proxyExecutor('/positions'), proxyExecutor('/health'),
      ])
      return NextResponse.json({
        executions: { data: execs.slice(-50), stats: getExecutionStats(execs), total: execs.length },
        recommendations: { data: recs, stats: getRecommendationStats(recs) },
        simulated: { total: sims.length },
        costs: getCostData(execs, recs),
        riskEvents: riskEvents.slice(-20),
        balance, positions, health,
      })
    }
    default:
      return NextResponse.json({ error: 'Invalid type' }, { status: 400 })
  }
}
