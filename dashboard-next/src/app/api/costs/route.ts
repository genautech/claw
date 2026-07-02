import { NextResponse } from 'next/server'
import { buildCostPayload } from '@/lib/costs'

export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json(buildCostPayload())
}
