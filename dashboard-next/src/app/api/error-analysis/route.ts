import { NextRequest, NextResponse } from 'next/server'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const DATA_DIR = join(process.cwd(), '..', 'data')
const EXECS_FILE = join(DATA_DIR, 'executions.jsonl')

function parseJsonl(filepath: string): any[] {
  if (!existsSync(filepath)) return []
  try {
    return readFileSync(filepath, 'utf-8')
      .trim().split('\n').filter(Boolean)
      .map(line => { try { return JSON.parse(line) } catch { return null } })
      .filter(Boolean)
  } catch { return [] }
}

export async function GET() {
  const execs = parseJsonl(EXECS_FILE)
  
  const errors = execs.filter((e: any) => !e.success && e.error)
  const now = new Date()
  
  const typeMap: Record<string, { count: number, lastSeen: string, impact: string, trend: number }> = {}

  errors.forEach((e: any) => {
    const err = String(e.error)
    let type = 'Other'
    let impact = 'Low'
    
    if (err.includes('balance') || err.includes('allowance')) {
      type = 'Balance/Allowance'
      impact = 'High - Trade blocked'
    } else if (err.includes('Invalid market') || err.includes('Unknown market')) {
      type = 'Invalid Market ID'
      impact = 'Medium - Skipped order'
    } else if (err.includes('invalid signature') || err.includes('signature validation failed')) {
      type = 'Invalid Signature'
      impact = 'High - Auth failure'
    } else if (err.includes('size lower') || err.includes('lower than the minimum')) {
      type = 'Size Too Small'
      impact = 'Medium - Order rejected'
    } else if (err.includes('POLYMARKET_PK') || err.includes('api_key') || err.includes('Unauthorized')) {
      type = 'Auth/Config Error'
      impact = 'Critical - System down'
    } else if (err.includes('division by zero')) {
      type = 'Division by Zero'
      impact = 'Medium - Calculation error'
    } else if (err.includes('price')) {
      type = 'Price Error'
      impact = 'Medium - Execution blocked'
    }
    
    if (!typeMap[type]) typeMap[type] = { count: 0, lastSeen: e.timestamp, impact, trend: 0 }
    typeMap[type].count += 1
    
    // update lastSeen
    if (new Date(e.timestamp) > new Date(typeMap[type].lastSeen)) {
      typeMap[type].lastSeen = e.timestamp
    }
    
    // trend: how many in last 24h
    const ts = new Date(e.timestamp)
    if (now.getTime() - ts.getTime() < 24 * 60 * 60 * 1000) {
      typeMap[type].trend += 1
    }
  })

  // Recommend fixes based on types
  const recommendedFixes: Record<string, string> = {
    'Balance/Allowance': 'Auto-approve USDC and pause agent if balance < reserve',
    'Size Too Small': 'Enforce minimum order size of 5 USDC in settings',
    'Invalid Market ID': 'Pre-validate market ID format against API schema',
    'Auth/Config Error': 'Agent should test credentials and prompt on startup',
    'Division by Zero': 'Guard against currentPrice = 0 or null',
    'Invalid Signature': 'Sync server time and verify L1 wallet state',
    'Price Error': 'Adjust slippage max and implement retry with backoff',
    'Other': 'Inspect raw logs to identify root cause'
  }

  const analysis = Object.entries(typeMap).map(([type, data]) => {
    const severityScore = data.count * (data.impact.includes('High') || data.impact.includes('Critical') ? 3 : 1)
    let severity = 'Low'
    if (severityScore > 20) severity = 'Critical'
    else if (severityScore > 10) severity = 'High'
    else if (severityScore > 5) severity = 'Medium'
    
    return {
      type,
      ...data,
      severity,
      severityScore,
      recommendedFix: recommendedFixes[type] || recommendedFixes['Other']
    }
  }).sort((a, b) => b.severityScore - a.severityScore)

  return NextResponse.json({
    totalErrors: errors.length,
    analysis
  })
}
