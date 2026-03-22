import { NextResponse } from 'next/server'
import { join } from 'path'
import { appendFileSync, readFileSync, existsSync } from 'fs'

const PROJECT_ROOT = join(process.cwd(), '..')
const CORRECTIONS_LOG = join(PROJECT_ROOT, 'data', 'approved_corrections.jsonl')
const EXECUTED_LOG = join(PROJECT_ROOT, 'data', 'executed_corrections.jsonl')

export async function GET() {
  try {
    let corrections: any[] = []
    
    // Parse pending approvals
    if (existsSync(CORRECTIONS_LOG)) {
      const pendingRaw = readFileSync(CORRECTIONS_LOG, 'utf-8')
      const pending = pendingRaw.trim().split('\n').filter(Boolean).map(line => {
        try {
          const d = JSON.parse(line)
          return {
            id: d.timestamp,
            status: 'pending',
            errorType: d.errorName,
            severity: 'High',
            description: 'Aguardando execução do agente',
            fix: d.action,
            timestamp: d.timestamp
          }
        } catch { return null }
      }).filter(Boolean)
      corrections = [...corrections, ...pending]
    }
    
    // Parse executed fixes and overwrite pending status
    if (existsSync(EXECUTED_LOG)) {
      const executedRaw = readFileSync(EXECUTED_LOG, 'utf-8')
      const executed = executedRaw.trim().split('\n').filter(Boolean).map(line => {
        try {
          const d = JSON.parse(line)
          return {
            id: d.timestamp,
            status: d.status === 'completed' ? 'applied' : 'failed',
            errorType: d.errorName,
            severity: 'High',
            description: d.result_message || 'Executado com sucesso',
            fix: d.action,
            timestamp: d.executed_at || d.timestamp
          }
        } catch { return null }
      }).filter(Boolean)
      
      // Merge: if a pending correction was executed, replace it with the executed one
      const executedMap = new Map(executed.map(e => [e?.id, e]))
      corrections = corrections.map(c => executedMap.get(c?.id) || c)
      // Add any executed that somehow weren't pending
      executed.forEach(e => {
        if (e && !corrections.find(c => c?.id === e.id)) corrections.push(e)
      })
    }
    
    // Sort descending by timestamp
    corrections.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    
    return NextResponse.json({ corrections })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}


export async function POST(request: Request) {
  try {
    const body = await request.json()
    const payload = {
      timestamp: new Date().toISOString(),
      status: 'pending',
      ...body
    }
    
    // Append to approved_corrections.jsonl
    appendFileSync(CORRECTIONS_LOG, JSON.stringify(payload) + '\n', 'utf-8')
    
    return NextResponse.json({ success: true })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
