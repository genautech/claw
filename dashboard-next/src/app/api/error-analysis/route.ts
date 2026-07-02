import { NextResponse } from 'next/server'
import { buildErrorAnalysis, getExecutionsCached } from '@/lib/aggregates'

export async function GET() {
  const { all } = getExecutionsCached()
  return NextResponse.json(buildErrorAnalysis(all))
}
