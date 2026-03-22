import { NextResponse } from 'next/server'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const PROJECT_ROOT = join(process.cwd(), '..')
const NINJA_LOG = join(PROJECT_ROOT, 'data', 'ninja_trades.jsonl')

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const limit = parseInt(searchParams.get('limit') || '100')

  if (!existsSync(NINJA_LOG)) {
    return NextResponse.json([])
  }

  try {
    const raw = readFileSync(NINJA_LOG, 'utf-8')
    const trades = raw
      .trim()
      .split('\n')
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line)
        } catch {
          return null
        }
      })
      .filter(Boolean)
      .reverse()
      .slice(0, limit)

    return NextResponse.json(trades)
  } catch (e) {
    return NextResponse.json({ error: 'Failed to read ninja trades' }, { status: 500 })
  }
}
