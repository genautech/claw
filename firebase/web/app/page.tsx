'use client'

import { useEffect, useState } from 'react'
import { getConfig, getPredictions, getTrades, getMetrics } from '@/lib/api'
import {
  getConfigDirect,
  getPredictionsDirect,
  getTradesDirect,
  getMetricsDirect,
} from '@/lib/firestore'

/** Try Firestore direct first, fall back to Cloud Run API */
async function loadWithFallback<T>(
  directFn: () => Promise<T>,
  apiFn: () => Promise<T>
): Promise<T> {
  try {
    return await directFn()
  } catch {
    console.warn('[ClawdBot] Firestore direct failed, falling back to API')
    return apiFn()
  }
}

export default function Home() {
  const [config, setConfig] = useState<any>(null)
  const [predictions, setPredictions] = useState<any[]>([])
  const [trades, setTrades] = useState<any[]>([])
  const [metrics, setMetrics] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState<'firestore' | 'api' | ''>('')

  useEffect(() => {
    async function loadData() {
      try {
        // Try direct Firestore first
        let usedFirestore = true
        try {
          const [configData, predictionsData, tradesData, metricsData] = await Promise.all([
            getConfigDirect(),
            getPredictionsDirect(undefined, 10),
            getTradesDirect('open', 10),
            getMetricsDirect('latency', 10),
          ])
          setConfig(configData)
          setPredictions(predictionsData)
          setTrades(tradesData)
          setMetrics(metricsData)
        } catch {
          usedFirestore = false
          // Fallback to API
          const [configData, predictionsData, tradesData, metricsData] = await Promise.all([
            getConfig(),
            getPredictions(undefined, 10),
            getTrades('open', 10),
            getMetrics('latency', 10),
          ])
          setConfig(configData)
          setPredictions(predictionsData)
          setTrades(tradesData)
          setMetrics(metricsData)
        }
        setSource(usedFirestore ? 'firestore' : 'api')
      } catch (error) {
        console.error('Error loading data:', error)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        {source && (
          <span className="text-xs px-2 py-1 rounded bg-gray-700 text-gray-400">
            {source === 'firestore' ? '🔥 Firestore Direct' : '☁️ Cloud Run API'}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Open Positions</div>
          <div className="text-2xl font-bold">{trades.length}</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Recent Predictions</div>
          <div className="text-2xl font-bold">{predictions.length}</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Latency Metrics</div>
          <div className="text-2xl font-bold">{metrics.length}</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Config Status</div>
          <div className="text-2xl font-bold">{config ? '✅' : '❌'}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-800 p-6 rounded-lg">
          <h2 className="text-xl font-bold mb-4">Recent Predictions</h2>
          {predictions.length > 0 ? (
            <ul className="space-y-2">
              {predictions.slice(0, 5).map((p: any, i: number) => (
                <li key={i} className="text-sm">
                  <div className="font-medium">{p.market_question}</div>
                  <div className="text-gray-400">Edge: {(p.edge * 100).toFixed(1)}% | {p.confidence}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400">No predictions yet</p>
          )}
        </div>

        <div className="bg-gray-800 p-6 rounded-lg">
          <h2 className="text-xl font-bold mb-4">Open Trades</h2>
          {trades.length > 0 ? (
            <ul className="space-y-2">
              {trades.slice(0, 5).map((t: any, i: number) => (
                <li key={i} className="text-sm">
                  <div className="font-medium">Market: {t.market_id.slice(0, 16)}...</div>
                  <div className="text-gray-400">Side: {t.side} | Size: ${t.size} | PnL: ${t.pnl.toFixed(2)}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400">No open trades</p>
          )}
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">System Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-sm text-gray-400">Gateway</div>
            <div className="font-medium">{config?.gateway?.mode || 'Unknown'}</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Port</div>
            <div className="font-medium">{config?.gateway?.port || 'N/A'}</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Telegram</div>
            <div className="font-medium">{config?.channels?.telegram ? '✅' : '❌'}</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Skills</div>
            <div className="font-medium">{Object.keys(config?.skills?.entries || {}).length}</div>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Firebase Project</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-400">Project ID</div>
            <div className="font-medium">openslaver</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Region</div>
            <div className="font-medium">us-east1</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Data Source</div>
            <div className="font-medium">{source === 'firestore' ? 'Firestore Direct 🔥' : 'Cloud Run API ☁️'}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
