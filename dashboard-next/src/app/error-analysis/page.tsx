'use client'

import { useEffect, useState } from 'react'

export default function ErrorAnalysisPage() {
  const [analysis, setAnalysis] = useState<any>(null)
  const [corrections, setCorrections] = useState<any[]>([])
  const [improvements, setImprovements] = useState<any[]>([])

  const fetchAll = () => {
    fetch('/api/error-analysis').then(r => r.json()).then(setAnalysis).catch(() => {})
    fetch('/api/corrections').then(r => r.json()).then(d => setCorrections(d.corrections || [])).catch(() => {})
    fetch('/api/improvements').then(r => r.json()).then(d => setImprovements(d.improvements || [])).catch(() => {})
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleAction = async (id: string, action: string) => {
    await fetch('/api/corrections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, action }),
    })
    fetchAll()
  }

  const errors = analysis?.analysis || []
  const topError = errors[0]
  const pendingCorrections = corrections.filter(c => c.status === 'pending')
  const appliedCorrections = corrections.filter(c => c.status === 'applied' || c.status === 'verified')

  return (
    <div className="space-y-5 max-w-[1400px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">🔍 Análise de Erros & Auto-Correção</h1>
          <p className="text-sm text-muted mt-1">Dashboard de mitigação ativa de erros comandado pelo OpenClaw</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="badge badge-success">● AutoCorrect Agent Live</span>
          <button onClick={fetchAll} className="px-3 py-1.5 rounded-lg bg-surface-2 text-white text-xs hover:bg-border transition border border-border">
            Atualizar
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard label="Total de Erros" value={analysis?.totalErrors || '0'} icon="⚠️" color="amber" />
        <KpiCard label="Maior Ofensor" value={topError?.type || 'Nenhum'} sub={`${topError?.count || 0} ocorrências`} icon="🔥" color="red" />
        <KpiCard label="Fixes Pendentes" value={pendingCorrections.length.toString()} icon="🛠️" color="blue" />
        <KpiCard label="Melhorias Aplicadas" value={appliedCorrections.length.toString()} icon="✅" color="green" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Error Table & Improvements */}
        <div className="lg:col-span-2 space-y-4">
          
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Prioridades de Correção</h3>
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead>
                  <tr>
                    <th>Tipo de Erro</th>
                    <th>Ocorrências</th>
                    <th>Impacto</th>
                    <th>Severidade</th>
                    <th>Correção Recomendada</th>
                  </tr>
                </thead>
                <tbody>
                  {errors.length === 0 && <tr><td colSpan={5} className="text-center py-4 text-muted border-none">Nenhum erro detectado</td></tr>}
                  {errors.map((err: any, i: number) => (
                    <tr key={i}>
                      <td className="font-semibold text-white">{err.type}</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="font-mono">{err.count}</span>
                          {err.trend > 0 && <span className="text-[10px] text-red-400">↑ {err.trend} nas ult. 24h</span>}
                        </div>
                      </td>
                      <td className="text-xs text-muted">{err.impact}</td>
                      <td>
                        <span className={`badge ${err.severity === 'Critical' ? 'badge-danger' : err.severity === 'High' ? 'badge-warning' : 'badge-info'}`}>
                          {err.severity}
                        </span>
                      </td>
                      <td className="text-[11px] text-accent truncate max-w-[200px]" title={err.recommendedFix}>
                        {err.recommendedFix}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Histórico de Efetividade (Melhorias)</h3>
            <div className="space-y-3">
              {improvements.length === 0 && <div className="text-center text-muted py-4 text-sm">Nenhuma melhoria verificada ainda.</div>}
              {improvements.map((imp: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface-2/30">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{imp.errorType}</span>
                      <span className="badge badge-success">Verificado</span>
                    </div>
                    <div className="text-[10px] text-muted mt-1 font-mono">
                      erros antes: {imp.errorsBefore} → depois: {imp.errorsAfter} ({imp.period})
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-bold text-green-400">{imp.effectivenessScore}%</div>
                    <div className="text-[10px] text-muted uppercase">Efetividade</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Right: AutoCorrect Actions */}
        <div className="space-y-4">
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              🤖 AutoCorrect Agent
              {pendingCorrections.length > 0 && <span className="badge badge-warning">{pendingCorrections.length} Pendentes</span>}
            </h3>
            
            <div className="space-y-3 mt-4">
              {pendingCorrections.length === 0 && (
                <div className="text-center text-muted py-6 text-sm">
                  O agente não encontrou novas correções para propor no momento.
                </div>
              )}
              
              {pendingCorrections.map((corr: any) => (
                <div key={corr.id} className="p-3 rounded-lg border border-warning/30 bg-warning/5">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-white">{corr.errorType}</span>
                    <span className="badge badge-danger">{corr.severity}</span>
                  </div>
                  <p className="text-[11px] text-muted mb-2">{corr.description}</p>
                  <div className="text-[11px] font-mono text-accent bg-accent/10 p-2 rounded mb-3 border border-accent/20">
                    Fix: {corr.fix}
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => handleAction(corr.id, 'approve')} className="flex-1 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-xs font-semibold hover:bg-green-500/30 transition border border-green-500/30">
                      ✓ Aprovar e Executar
                    </button>
                    <button onClick={() => handleAction(corr.id, 'reject')} className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs font-semibold hover:bg-red-500/30 transition border border-red-500/30">
                      ✗
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          <div className="glass-card p-4">
            <h3 className="text-xs font-semibold text-white mb-2 uppercase tracking-wide">Status do Agente</h3>
            <ul className="space-y-2">
              <li className="text-[11px] text-muted flex items-start gap-2">
                <span className="text-green-400">●</span> <b>Monitoramento:</b> Ativo (logs/executions.jsonl)
              </li>
              <li className="text-[11px] text-muted flex items-start gap-2">
                <span className="text-green-400">●</span> <b>Análise:</b> Padrões detectados
              </li>
              <li className="text-[11px] text-muted flex items-start gap-2">
                <span className="text-blue-400">●</span> <b>Deploy:</b> Aguardando aprovação humana para tuning
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function KpiCard({ label, value, sub, icon, color }: any) {
  const gradients: any = {
    blue: 'from-blue-500/10 to-indigo-500/5',
    green: 'from-emerald-500/10 to-teal-500/5',
    amber: 'from-amber-500/10 to-orange-500/5',
    red: 'from-red-500/10 to-rose-500/5',
  }
  return (
    <div className={`glass-card p-4 bg-gradient-to-br ${gradients[color] || gradients.blue}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-muted font-medium uppercase tracking-wide">{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className="text-xl font-bold text-white font-mono">{value}</div>
      {sub && <div className="text-[10px] text-muted mt-0.5">{sub}</div>}
    </div>
  )
}
