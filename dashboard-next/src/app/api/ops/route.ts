import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'
import { spawnBackground } from '@/lib/spawnBackground'

const LOGS_DIR = join(process.cwd(), '..', 'logs')

export const dynamic = 'force-dynamic'

export async function POST(request: NextRequest) {
  try {
    const { action } = await request.json()
    switch (action) {
      case 'process-recs': {
        const logFile = '/tmp/process-recs-dashboard.log'
        spawnBackground('python3', ['scripts/polymarket-exec.py', '--process-recs'], logFile)
        return NextResponse.json({ ok: true, action, logFile })
      }
      case 'analyze-bots': {
        const logFile = '/tmp/polybot-analyze.log'
        spawnBackground('python3', ['scripts/agent_polybot_analyzer.py', '--all'], logFile)
        return NextResponse.json({ ok: true, action, logFile })
      }
      case 'calibrate-edge': {
        const logFile = '/tmp/polybot-calibrate.log'
        spawnBackground(
          'python3',
          ['scripts/agent_polybot_analyzer.py', '--all', '--apply-config'],
          logFile
        )
        return NextResponse.json({ ok: true, action, logFile })
      }
      case 'check-latency': {
        const logFile = '/tmp/latency-ninja-dashboard.log'
        spawnBackground('bash', ['scripts/run-agents.sh', 'ninja'], logFile)
        const reportPath = join(LOGS_DIR, 'latency-report.json')
        let report = null
        if (existsSync(reportPath)) {
          try {
            report = JSON.parse(readFileSync(reportPath, 'utf-8'))
          } catch {
            report = null
          }
        }
        return NextResponse.json({ ok: true, action, logFile, reportPath, report })
      }
      default:
        return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 })
    }
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
