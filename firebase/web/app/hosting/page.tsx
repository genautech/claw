'use client'

export default function HostingPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Hosting Advisor</h1>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Recommended Regions</h2>
        <div className="space-y-4">
          <div className="border-l-4 border-green-500 pl-4">
            <div className="font-medium">us-east1 (Recommended)</div>
            <div className="text-sm text-gray-400">Latency: ~45ms to Polymarket | Cost: Standard</div>
          </div>
          <div className="border-l-4 border-yellow-500 pl-4">
            <div className="font-medium">us-west1</div>
            <div className="text-sm text-gray-400">Latency: ~120ms | Cost: 5% lower</div>
          </div>
          <div className="border-l-4 border-red-500 pl-4">
            <div className="font-medium">europe-west1</div>
            <div className="text-sm text-gray-400">Latency: ~180ms | Not recommended</div>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Current Setup</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm text-gray-400">Cloud Run Region</div>
            <div className="font-medium">us-east1 ✅</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Firestore Region</div>
            <div className="font-medium">us-east1 ✅</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Hosting CDN</div>
            <div className="font-medium">Global (us-east1 primary) ✅</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Cache Layer</div>
            <div className="font-medium">Firestore TTL ✅</div>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Optimization Tips</h2>
        <ul className="space-y-2 list-disc list-inside text-gray-300">
          <li>Use async RPC calls for Polygon network</li>
          <li>Implement connection pooling for Chainstack</li>
          <li>Cache LLM responses with 5min TTL</li>
          <li>Pre-validate orders before CLOB submission</li>
          <li>Monitor latency metrics in real-time</li>
        </ul>
      </div>
    </div>
  )
}
