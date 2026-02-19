/**
 * API Client for Cloud Run Backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://clawdbot-api-xxxxx-uc.a.run.app'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || ''

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
}

export interface Config {
  gateway?: any
  channels?: any
  skills?: any
  tools?: any
}

export interface Prediction {
  market_id: string
  market_question: string
  edge: number
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  decision: string
  source?: string
  data_sources?: string[]
  timestamp?: string
}

export interface Trade {
  trade_id: string
  market_id: string
  side: 'YES' | 'NO'
  size: number
  entry_price: number
  exit_price?: number
  status: 'open' | 'closed' | 'closing'
  pnl: number
  timestamp?: string
}

export interface Metric {
  type: 'latency' | 'exposure' | 'win_rate'
  value: number
  component?: string
  timestamp?: string
}

export async function getConfig(): Promise<Config | null> {
  const response = await fetch(`${API_BASE_URL}/config`, { headers })
  const data = await response.json()
  return data.success ? data.data : null
}

export async function updateConfig(config: Partial<Config>): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/config`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(config),
  })
  const data = await response.json()
  return data.success
}

export async function createPrediction(prediction: Prediction): Promise<string | null> {
  const response = await fetch(`${API_BASE_URL}/predictions`, {
    method: 'POST',
    headers,
    body: JSON.stringify(prediction),
  })
  const data = await response.json()
  return data.success ? data.id : null
}

export async function getPredictions(marketId?: string, limit = 50): Promise<Prediction[]> {
  const params = new URLSearchParams({ limit: limit.toString() })
  if (marketId) params.append('market_id', marketId)
  
  const response = await fetch(`${API_BASE_URL}/predictions?${params}`, { headers })
  const data = await response.json()
  return data.success ? data.data : []
}

export async function createTrade(trade: Trade): Promise<string | null> {
  const response = await fetch(`${API_BASE_URL}/trades`, {
    method: 'POST',
    headers,
    body: JSON.stringify(trade),
  })
  const data = await response.json()
  return data.success ? data.id : null
}

export async function getTrades(status?: string, limit = 50): Promise<Trade[]> {
  const params = new URLSearchParams({ limit: limit.toString() })
  if (status) params.append('status', status)
  
  const response = await fetch(`${API_BASE_URL}/trades?${params}`, { headers })
  const data = await response.json()
  return data.success ? data.data : []
}

export async function createMetric(metric: Metric): Promise<string | null> {
  const response = await fetch(`${API_BASE_URL}/metrics`, {
    method: 'POST',
    headers,
    body: JSON.stringify(metric),
  })
  const data = await response.json()
  return data.success ? data.id : null
}

export async function getMetrics(metricType?: string, limit = 100): Promise<Metric[]> {
  const params = new URLSearchParams({ limit: limit.toString() })
  if (metricType) params.append('metric_type', metricType)
  
  const response = await fetch(`${API_BASE_URL}/metrics?${params}`, { headers })
  const data = await response.json()
  return data.success ? data.data : []
}

export async function getPolyclawPositions(agentId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/polyclaw/${agentId}/positions`, { headers })
  return response.json()
}

export async function getPolyclawTrades(agentId: string, limit = 50): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/polyclaw/${agentId}/trades?limit=${limit}`, { headers })
  return response.json()
}

export async function getPolyclawMetrics(agentId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/polyclaw/${agentId}/metrics`, { headers })
  return response.json()
}
