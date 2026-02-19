'use client'

import { useEffect, useState } from 'react'
import { getConfig, updateConfig } from '@/lib/api'

export default function ConfigPage() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    async function load() {
      const data = await getConfig()
      setConfig(data)
      setLoading(false)
    }
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateConfig(config)
      alert('Config updated!')
    } catch (error) {
      alert('Error updating config')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Config Editor</h1>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Gateway Settings</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Mode</label>
            <select
              value={config?.gateway?.mode || 'local'}
              onChange={(e) => setConfig({ ...config, gateway: { ...config?.gateway, mode: e.target.value } })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            >
              <option value="local">Local</option>
              <option value="cloud">Cloud</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Port</label>
            <input
              type="number"
              value={config?.gateway?.port || 18789}
              onChange={(e) => setConfig({ ...config, gateway: { ...config?.gateway, port: parseInt(e.target.value) } })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            />
          </div>
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Telegram Channel</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Bot Token</label>
            <input
              type="password"
              value={config?.channels?.telegram?.botToken || ''}
              onChange={(e) => setConfig({
                ...config,
                channels: {
                  ...config?.channels,
                  telegram: { ...config?.channels?.telegram, botToken: e.target.value }
                }
              })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
              placeholder="123456789:ABCdef..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Channel</label>
            <input
              type="text"
              value="/openslaver"
              disabled
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 opacity-50"
            />
          </div>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
      >
        {saving ? 'Saving...' : 'Save Config'}
      </button>
    </div>
  )
}
