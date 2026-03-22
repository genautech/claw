import { NextResponse } from 'next/server'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const file = join(process.cwd(), '..', 'data', 'improvements.jsonl')

function parseJsonl(filepath: string) {
  if (!existsSync(filepath)) return []
  try {
    return readFileSync(filepath, 'utf-8')
      .trim().split('\n')
      .filter(Boolean)
      .map(l => {
        try { return JSON.parse(l) } catch { return null }
      })
      .filter(Boolean)
  } catch { return [] }
}

export async function GET() {
  const data = parseJsonl(file)
  return NextResponse.json({ improvements: data.reverse() })
}
