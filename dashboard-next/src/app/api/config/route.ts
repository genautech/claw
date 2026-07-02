import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, writeFileSync, existsSync } from 'fs'
import { join } from 'path'
import os from 'os'

const CONFIG_FILE = join(process.cwd(), '..', 'data', 'dashboard-config.json')
const OPENCLAW_CONFIG = join(os.homedir(), '.openclaw', 'openclaw.json')

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
  } catch {
    // fall through
  }
  return DEFAULT_CONFIG
}

function syncDryRunToOpenclaw(dryRun: boolean): { synced: boolean; message?: string } {
  try {
    if (!existsSync(OPENCLAW_CONFIG)) {
      return { synced: false, message: 'openclaw.json não encontrado' }
    }
    const cfg = JSON.parse(readFileSync(OPENCLAW_CONFIG, 'utf-8'))
    if (!cfg.skills) cfg.skills = {}
    if (!cfg.skills.entries) cfg.skills.entries = {}
    if (!cfg.skills.entries['polymarket-exec']) {
      cfg.skills.entries['polymarket-exec'] = { enabled: true, env: {} }
    }
    if (!cfg.skills.entries['polymarket-exec'].env) {
      cfg.skills.entries['polymarket-exec'].env = {}
    }
    cfg.skills.entries['polymarket-exec'].env.DRY_RUN = dryRun ? 'true' : 'false'
    writeFileSync(OPENCLAW_CONFIG, JSON.stringify(cfg, null, 2))
    return { synced: true }
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'sync failed'
    return { synced: false, message }
  }
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

    let syncResult: { synced: boolean; message?: string } = { synced: false }
    if (typeof body.dryRun === 'boolean') {
      syncResult = syncDryRunToOpenclaw(body.dryRun)
    }

    return NextResponse.json({
      ...updated,
      _sync: syncResult,
      _executorRestartHint: syncResult.synced
        ? 'Reinicie o executor para aplicar DRY_RUN: bash scripts/start-executor.sh'
        : undefined,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
