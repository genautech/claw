'use client'

import { useEffect, useState } from 'react'
import { getPredictions } from '@/lib/api'
import { getPredictionsDirect } from '@/lib/firestore'

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const data = await getPredictionsDirect()
        setPredictions(data)
      } catch {
        // fallback to API
        const data = await getPredictions()
        setPredictions(data)
      }
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Predictions</h1>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Historical Predictions</h2>
        {predictions.length > 0 ? (
          <div className="space-y-4">
            {predictions.map((p: any, i: number) => (
              <div key={i} className="border-b border-gray-700 pb-4">
                <div className="font-medium">{p.market_question}</div>
                <div className="text-sm text-gray-400 mt-1">
                  Edge: {(p.edge * 100).toFixed(1)}% | Confidence: {p.confidence} | Decision: {p.decision}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {p.timestamp ? new Date(p.timestamp?.seconds ? p.timestamp.seconds * 1000 : p.timestamp).toLocaleString() : 'No timestamp'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400">No predictions found</p>
        )}
      </div>
    </div>
  )
}
