import { readFileSync, writeFileSync, existsSync } from 'fs'
import { join } from 'path'

export const REGISTRY_FILE = join(process.cwd(), '..', 'data', 'agent-registry.json')

export interface AgentRegistryEntry {
  agent: string
  pid: number
  startedAt: string
  command: string
}

export type AgentRegistry = Record<string, AgentRegistryEntry>

export function readRegistry(): AgentRegistry {
  try {
    if (existsSync(REGISTRY_FILE)) {
      return JSON.parse(readFileSync(REGISTRY_FILE, 'utf-8')) as AgentRegistry
    }
  } catch {
    // fall through
  }
  return {}
}

export function writeRegistry(registry: AgentRegistry) {
  writeFileSync(REGISTRY_FILE, JSON.stringify(registry, null, 2))
}

export function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

export function getRegistryEntry(agent: string): AgentRegistryEntry | null {
  const entry = readRegistry()[agent]
  if (!entry) return null
  if (!isPidAlive(entry.pid)) {
    const reg = readRegistry()
    delete reg[agent]
    writeRegistry(reg)
    return null
  }
  return entry
}

export function setRegistryEntry(agent: string, entry: AgentRegistryEntry) {
  const reg = readRegistry()
  reg[agent] = entry
  writeRegistry(reg)
}

export function removeRegistryEntry(agent: string) {
  const reg = readRegistry()
  delete reg[agent]
  writeRegistry(reg)
}
