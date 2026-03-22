import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, writeFileSync, existsSync } from 'fs'
import { join } from 'path'

const CONFIG_FILE = join(process.cwd(), '..', 'data', 'dashboard-config.json')

const DEFAULT_CONFIG = {
  goal: 10000,
  goalDays: 30,
  minTrade: 0.5,
  maxTrade: 5,
  maxDaily: 20,
  dryRun: true,
  minConfidence: 'MEDIUM',
  minEdge: 5,
  autoExecute: false,
  capitalInitial: 9,
  // Risk Management (Brimo)
  reserveFloor: 3,
  takeProfit: 20,
  stopLoss: 15,
  trailingStop: 10,
  maxDailyExposure: 20,
}

function getConfig() {
  try {
    if (existsSync(CONFIG_FILE)) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(readFileSync(CONFIG_FILE, 'utf-8')) }
    }
  } catch {}
  return DEFAULT_CONFIG
}

export async function GET() {
  return NextResponse.json(getConfig())
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const current = getConfig()
    const updated = { ...current, ...body }
    writeFileSync(CONFIG_FILE, JSON.stringify(updated, null, 2))
    return NextResponse.json(updated)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
