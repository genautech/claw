import { NextRequest, NextResponse } from 'next/server'
import { getLoopConfig, saveLoopConfig } from '@/lib/loop'

export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json(getLoopConfig())
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const updated = saveLoopConfig(body)
    return NextResponse.json(updated)
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
