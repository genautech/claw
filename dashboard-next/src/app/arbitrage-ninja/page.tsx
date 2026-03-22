'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ReferenceLine
} from 'recharts'

// ======================== TYPES ========================
interface MarketData {
  question: string
  yesTokenId: string
  noTokenId: string
  yesPrice: number
  noPrice: number
  volume: number
  volume24h: number
  liquidity: number
}

interface SpreadPoint {
  time: string
  spread: number
  isOpp: boolean
}

interface Opportunity {
  time: string
  asset: string
  bestBid: number
  bestAsk: number
  spread: number
  profit: number
  cumPnl: number
}

interface OrderLevel {
  price: number
  size: number
}

interface LogEntry {
  msg: string
  type: 'info' | 'warn' | 'err' | 'opp'
  time: string
}

interface NinjaStats {
  ticks: number
  opportunities: number
  simulatedTrades: number
  simulatedPnl: number
  maxSpread: number
  currentSpread: number
  spreads: number[]
}

// ======================== CONSTANTS ========================
const GAMMA_API = 'https://gamma-api.polymarket.com'
const CLOB_WS = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'

// ======================== MAIN PAGE ========================
export default function ArbitrageNinjaPage() {
  // State
  const [marketId, setMarketId] = useState('')
  const [minSpread, setMinSpread] = useState('0.02')
  const [isRunning, setIsRunning] = useState(false)
  const [autoExecute, setAutoExecute] = useState(false)
  const [wsStatus, setWsStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected')
  const [currentMarket, setCurrentMarket] = useState<MarketData | null>(null)
  const [stats, setStats] = useState<NinjaStats>({
    ticks: 0, opportunities: 0, simulatedTrades: 0,
    simulatedPnl: 0, maxSpread: 0, currentSpread: 0, spreads: []
  })
  const [chartData, setChartData] = useState<SpreadPoint[]>([])
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [bids, setBids] = useState<OrderLevel[]>([])
  const [asks, setAsks] = useState<OrderLevel[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([
    { msg: '🥷 ArbitrageNinja ready. Connect to a market to start monitoring.', type: 'info', time: new Date().toLocaleTimeString() }
  ])
  const [history, setHistory] = useState<any[]>([])
  const [trendingMarkets, setTrendingMarkets] = useState<any[]>([])
  const [showTrending, setShowTrending] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(false)
  const [startTime, setStartTime] = useState<number | null>(null)
  const [uptime, setUptime] = useState('00:00')
  const [tickRate, setTickRate] = useState(0)

  // Refs
  const wsRef = useRef<WebSocket | null>(null)
  const statsRef = useRef(stats)
  const logRef = useRef<HTMLDivElement>(null)
  const lastTickCountRef = useRef(0)
  const audioCtxRef = useRef<AudioContext | null>(null)
  
  // Ref synced flags for the WS closure
  const autoExecRef = useRef(autoExecute)
  const isExecutingRef = useRef(false)
  const currentAssetRef = useRef('')

  statsRef.current = stats
  autoExecRef.current = autoExecute

  // ======================== AUDIO ========================
  const playBeep = useCallback(() => {
    if (!soundEnabled) return
    try {
      if (!audioCtxRef.current) audioCtxRef.current = new AudioContext()
      const ctx = audioCtxRef.current
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = 880
      osc.type = 'sine'
      gain.gain.value = 0.1
      osc.start()
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
      osc.stop(ctx.currentTime + 0.15)
    } catch {}
  }, [soundEnabled])

  // ======================== LOGGING ========================
  const addLog = useCallback((msg: string, type: LogEntry['type'] = 'info') => {
    const entry: LogEntry = { msg, type, time: new Date().toLocaleTimeString() }
    setLogs(prev => [...prev.slice(-299), entry])
  }, [])

  // ======================== TIMERS & AUTO-UPDATE ========================
  useEffect(() => {
    // Initial history load
    loadHistory()
    
    // Auto-refresh history every 5 seconds
    const historyInterval = setInterval(() => {
      loadHistory(true) // Pass true to avoid polluting logs every 5s
    }, 5000)

    return () => clearInterval(historyInterval)
  }, [])

  useEffect(() => {
    if (!isRunning || !startTime) return
    const uptimeInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      const m = Math.floor(elapsed / 60).toString().padStart(2, '0')
      const s = (elapsed % 60).toString().padStart(2, '0')
      setUptime(`${m}:${s}`)
    }, 1000)

    const rateInterval = setInterval(() => {
      const rate = statsRef.current.ticks - lastTickCountRef.current
      lastTickCountRef.current = statsRef.current.ticks
      setTickRate(rate)
    }, 1000)

    return () => {
      clearInterval(uptimeInterval)
      clearInterval(rateInterval)
    }
  }, [isRunning, startTime])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])

  // Auto-start with trending market on mount
  useEffect(() => {
    let isMounted = true
    const autoInitialize = async () => {
      try {
        const res = await fetch(`${GAMMA_API}/markets?closed=false&limit=1&order=volume24hr&ascending=false`)
        if (!res.ok) return
        const data = await res.json()
        if (data && data.length > 0 && isMounted) {
          setMarketId(data[0].id)
          startMonitoring(data[0].id)
        }
      } catch {}
    }
    setTimeout(autoInitialize, 500)
    return () => { isMounted = false }
  }, [])

  // ======================== GAMMA API ========================
  const fetchMarket = async (id: string): Promise<MarketData | null> => {
    try {
      const url = id.startsWith('0x')
        ? `${GAMMA_API}/markets?condition_id=${id}`
        : `${GAMMA_API}/markets/${id}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      let data = await res.json()
      if (Array.isArray(data)) data = data[0]
      if (!data) throw new Error('Market not found')

      const tokens = JSON.parse(data.clobTokenIds || '[]')
      const prices = JSON.parse(data.outcomePrices || '[0.5,0.5]')
      return {
        question: data.question || '',
        yesTokenId: tokens[0] || '',
        noTokenId: tokens[1] || '',
        yesPrice: parseFloat(prices[0]) || 0.5,
        noPrice: parseFloat(prices[1]) || 0.5,
        volume: parseFloat(data.volume || 0),
        volume24h: parseFloat(data.volume24hr || 0),
        liquidity: parseFloat(data.liquidity || 0),
      }
    } catch (e: any) {
      addLog(`❌ Failed to fetch market: ${e.message}`, 'err')
      return null
    }
  }

  const fetchTrending = async () => {
    addLog('🔥 Fetching trending markets...', 'info')
    try {
      const res = await fetch(`${GAMMA_API}/markets?closed=false&limit=10&order=volume24hr&ascending=false`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setTrendingMarkets(data)
      setShowTrending(true)
      addLog(`✅ Found ${data.length} trending markets.`, 'opp')
    } catch (e: any) {
      addLog(`❌ Failed to fetch trending: ${e.message}`, 'err')
    }
  }

  // ======================== WEBSOCKET ========================
  const startMonitoring = async (targetId?: string) => {
    if (isRunning) return
    const idToUse = targetId || marketId
    if (!idToUse.trim()) {
      addLog('⚠️ Please enter a market ID or click "Trending" to pick one.', 'warn')
      return
    }

    addLog(`🔍 Fetching market data for: ${idToUse}...`, 'info')
    setWsStatus('connecting')
    const market = await fetchMarket(idToUse.trim())
    if (!market) { setWsStatus('error'); return }

    setCurrentMarket(market)
    const assets = [market.yesTokenId, market.noTokenId].filter(Boolean)
    if (assets.length === 0) {
      addLog('❌ No token IDs found for this market.', 'err')
      setWsStatus('error')
      return
    }

    addLog(`✅ Market: ${market.question}`, 'info')
    addLog(`   YES: ${market.yesTokenId.substring(0, 20)}...`, 'info')
    addLog(`   NO: ${market.noTokenId ? market.noTokenId.substring(0, 20) + '...' : 'N/A'}`, 'info')
    addLog(`🔗 Connecting to CLOB WebSocket...`, 'info')

    try {
      const ws = new WebSocket(CLOB_WS)
      wsRef.current = ws

      ws.onopen = () => {
        setWsStatus('connected')
        ws.send(JSON.stringify({ assets_ids: assets, type: 'market' }))
        addLog('✅ Subscribed to order book stream!', 'opp')
        setIsRunning(true)
        setStartTime(Date.now())
        currentAssetRef.current = market.yesTokenId // Approximate for execution parameter
        setStats({ ticks: 0, opportunities: 0, simulatedTrades: 0, simulatedPnl: 0, maxSpread: 0, currentSpread: 0, spreads: [] })
        setChartData([])
        setOpportunities([])
        lastTickCountRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const events = Array.isArray(data) ? data : [data]
          events.forEach(evt => processEvent(evt))
        } catch {}
      }

      ws.onerror = () => {
        addLog('❌ WebSocket error', 'err')
        setWsStatus('error')
      }

      ws.onclose = () => {
        addLog('🔌 WebSocket closed', 'warn')
        setWsStatus('disconnected')
        setIsRunning(false)
      }
    } catch (e: any) {
      addLog(`❌ Connection failed: ${e.message}`, 'err')
      setWsStatus('error')
    }
  }

  const stopMonitoring = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsRunning(false)
    setWsStatus('disconnected')
    addLog('⏹ Monitoring stopped.', 'warn')
  }

  // ======================== PROCESS EVENT ========================
  const processEvent = (data: any) => {
    if (!data.bids || !data.asks) return

    const eventBids: OrderLevel[] = data.bids.slice(0, 10).map((b: any) => ({
      price: parseFloat(b.price), size: parseFloat(b.size)
    }))
    const eventAsks: OrderLevel[] = data.asks.slice(0, 10).map((a: any) => ({
      price: parseFloat(a.price), size: parseFloat(a.size)
    }))

    setBids(eventBids)
    setAsks(eventAsks)

    if (!data.bids.length || !data.asks.length) return

    try {
      const bestBid = parseFloat(data.bids[0].price)
      const bestAsk = parseFloat(data.asks[0].price)
      const spread = bestAsk - bestBid
      const assetId = data.asset_id || ''
      const threshold = parseFloat(document.getElementById('minSpreadHidden')?.getAttribute('data-value') || '0.02')

      setStats(prev => {
        const newSpreads = [...prev.spreads.slice(-199), spread]
        const newMaxSpread = Math.max(prev.maxSpread, spread)
        const newTicks = prev.ticks + 1

        // Opportunity check
        let newOpps = prev.opportunities
        let newSimTrades = prev.simulatedTrades
        let newSimPnl = prev.simulatedPnl

        if (spread > threshold) {
          newOpps++
          const buyPrice = bestBid + 0.001
          const sellPrice = bestAsk - 0.001
          const profit = sellPrice - buyPrice
          newSimTrades++
          newSimPnl += profit

          // Add opportunity
          setOpportunities(prevOpps => [{
            time: new Date().toLocaleTimeString(),
            asset: assetId.substring(0, 16) + '...',
            bestBid, bestAsk, spread, profit,
            cumPnl: newSimPnl
          }, ...prevOpps.slice(0, 99)])

          // Log every opportunity
          setLogs(prevLogs => [...prevLogs.slice(-299), {
            msg: `🤑 SPREAD #${newOpps}: $${spread.toFixed(4)} | BUY@${buyPrice.toFixed(3)} SELL@${sellPrice.toFixed(3)} | Profit: $${profit.toFixed(4)}`,
            type: 'opp' as const,
            time: new Date().toLocaleTimeString()
          }])

          // Live Execution Handling!
          if (autoExecRef.current && !isExecutingRef.current) {
            isExecutingRef.current = true
            setLogs(prevLogs => [...prevLogs.slice(-299), {
              msg: `⚡ AUTO-EXECUTING Spread Capture on ${assetId.substring(0, 8)}... (${spread.toFixed(4)} spread)`,
              type: 'warn' as const,
              time: new Date().toLocaleTimeString()
            }])
            
            // Dispatch to backend
            fetch('/api/ninja/execute', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                marketId: document.getElementById('marketIdHidden')?.getAttribute('data-value') || '',
                asset: currentAssetRef.current,
                bestBid: bestBid,
                bestAsk: bestAsk,
                spread: spread,
                profit: profit,
                sizeUsd: 1.0
              })
            }).then(r => r.json()).then(res => {
              if (res.error) {
                addLog(`❌ Auto-Exec Failed: ${res.error}`, 'err')
              } else {
                addLog(`✅ Auto-Exec Success! Realized PnL: $${res.pnl}`, 'opp')
              }
            }).catch(e => addLog(`❌ Auto-Exec Error: ${e.message}`, 'err'))
              .finally(() => {
                 setTimeout(() => { isExecutingRef.current = false }, 3000) // 3s cooldown between arb shots
              })
          }
        }

        // Log every 25 ticks
        if (newTicks % 25 === 0) {
          const avg = newSpreads.slice(-25).reduce((a, b) => a + b, 0) / Math.min(25, newSpreads.length)
          setLogs(prevLogs => [...prevLogs.slice(-299), {
            msg: `📊 Tick #${newTicks} | Spread: $${spread.toFixed(4)} | Avg(25): $${avg.toFixed(4)} | Opps: ${newOpps}`,
            type: 'info' as const,
            time: new Date().toLocaleTimeString()
          }])
        }

        return {
          ticks: newTicks,
          opportunities: newOpps,
          simulatedTrades: newSimTrades,
          simulatedPnl: newSimPnl,
          maxSpread: newMaxSpread,
          currentSpread: spread,
          spreads: newSpreads
        }
      })

      // Chart data
      const isOpp = spread > threshold
      setChartData(prev => [...prev.slice(-199), {
        time: new Date().toLocaleTimeString(),
        spread,
        isOpp
      }])

      if (isOpp) playBeep()

    } catch {}
  }

  // ======================== LOAD HISTORY ========================
  const loadHistory = async (silent: boolean = false) => {
    if (!silent) addLog('📜 Loading trade history...', 'info')
    try {
      const res = await fetch('/api/ninja?limit=50')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setHistory(data)
      if (!silent) addLog(`✅ Loaded ${data.length} history entries.`, 'opp')
    } catch (e: any) {
      if (!silent) addLog(`❌ Failed to load history: ${e.message}`, 'err')
    }
  }

  // Calculate derived stats
  const hitRate = stats.ticks > 0 ? (stats.opportunities / stats.ticks * 100).toFixed(1) : '0.0'
  const avgSpread = stats.spreads.length > 0
    ? (stats.spreads.slice(-50).reduce((a, b) => a + b, 0) / Math.min(50, stats.spreads.length)).toFixed(4)
    : '0.0000'
  const spreadMin = stats.spreads.length > 0 ? Math.min(...stats.spreads.slice(-50)).toFixed(4) : '0.0000'
  const spreadMax = stats.spreads.length > 0 ? Math.max(...stats.spreads.slice(-50)).toFixed(4) : '0.0000'

  // Spread intensity (0-1) for heatmap indicator
  const spreadIntensity = stats.maxSpread > 0 ? Math.min(stats.currentSpread / stats.maxSpread, 1) : 0
  const heatColor = spreadIntensity > 0.7 ? '#22c55e' : spreadIntensity > 0.4 ? '#f59e0b' : '#64748b'

  return (
    <div className="space-y-5 max-w-[1400px]">
      {/* Hidden elements for closures */}
      <input type="hidden" id="minSpreadHidden" data-value={minSpread} />
      <input type="hidden" id="marketIdHidden" data-value={marketId} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">🥷 ArbitrageNinja</h1>
          <p className="text-sm text-muted mt-1">High-Frequency Spread Monitor — Polymarket CLOB</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={wsStatus} />
          <span className="badge badge-info">Ticks: {stats.ticks.toLocaleString()}</span>
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition font-semibold ${
              soundEnabled
                ? 'bg-green-500/20 border-green-500/30 text-green-400'
                : 'bg-surface border-border text-muted'
            }`}
          >
            {soundEnabled ? '🔊 Sound ON' : '🔇 Sound OFF'}
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="glass-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-[10px] text-muted uppercase tracking-wider font-semibold whitespace-nowrap">Target Market:</span>
            <div className="flex-1 bg-surface-2 border border-border rounded-lg px-4 py-2 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] animate-pulse' : 'bg-red-500'}`}></span>
              <span className="text-sm font-semibold text-white truncate max-w-[400px]">
                {currentMarket ? currentMarket.question : (wsStatus === 'connecting' ? 'Auto-connecting to top trending market...' : 'Scanning for optimal market...')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted uppercase tracking-wider font-semibold whitespace-nowrap">Min Spread:</span>
            <input
              type="text"
              value={minSpread}
              onChange={(e) => setMinSpread(e.target.value)}
              className="w-20 bg-surface border border-border rounded-lg px-3 py-2 text-sm font-mono text-white outline-none focus:border-accent-2 focus:ring-1 focus:ring-accent-2/30 transition"
            />
          </div>

          {!isRunning ? (
            <button onClick={() => startMonitoring()}
              className="px-5 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-sm font-semibold hover:opacity-90 hover:shadow-lg hover:shadow-purple-500/20 transition active:scale-95">
              ▶ Connect
            </button>
          ) : (
            <button onClick={stopMonitoring}
              className="px-5 py-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-400 text-sm font-semibold hover:bg-red-500/30 transition active:scale-95">
              ⏹ Stop
            </button>
          )}
          <button onClick={() => fetchTrending()}
            className="px-4 py-2 rounded-lg bg-surface border border-border text-sm font-semibold text-white hover:border-accent-2 hover:bg-accent-2/10 transition active:scale-95 flex items-center gap-2">
            🔥 Change Market
          </button>
          <button onClick={() => loadHistory()}
            className="px-4 py-2 rounded-lg bg-surface border border-border text-sm font-semibold text-white hover:border-accent-2 hover:bg-accent-2/10 transition active:scale-95">
            📜 History
          </button>
        </div>
      </div>

      {/* Market Info */}
      {currentMarket && (
        <div className="glass-card p-4">
          <div className="text-base font-semibold text-white mb-2">{currentMarket.question}</div>
          <div className="flex flex-wrap gap-5 text-sm">
            <span className="text-muted">YES: <strong className="text-green-400">${currentMarket.yesPrice.toFixed(4)}</strong></span>
            <span className="text-muted">NO: <strong className="text-red-400">${currentMarket.noPrice.toFixed(4)}</strong></span>
            <span className="text-muted">Liquidity: <strong className="text-white">${currentMarket.liquidity.toLocaleString()}</strong></span>
            <span className="text-muted">Volume 24h: <strong className="text-white">${currentMarket.volume24h.toLocaleString()}</strong></span>
          </div>
        </div>
      )}

      {/* Trending Markets Modal */}
      {showTrending && trendingMarkets.length > 0 && (
        <div className="glass-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">🔥 Trending Markets — Click to select</h3>
            <button onClick={() => setShowTrending(false)}
              className="text-xs text-muted hover:text-white transition">✕ Close</button>
          </div>
          <div className="space-y-1 max-h-[300px] overflow-y-auto">
            {trendingMarkets.map((m: any, i: number) => {
              const prices = JSON.parse(m.outcomePrices || '[0.5,0.5]')
              const vol = parseFloat(m.volume24hr || 0)
              return (
                <div key={i}
                  onClick={() => { setMarketId(m.id); setShowTrending(false); addLog(`✅ Selected: ${m.question}`, 'opp') }}
                  className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-accent-2/10 cursor-pointer transition group"
                >
                  <span className="text-xs text-muted font-mono w-6">#{i + 1}</span>
                  <span className="flex-1 text-xs text-white group-hover:text-accent truncate">{m.question}</span>
                  <span className="text-xs font-mono text-green-400">${parseFloat(prices[0]).toFixed(2)}</span>
                  <span className="text-xs font-mono text-muted">${vol.toLocaleString()}/24h</span>
                  <span className="badge badge-info text-[9px]">Select</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <NinjaKpi label="📊 Ticks" value={stats.ticks.toLocaleString()} sub={`${tickRate}/s`} color="blue" />
        <NinjaKpi label="🎯 Opportunities" value={stats.opportunities.toLocaleString()} sub={`${hitRate}% hit rate`} color="green" />
        <NinjaKpi label="📐 Current Spread" value={`$${stats.currentSpread.toFixed(4)}`} sub={`Avg: $${avgSpread}`} color="amber" />
        <NinjaKpi label="🏔️ Max Spread" value={`$${stats.maxSpread.toFixed(4)}`} sub="" color="purple" />
        <NinjaKpi label="💰 Simulated PnL" value={`$${stats.simulatedPnl.toFixed(4)}`}
          sub={`${stats.simulatedTrades} trades`}
          color={stats.simulatedPnl >= 0 ? 'green' : 'red'} />
        <NinjaKpi label="⏱️ Uptime" value={uptime} sub="" color="blue" />
      </div>

      {/* Spread Heatmap Indicator */}
      <div className="glass-card p-3 flex items-center gap-4">
        <span className="text-xs text-muted font-semibold uppercase tracking-wider">Spread Intensity</span>
        <div className="flex-1 h-3 bg-surface-2 rounded-full overflow-hidden relative">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${spreadIntensity * 100}%`,
              background: `linear-gradient(90deg, #64748b, ${heatColor})`,
              boxShadow: spreadIntensity > 0.5 ? `0 0 12px ${heatColor}50` : 'none'
            }}
          />
        </div>
        <span className="text-xs font-mono font-semibold" style={{ color: heatColor }}>
          {(spreadIntensity * 100).toFixed(0)}%
        </span>
        <span className="text-[10px] text-muted font-mono">Range: ${spreadMin} — ${spreadMax}</span>
      </div>

      {/* Main Grid: Chart + Book + Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Spread Chart (full width) */}
        <div className="glass-card lg:col-span-2">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-2/50 rounded-t-2xl">
            <h3 className="text-sm font-semibold text-white">📈 Live Spread Chart</h3>
            <button onClick={() => setChartData([])}
              className="text-[10px] text-muted hover:text-white transition px-2 py-1 rounded border border-border hover:border-accent-2">
              Clear
            </button>
          </div>
          <div className="p-4" style={{ height: 280 }}>
            {chartData.length < 2 ? (
              <div className="flex items-center justify-center h-full text-muted text-sm">
                Waiting for spread data...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorSpread" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
                  <XAxis dataKey="time" stroke="#64748b" fontSize={9} tickLine={false}
                    interval={Math.max(0, Math.floor(chartData.length / 6) - 1)} />
                  <YAxis stroke="#64748b" fontSize={10} tickLine={false}
                    tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                    domain={['dataMin', 'dataMax']} />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number) => [`$${v.toFixed(4)}`, 'Spread']}
                  />
                  <ReferenceLine y={parseFloat(minSpread) || 0.02} stroke="#f59e0b" strokeDasharray="5 5" label={{
                    value: 'MIN SPREAD', position: 'right', fill: '#f59e0b', fontSize: 10
                  }} />
                  <Area type="monotone" dataKey="spread" stroke="#8b5cf6" fill="url(#colorSpread)" strokeWidth={2}
                    dot={(props: any) => {
                      if (props.payload?.isOpp) {
                        return <circle cx={props.cx} cy={props.cy} r={4} fill="#22c55e" stroke="rgba(34,197,94,0.3)" strokeWidth={6} />
                      }
                      return <circle cx={0} cy={0} r={0} fill="none" />
                    }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Order Book */}
        <div className="glass-card">
          <div className="px-5 py-3 border-b border-border bg-surface-2/50 rounded-t-2xl">
            <h3 className="text-sm font-semibold text-white">📖 Order Book (Top 10)</h3>
          </div>
          <div className="grid grid-cols-2">
            {/* Bids */}
            <div>
              <div className="text-[11px] uppercase tracking-wider font-semibold px-3 py-2 text-green-400 bg-green-500/10 border-b border-border">
                BIDS (Buyers)
              </div>
              <div className="divide-y divide-white/[0.03]">
                {bids.length === 0 ? (
                  <div className="p-4 text-center text-muted text-xs">Waiting for data...</div>
                ) : bids.map((b, i) => {
                  const maxSize = Math.max(...bids.map(x => x.size), ...asks.map(x => x.size), 1)
                  const pct = (b.size / maxSize * 100)
                  return (
                    <div key={i} className="relative flex justify-between px-3 py-1.5 text-xs font-mono">
                      <div className="absolute top-0 right-0 bottom-0 bg-green-500/[0.08] rounded-l" style={{ width: `${pct}%` }} />
                      <span className="relative z-10 text-green-400 font-semibold">${b.price.toFixed(4)}</span>
                      <span className="relative z-10 text-muted">{b.size.toFixed(2)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
            {/* Asks */}
            <div className="border-l border-border">
              <div className="text-[11px] uppercase tracking-wider font-semibold px-3 py-2 text-red-400 bg-red-500/10 border-b border-border">
                ASKS (Sellers)
              </div>
              <div className="divide-y divide-white/[0.03]">
                {asks.length === 0 ? (
                  <div className="p-4 text-center text-muted text-xs">Waiting for data...</div>
                ) : asks.map((a, i) => {
                  const maxSize = Math.max(...bids.map(x => x.size), ...asks.map(x => x.size), 1)
                  const pct = (a.size / maxSize * 100)
                  return (
                    <div key={i} className="relative flex justify-between px-3 py-1.5 text-xs font-mono">
                      <div className="absolute top-0 left-0 bottom-0 bg-red-500/[0.08] rounded-r" style={{ width: `${pct}%` }} />
                      <span className="relative z-10 text-red-400 font-semibold">${a.price.toFixed(4)}</span>
                      <span className="relative z-10 text-muted">{a.size.toFixed(2)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Live Feed */}
        <div className="glass-card flex flex-col">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-2/50 rounded-t-2xl">
            <h3 className="text-sm font-semibold text-white">🔴 Live Feed</h3>
            <button onClick={() => setLogs([])}
              className="text-[10px] text-muted hover:text-white transition px-2 py-1 rounded border border-border hover:border-accent-2">
              Clear
            </button>
          </div>
          <div ref={logRef} className="p-3 overflow-y-auto flex-1" style={{ maxHeight: 300 }}>
            <div className="bg-black rounded-lg p-3 font-mono text-[11px] leading-relaxed space-y-0.5 min-h-[100px]">
              {logs.map((entry, i) => (
                <div key={i} className={
                  entry.type === 'opp' ? 'text-green-400' :
                  entry.type === 'warn' ? 'text-amber-400' :
                  entry.type === 'err' ? 'text-red-400' :
                  'text-cyan-400'
                }>
                  <span className="text-muted/50">{entry.time}</span> {entry.msg}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Opportunities Table */}
      <div className="glass-card">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-2/50 rounded-t-2xl">
          <h3 className="text-sm font-semibold text-white">🤑 Arbitrage Opportunities (Spread {'>'} Min)</h3>
          <span className="text-xs text-muted font-mono">{stats.opportunities} detected</span>
        </div>
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Asset</th>
                <th>Best Bid</th>
                <th>Best Ask</th>
                <th>Spread</th>
                <th>Sim. Profit</th>
                <th>Cum. PnL</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted text-sm">
                    No opportunities yet. Connect to a market to start scanning.
                  </td>
                </tr>
              ) : opportunities.map((opp, i) => (
                <tr key={i} className={i === 0 ? 'animate-pulse' : ''}>
                  <td className="text-muted font-mono text-xs">{opp.time}</td>
                  <td className="font-mono text-xs text-accent">{opp.asset}</td>
                  <td className="font-mono text-xs text-green-400">${opp.bestBid.toFixed(4)}</td>
                  <td className="font-mono text-xs text-red-400">${opp.bestAsk.toFixed(4)}</td>
                  <td className="font-mono text-xs text-amber-400 font-semibold">${opp.spread.toFixed(4)}</td>
                  <td className="font-mono text-xs text-green-400 font-semibold">${opp.profit.toFixed(4)}</td>
                  <td className={`font-mono text-xs font-semibold ${opp.cumPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${opp.cumPnl.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* History Table */}
      <div className="glass-card">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-2/50 rounded-t-2xl">
          <h3 className="text-sm font-semibold text-white">📜 Trade History (ninja_trades.jsonl)</h3>
          <button onClick={() => loadHistory()}
            className="text-[10px] text-muted hover:text-white transition px-2 py-1 rounded border border-border hover:border-accent-2">
            Reload
          </button>
        </div>
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Market</th>
                <th>Spread</th>
                <th>Profit</th>
                <th>Cum. PnL</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-muted text-sm">
                    Click &quot;History&quot; to load past trades.
                  </td>
                </tr>
              ) : history.map((entry: any, i: number) => {
                const time = new Date(entry.timestamp).toLocaleString()
                const type = entry.type || '—'
                const market = (entry.market || '').substring(0, 40)
                const spread = entry.spread ? `$${entry.spread.toFixed(4)}` : '—'
                const profit = entry.profit ? `$${entry.profit.toFixed(4)}` : '—'
                const pnl = entry.cumulative_pnl != null ? entry.cumulative_pnl
                  : entry.simulated_pnl != null ? entry.simulated_pnl : null

                return (
                  <tr key={i}>
                    <td className="text-muted font-mono text-xs">{time}</td>
                    <td className={`font-mono text-xs ${
                      type === 'session_summary' ? 'text-cyan-400' :
                      type === 'spread_capture' ? 'text-green-400' : 'text-muted'
                    }`}>{type}</td>
                    <td className="text-xs text-accent font-mono">{market}{market.length >= 40 ? '...' : ''}</td>
                    <td className="font-mono text-xs text-amber-400 font-semibold">{spread}</td>
                    <td className="font-mono text-xs text-green-400 font-semibold">{profit}</td>
                    <td className={`font-mono text-xs font-semibold ${(pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pnl != null ? `$${pnl.toFixed(4)}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ticker Bar */}
      <div className="glass-card flex flex-wrap items-center gap-5 px-5 py-3 text-xs font-mono justify-between">
        <div className="flex gap-5">
          <div className="flex gap-2 items-center">
            <span className="text-muted">Mode:</span>
            <span className={`font-bold ${autoExecute ? 'text-danger animate-pulse' : 'text-amber-400'}`}>
              {autoExecute ? 'LIVE_EXECUTION' : 'DRY_RUN'}
            </span>
          </div>
          <div className="flex gap-2 items-center">
            <span className="text-muted">Status:</span>
            <span className={wsStatus === 'connected' ? 'text-green-400' : 'text-red-400'}>
              {wsStatus.toUpperCase()}
            </span>
          </div>
        </div>
        
        {/* Execution Toggle */}
        <div className="flex items-center gap-3">
          <span className={`text-[11px] font-semibold tracking-wide uppercase ${autoExecute ? 'text-danger' : 'text-muted'}`}>
            {autoExecute ? '⚠️ Auto-Execute Ativado' : 'Simulação de Ganhos'}
          </span>
          <button 
            onClick={() => setAutoExecute(!autoExecute)}
            title={autoExecute ? 'Desativar Auto-Execute' : 'Ativar Auto-Execute'}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background ${autoExecute ? 'bg-danger' : 'bg-surface-2 border border-border'}`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoExecute ? 'translate-x-6' : 'translate-x-1'}`} />
          </button>
        </div>
        <div className="flex gap-2">
          <span className="text-muted">Last Tick:</span>
          <span className="text-white">{chartData.length > 0 ? chartData[chartData.length - 1].time : '—'}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-muted">Spread Range:</span>
          <span className="text-white">${spreadMin} — ${spreadMax}</span>
        </div>
      </div>
    </div>
  )
}

// ======================== COMPONENTS ========================

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { cls: string; label: string }> = {
    connected: { cls: 'badge-success', label: '● Connected' },
    connecting: { cls: 'badge-warning', label: '○ Connecting...' },
    error: { cls: 'badge-danger', label: '● Error' },
    disconnected: { cls: 'badge-muted', label: '● Disconnected' },
  }
  const c = config[status] || config.disconnected
  return <span className={`badge ${c.cls}`}>{c.label}</span>
}

function NinjaKpi({ label, value, sub, color }: {
  label: string; value: string; sub: string; color: string
}) {
  const gradients: Record<string, string> = {
    blue: 'from-blue-500/10 to-indigo-500/5',
    purple: 'from-purple-500/10 to-pink-500/5',
    green: 'from-emerald-500/10 to-teal-500/5',
    amber: 'from-amber-500/10 to-orange-500/5',
    red: 'from-red-500/10 to-rose-500/5',
  }
  return (
    <div className={`glass-card kpi-glow p-4 bg-gradient-to-br ${gradients[color] || gradients.blue}`}>
      <div className="relative z-10">
        <div className="text-[10px] text-muted font-medium uppercase tracking-wide mb-1">{label}</div>
        <div className="text-xl font-bold text-white font-mono">{value}</div>
        {sub && <div className="text-[10px] text-muted mt-0.5 font-mono">{sub}</div>}
      </div>
    </div>
  )
}
