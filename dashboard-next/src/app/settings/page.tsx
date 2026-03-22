'use client'

import { useEffect, useState } from 'react'

interface Config {
  goal: number
  goalDays: number
  minTrade: number
  maxTrade: number
  maxDaily: number
  dryRun: boolean
  minConfidence: string
  minEdge: number
  autoExecute: boolean
  capitalInitial: number
}

export default function SettingsPage() {
  const [config, setConfig] = useState<Config | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(setConfig)
  }, [])

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const update = (key: keyof Config, value: any) => {
    if (!config) return
    setConfig({ ...config, [key]: value })
  }

  if (!config) return <div className="text-muted p-8">Carregando configurações...</div>

  return (
    <div className="space-y-6 max-w-[900px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">⚙️ Configurações</h1>
          <p className="text-sm text-muted mt-1">Configure metas, limites e automação dos agentes</p>
        </div>
        <button onClick={handleSave} disabled={saving}
          className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            saved ? 'bg-green-500/20 text-green-400 border border-green-500/30'
            : 'bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30'
          }`}>
          {saving ? '💾 Salvando...' : saved ? '✓ Salvo!' : '💾 Salvar Configurações'}
        </button>
      </div>

      {/* Meta Financeira */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🎯 Meta Financeira</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <InputField label="Meta ($)" type="number" value={config.goal}
            onChange={v => update('goal', parseFloat(v))} hint="Objetivo de capital" />
          <InputField label="Prazo (dias)" type="number" value={config.goalDays}
            onChange={v => update('goalDays', parseInt(v))} hint="Dias para atingir a meta" />
          <InputField label="Capital Inicial ($)" type="number" value={config.capitalInitial}
            onChange={v => update('capitalInitial', parseFloat(v))} hint="Quanto você começou" />
        </div>
        <div className="mt-3 p-3 rounded-lg bg-accent/5 border border-accent/20">
          <div className="text-xs text-muted">
            Crescimento necessário: <span className="text-white font-semibold">{(config.goal / config.capitalInitial).toFixed(1)}x</span>
            {' • '}
            Daily target: <span className="text-white font-semibold">${((config.goal - config.capitalInitial) / config.goalDays).toFixed(2)}/dia</span>
          </div>
        </div>
      </div>

      {/* Limites de Investimento */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">💰 Limites de Investimento</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <InputField label="Mínimo por Trade ($)" type="number" value={config.minTrade}
            onChange={v => update('minTrade', parseFloat(v))} hint="Valor mínimo por operação" step="0.1" />
          <InputField label="Máximo por Trade ($)" type="number" value={config.maxTrade}
            onChange={v => update('maxTrade', parseFloat(v))} hint="Valor máximo por operação" step="0.5" />
          <InputField label="Máximo Diário ($)" type="number" value={config.maxDaily}
            onChange={v => update('maxDaily', parseFloat(v))} hint="Limite diário total" />
        </div>
      </div>

      {/* Modo de Execução */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">⚡ Modo de Execução</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ToggleField label="Dry Run Mode" description="Simular trades sem gastar USDC"
            value={config.dryRun} onChange={v => update('dryRun', v)} />
          <ToggleField label="Auto Execute" description="Executar recomendações automaticamente"
            value={config.autoExecute} onChange={v => update('autoExecute', v)}
            dangerWhenOn />
        </div>
        {config.autoExecute && (
          <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
            <div className="text-xs text-red-400 font-semibold">⚠️ Auto-execute está ATIVO</div>
            <div className="text-[11px] text-muted mt-1">
              Recomendações com confiança ≥ {config.minConfidence} e edge ≥ {config.minEdge}% serão executadas automaticamente.
            </div>
          </div>
        )}
      </div>

      {/* Filtros de Recomendação */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🔍 Filtros de Recomendação</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SelectField label="Confiança Mínima" value={config.minConfidence}
            options={['LOW', 'MEDIUM', 'HIGH']}
            onChange={v => update('minConfidence', v)}
            hint="Só executar recomendações com confiança ≥ este nível" />
          <InputField label="Edge Mínimo (%)" type="number" value={config.minEdge}
            onChange={v => update('minEdge', parseFloat(v))} hint="Edge mínimo para execução" step="1" />
        </div>
      </div>

      {/* Current Config JSON (debug) */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-3">📋 Config Atual (JSON)</h3>
        <pre className="text-[11px] font-mono text-muted bg-bg rounded-lg p-3 overflow-x-auto">
          {JSON.stringify(config, null, 2)}
        </pre>
      </div>
    </div>
  )
}

function InputField({ label, type, value, onChange, hint, step }: {
  label: string; type: string; value: any; onChange: (v: string) => void; hint?: string; step?: string
}) {
  return (
    <div>
      <label className="text-xs text-muted font-medium block mb-1.5">{label}</label>
      <input type={type} value={value} step={step}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-white font-mono
          focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition" />
      {hint && <div className="text-[10px] text-muted mt-1">{hint}</div>}
    </div>
  )
}

function SelectField({ label, value, options, onChange, hint }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void; hint?: string
}) {
  return (
    <div>
      <label className="text-xs text-muted font-medium block mb-1.5">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-white
          focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition">
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      {hint && <div className="text-[10px] text-muted mt-1">{hint}</div>}
    </div>
  )
}

function ToggleField({ label, description, value, onChange, dangerWhenOn }: {
  label: string; description: string; value: boolean; onChange: (v: boolean) => void; dangerWhenOn?: boolean
}) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-bg border border-border">
      <div>
        <div className="text-sm text-white font-medium">{label}</div>
        <div className="text-[11px] text-muted">{description}</div>
      </div>
      <button onClick={() => onChange(!value)}
        className={`w-12 h-6 rounded-full transition-all flex items-center ${
          value
            ? dangerWhenOn ? 'bg-red-500' : 'bg-accent'
            : 'bg-surface-3'
        }`}>
        <div className={`w-5 h-5 rounded-full bg-white shadow-md transition-transform ${
          value ? 'translate-x-6' : 'translate-x-0.5'
        }`} />
      </button>
    </div>
  )
}
