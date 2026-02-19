'use client'

import { useEffect, useState } from 'react'
import { getTrades } from '@/lib/api'
import { getTradesDirect } from '@/lib/firestore'

export default function TradesPage() {
  const [trades, setTrades] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const data = await getTradesDirect()
        setTrades(data)
      } catch {
        const data = await getTrades()
        setTrades(data)
      }
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12">Loading...</div>
  }

  const totalPnL = trades.reduce((sum, t) => sum + (t.pnl || 0), 0)

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Trades</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Total Trades</div>
          <div className="text-2xl font-bold">{trades.length}</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Open Positions</div>
          <div className="text-2xl font-bold">{trades.filter(t => t.status === 'open').length}</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg">
          <div className="text-sm text-gray-400">Total PnL</div>
          <div className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${totalPnL.toFixed(2)}
          </div>
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Trade History</h2>
        {trades.length > 0 ? (
          <div className="space-y-4">
            {trades.map((t: any, i: number) => (
              <div key={i} className="border-b border-gray-700 pb-4">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-medium">Market: {t.market_id.slice(0, 16)}...</div>
                    <div className="text-sm text-gray-400 mt-1">
                      Side: {t.side} | Size: ${t.size} | Entry: ${t.entry_price.toFixed(4)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`font-bold ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ${t.pnl.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-400">{t.status}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400">No trades found</p>
        )}
      </div>
    </div>
  )
}
