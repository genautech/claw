import { NextResponse } from 'next/server'
import { join } from 'path'

const EXECUTOR_URL = process.env.EXECUTOR_URL || 'http://127.0.0.1:8789'
const EXEC_TOKEN = process.env.EXEC_API_TOKEN || 'change-me-in-production'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const res = await fetch(`${EXECUTOR_URL}/arbitrage`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${EXEC_TOKEN}`,
        'Content-Type': 'application/json' 
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    })
    
    if (!res.ok) {
        const txt = await res.text()
        return NextResponse.json({ error: `Executor error: ${txt}` }, { status: res.status })
    }
    
    const data = await res.json()
    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
