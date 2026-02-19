'use client'

export default function KeysPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Keys Manager</h1>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">API Keys</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">OpenRouter API Key</label>
            <input
              type="password"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
              placeholder="sk-or-v1-..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Chainstack Node URL</label>
            <input
              type="text"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
              placeholder="https://polygon-mainnet.core.chainstack.com/..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Polyclaw Agent API Key</label>
            <input
              type="password"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
              placeholder="pc_agent_..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Telegram Bot Token</label>
            <input
              type="password"
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
              placeholder="123456789:ABCdef..."
            />
          </div>
        </div>
        <button className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
          Save Keys
        </button>
      </div>
    </div>
  )
}
