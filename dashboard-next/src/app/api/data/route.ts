import { NextRequest, NextResponse } from 'next/server'
import { join } from 'path'
import { buildCostPayload } from '@/lib/costs'
import {
  getExecutionsCached,
  getRecommendationsCached,
  getSimulatedCached,
  getRiskEventsCached,
} from '@/lib/aggregates'

const EXECUTOR_URL = process.env.EXECUTOR_URL || 'http://127.0.0.1:8789'
const EXEC_TOKEN = process.env.EXEC_API_TOKEN || 'change-me-in-production'

async function proxyExecutor(path: string): Promise<Record<string, unknown>> {
  try {
    const res = await fetch(`${EXECUTOR_URL}${path}`, {
      headers: { Authorization: `Bearer ${EXEC_TOKEN}` },
      signal: AbortSignal.timeout(5000),
    })
    if (!res.ok) return { error: `Executor returned ${res.status}`, offline: true }
    return await res.json()
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return { error: message, offline: true }
  }
}

export async function GET(request: NextRequest) {
  const type = request.nextUrl.searchParams.get('type') || 'executions'

  switch (type) {
    case 'executions': {
      const { all, stats } = getExecutionsCached()
      return NextResponse.json({ data: all.slice(-100), stats, total: all.length })
    }
    case 'recommendations': {
      const { all, stats } = getRecommendationsCached()
      return NextResponse.json({ data: all.slice(-100), stats, total: all.length })
    }
    case 'simulated': {
      const { all, total } = getSimulatedCached()
      return NextResponse.json({ data: all.slice(-100), total })
    }
    case 'costs': {
      return NextResponse.json(buildCostPayload())
    }
    case 'balance': {
      return NextResponse.json(await proxyExecutor('/balance'))
    }
    case 'positions': {
      return NextResponse.json(await proxyExecutor('/positions'))
    }
    case 'health': {
      return NextResponse.json(await proxyExecutor('/health'))
    }
    case 'risk-events': {
      const { all, total } = getRiskEventsCached()
      return NextResponse.json({ events: all.slice(-50), total })
    }
    case 'risk-status': {
      return NextResponse.json(await proxyExecutor('/risk/status'))
    }
    case 'summary': {
      const { all: execs, stats: execStats } = getExecutionsCached()
      const { stats: recStats, all: recs } = getRecommendationsCached()
      const { total: simTotal } = getSimulatedCached()
      const [balance, health, positions] = await Promise.all([
        proxyExecutor('/balance'),
        proxyExecutor('/health'),
        proxyExecutor('/positions'),
      ])
      return NextResponse.json({
        executions: { stats: execStats, data: execs.slice(-20), total: execs.length },
        recommendations: { stats: recStats },
        simulated: { total: simTotal },
        balance,
        health,
        positions,
      })
    }
    case 'all': {
      const [{ all: execs, stats: execStats }, { all: recs, stats: recStats }, { total: simTotal }, { all: riskEvents }] =
        await Promise.all([
          Promise.resolve(getExecutionsCached()),
          Promise.resolve(getRecommendationsCached()),
          Promise.resolve(getSimulatedCached()),
          Promise.resolve(getRiskEventsCached()),
        ])
      const [balance, positions, health] = await Promise.all([
        proxyExecutor('/balance'),
        proxyExecutor('/positions'),
        proxyExecutor('/health'),
      ])
      return NextResponse.json({
        executions: { data: execs.slice(-50), stats: execStats, total: execs.length },
        recommendations: { data: recs.slice(-50), stats: recStats, total: recs.length },
        simulated: { total: simTotal },
        costs: buildCostPayload(),
        riskEvents: riskEvents.slice(-20),
        balance,
        positions,
        health,
      })
    }
    default:
      return NextResponse.json({ error: 'Invalid type' }, { status: 400 })
  }
}
