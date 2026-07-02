import { readFileSync, writeFileSync, existsSync } from 'fs'
import { join } from 'path'
import os from 'os'

export const CONFIG_FILE = join(process.cwd(), '..', 'data', 'dashboard-config.json')
export const OPENCLAW_CONFIG = join(os.homedir(), '.openclaw', 'openclaw.json')

export const DEFAULT_CONFIG = {
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

export function getDashboardConfig() {
  try {
    if (existsSync(CONFIG_FILE)) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(readFileSync(CONFIG_FILE, 'utf-8')) }
    }
  } catch {
    // fall through
  }
  return { ...DEFAULT_CONFIG }
}

export function saveDashboardConfig(updates: Record<string, unknown>) {
  const updated = { ...getDashboardConfig(), ...updates }
  writeFileSync(CONFIG_FILE, JSON.stringify(updated, null, 2))
  return updated
}

export function syncDryRunToOpenclaw(dryRun: boolean): { synced: boolean; message?: string } {
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
