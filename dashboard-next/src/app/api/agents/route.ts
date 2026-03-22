import { NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import { join } from 'path'
import { statSync } from 'fs'

const execAsync = promisify(exec)
const PROJECT_ROOT = join(process.cwd(), '..')

const AGENT_MAP: Record<string, string> = {
  'PolyWhale': 'scripts/agent_polywhale.py',
  'Brimo': 'scripts/brimo.py',
  'CorrectionAgent': 'scripts/correction_agent.py',
  'Executor': 'scripts/polymarket-exec.py'
}

export async function GET() {
  try {
    const statuses = Object.keys(AGENT_MAP).reduce((acc, name) => {
      acc[name] = 'offline'
      try {
        const logStat = statSync(`/tmp/${name.toLowerCase()}.log`)
        // If log was modified in the last 2 minutes, code is active
        if (Date.now() - logStat.mtimeMs < 120000) {
          acc[name] = 'active'
        }
      } catch (e) {
        // file unexistent, definitely offline
      }
      return acc
    }, {} as Record<string, string>)
    
    // Executor API double check
    try {
      const res = await fetch('http://127.0.0.1:8789/health')
      if (res.ok) statuses['Executor'] = 'active'
    } catch {}

    return NextResponse.json({ statuses })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}

export async function POST(request: Request) {
  try {
    const { agent, action } = await request.json()
    const script = AGENT_MAP[agent]
    
    if (!script) return NextResponse.json({ error: 'Unknown agent' }, { status: 400 })
    
    if (action === 'stop') {
      await execAsync(`pkill -f "python3 ${script}"`).catch(() => {})
      return NextResponse.json({ success: true, status: 'offline' })
    } else if (action === 'start') {
      const logFile = `/tmp/${agent.toLowerCase()}.log`
      const serveArg = agent === 'Executor' ? '--serve' : ''
      await execAsync(`nohup python3 ${script} ${serveArg} > ${logFile} 2>&1 &`, { cwd: PROJECT_ROOT }).catch(() => {})
      return NextResponse.json({ success: true, status: 'active' })
    }
    
    return NextResponse.json({ error: 'Invalid action' }, { status: 400 })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
