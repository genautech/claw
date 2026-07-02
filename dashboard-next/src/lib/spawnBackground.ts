import { spawn } from 'child_process'
import { openSync } from 'fs'
import { readFileSync } from 'fs'
import { join } from 'path'
import os from 'os'

const PROJECT_ROOT = join(process.cwd(), '..')

export function loadExecutorEnv(): Record<string, string> {
  const configPath = join(os.homedir(), '.openclaw', 'openclaw.json')
  try {
    const cfg = JSON.parse(readFileSync(configPath, 'utf-8'))
    const env = cfg?.skills?.entries?.['polymarket-exec']?.env ?? {}
    const out: Record<string, string> = {}
    for (const [k, v] of Object.entries(env)) {
      if (v != null && v !== '') out[k] = String(v)
    }
    return out
  } catch {
    return {}
  }
}

export function spawnBackground(command: string, args: string[], logFile?: string): void {
  const stdio: ['ignore', number, number] | 'ignore' = logFile
    ? ['ignore', openSync(logFile, 'a'), openSync(logFile, 'a')]
    : 'ignore'

  const child = spawn(command, args, {
    cwd: PROJECT_ROOT,
    env: { ...process.env, ...loadExecutorEnv() },
    detached: true,
    stdio,
  })
  child.unref()
}
