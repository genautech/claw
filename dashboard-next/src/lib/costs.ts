import { join } from 'path'
import { readJsonlFull } from '@/lib/jsonl'
import { getExecutionsCached, getRecommendationsCached } from '@/lib/aggregates'

const DATA_DIR = join(process.cwd(), '..', 'data')

export function parseJsonl(filepath: string) {
  return readJsonlFull(filepath)
}

export interface AgentCostRow {
  agent: string
  model: string
  source: string
  tokensIn: number
  tokensOut: number
  tokensUsed: number
  costUsd: number
  calls: number
}

export interface CostPayload {
  tradingFees: number
  totalApiCost: number
  totalTokens: number
  costPerTrade: number
  gasFees: number
  tokenBreakdown: {
    model: string
    calls: number
    tokensUsed: number
    costInput: number
    costOutput: number
    totalCost: number
  }[]
  agentBreakdown: AgentCostRow[]
  dailyCosts: {
    date: string
    tradingFees: number
    apiCost: number
    gasFees: number
  }[]
  _estimated: boolean
  lastCollectedAt: string | null
}

function estimateFromExecutions(execs: Record<string, unknown>[], recs: Record<string, unknown>[]): CostPayload {
  const tradingFees = execs.filter(
    (e) => e.success && !(String(e.action || '').includes('dry-run')),
  ).length * 0.02
  const apiCalls = execs.length + recs.length
  const modelCosts: Record<string, { input: number; output: number; callsEstimate: number }> = {
    'gemini-2.5-flash': { input: 0.00015, output: 0.0006, callsEstimate: Math.round(apiCalls * 0.5) },
    'claude-sonnet-4-5': { input: 0.003, output: 0.015, callsEstimate: Math.round(apiCalls * 0.1) },
    'gpt-4o': { input: 0.0025, output: 0.01, callsEstimate: Math.round(apiCalls * 0.15) },
    grok: { input: 0.005, output: 0.015, callsEstimate: Math.round(apiCalls * 0.05) },
    deepseek: { input: 0.00014, output: 0.00028, callsEstimate: Math.round(apiCalls * 0.15) },
    r1: { input: 0.0008, output: 0.0016, callsEstimate: Math.round(apiCalls * 0.05) },
  }
  const avgTokensPerCall = 800
  const tokenBreakdown = Object.entries(modelCosts).map(([model, cost]) => ({
    model,
    calls: cost.callsEstimate,
    tokensUsed: cost.callsEstimate * avgTokensPerCall,
    costInput: (cost.callsEstimate * avgTokensPerCall * cost.input) / 1000,
    costOutput: (cost.callsEstimate * avgTokensPerCall * cost.output) / 1000,
    totalCost: (cost.callsEstimate * avgTokensPerCall * (cost.input + cost.output)) / 1000,
  }))
  const totalApiCost = tokenBreakdown.reduce((sum, t) => sum + t.totalCost, 0)
  const totalTokens = tokenBreakdown.reduce((sum, t) => sum + t.tokensUsed, 0)
  const perDay = 7
  const dailyCosts = Array.from({ length: perDay }, (_, i) => {
    const date = new Date()
    date.setDate(date.getDate() - (perDay - 1 - i))
    return {
      date: date.toISOString().split('T')[0],
      tradingFees: tradingFees / perDay,
      apiCost: totalApiCost / perDay,
      gasFees: 0,
    }
  })
  return {
    tradingFees,
    totalApiCost,
    totalTokens,
    tokenBreakdown,
    agentBreakdown: [],
    dailyCosts,
    gasFees: 0,
    costPerTrade: execs.length > 0 ? (tradingFees + totalApiCost) / execs.length : 0,
    _estimated: true,
    lastCollectedAt: null,
  }
}

function aggregateTokenUsage(rows: Record<string, unknown>[]): {
  tokenBreakdown: CostPayload['tokenBreakdown']
  agentBreakdown: AgentCostRow[]
  totalApiCost: number
  totalTokens: number
  lastCollectedAt: string | null
} {
  const byModel: Record<string, { calls: number; tokensIn: number; tokensOut: number; costUsd: number }> = {}
  const byAgent: Record<string, AgentCostRow> = {}
  let lastCollectedAt: string | null = null

  for (const row of rows) {
    const model = String(row.model || 'unknown')
    const agent = String(row.agent || 'unknown')
    const source = String(row.source || 'openclaw_gateway')
    const tokensIn = Number(row.tokensIn || 0)
    const tokensOut = Number(row.tokensOut || 0)
    const costUsd = Number(row.costUsd || 0)
    const ts = String(row.timestamp || '')

    if (ts && (!lastCollectedAt || ts > lastCollectedAt)) lastCollectedAt = ts

    if (!byModel[model]) byModel[model] = { calls: 0, tokensIn: 0, tokensOut: 0, costUsd: 0 }
    byModel[model].calls += 1
    byModel[model].tokensIn += tokensIn
    byModel[model].tokensOut += tokensOut
    byModel[model].costUsd += costUsd

    const key = `${agent}::${model}::${source}`
    if (!byAgent[key]) {
      byAgent[key] = { agent, model, source, tokensIn: 0, tokensOut: 0, tokensUsed: 0, costUsd: 0, calls: 0 }
    }
    byAgent[key].tokensIn += tokensIn
    byAgent[key].tokensOut += tokensOut
    byAgent[key].tokensUsed += tokensIn + tokensOut
    byAgent[key].costUsd += costUsd
    byAgent[key].calls += 1
  }

  const tokenBreakdown = Object.entries(byModel).map(([model, v]) => ({
    model,
    calls: v.calls,
    tokensUsed: v.tokensIn + v.tokensOut,
    costInput: v.costUsd * 0.7,
    costOutput: v.costUsd * 0.3,
    totalCost: v.costUsd,
  }))

  const totalApiCost = tokenBreakdown.reduce((s, t) => s + t.totalCost, 0)
  const totalTokens = tokenBreakdown.reduce((s, t) => s + t.tokensUsed, 0)

  return {
    tokenBreakdown,
    agentBreakdown: Object.values(byAgent).sort((a, b) => b.costUsd - a.costUsd),
    totalApiCost,
    totalTokens,
    lastCollectedAt,
  }
}

function dailyFromExecutions(execs: Record<string, unknown>[]) {
  const byDay: Record<string, { tradingFees: number; gasFees: number }> = {}
  for (const e of execs) {
    const ts = String(e.timestamp || '')
    const day = ts.slice(0, 10)
    if (!day) continue
    if (!byDay[day]) byDay[day] = { tradingFees: 0, gasFees: 0 }
    if (e.success && !String(e.action || '').includes('dry-run')) {
      const fee = Number((e.details as Record<string, unknown>)?.feeUsd ?? (e.result as Record<string, unknown>)?.fee ?? 0.02)
      byDay[day].tradingFees += fee
      const gas = Number((e.details as Record<string, unknown>)?.gas_used ?? (e.result as Record<string, unknown>)?.gas ?? 0)
      byDay[day].gasFees += gas
    }
  }
  const days = Object.keys(byDay).sort()
  const last7 = days.slice(-7)
  return last7.map((date) => ({ date, tradingFees: byDay[date].tradingFees, apiCost: 0, gasFees: byDay[date].gasFees }))
}

export function buildCostPayload(): CostPayload {
  const execs = getExecutionsCached().all
  const recs = getRecommendationsCached().all
  const usage = parseJsonl(join(DATA_DIR, 'token-usage.jsonl'))

  if (usage.length === 0) {
    return estimateFromExecutions(execs, recs)
  }

  const agg = aggregateTokenUsage(usage)
  const liveFees = execs
    .filter((e) => e.success && !String(e.action || '').includes('dry-run'))
    .reduce((sum, e) => {
      const fee = Number((e.details as Record<string, unknown>)?.feeUsd ?? 0.02)
      return sum + fee
    }, 0)

  const gasFees = execs.reduce((sum, e) => {
    const gas = Number((e.details as Record<string, unknown>)?.gas_used ?? (e.result as Record<string, unknown>)?.gas ?? 0)
    return sum + gas
  }, 0)

  const dailyCosts = dailyFromExecutions(execs)
  const apiPerDay = agg.totalApiCost / Math.max(dailyCosts.length, 1)
  const dailyWithApi = dailyCosts.map((d) => ({ ...d, apiCost: apiPerDay }))

  return {
    tradingFees: liveFees,
    totalApiCost: agg.totalApiCost,
    totalTokens: agg.totalTokens,
    tokenBreakdown: agg.tokenBreakdown,
    agentBreakdown: agg.agentBreakdown,
    dailyCosts: dailyWithApi.length ? dailyWithApi : estimateFromExecutions(execs, recs).dailyCosts,
    gasFees,
    costPerTrade: execs.length > 0 ? (liveFees + agg.totalApiCost) / execs.length : 0,
    _estimated: false,
    lastCollectedAt: agg.lastCollectedAt,
  }
}
