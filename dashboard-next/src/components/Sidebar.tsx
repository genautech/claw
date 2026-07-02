'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useDashboardData } from '@/hooks/useDashboardData'

const navItems = [
  { href: '/', label: 'Dashboard', icon: '📊' },
  { href: '/bots', label: 'Análise de Bots', icon: '🤖' },
  { href: '/trades', label: 'Trades & Charts', icon: '📈' },
  { href: '/arbitrage-ninja', label: 'ArbitrageNinja', icon: '🥷' },
  { href: '/analysis', label: 'Análise & Tendências', icon: '🔬' },
  { href: '/error-analysis', label: 'Análise de Erros', icon: '🔍' },
  { href: '/costs', label: 'Custos & Fees', icon: '💰' },
  { href: '/strategy', label: 'Estratégia', icon: '🎯' },
  { href: '/risk', label: 'Brimo (Risk)', icon: '🐻' },
  { href: '/settings', label: 'Configurações', icon: '⚙️' },
]

const externalLinks: { href: string; label: string; icon: string }[] = [
  { href: 'http://localhost:3001', label: 'Mission Control', icon: '🎛️' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { data: health } = useDashboardData<Record<string, unknown>>('/api/data?type=health', {
    intervalMs: 30000,
    staleTimeMs: 15000,
  })
  const { data: config } = useDashboardData<Record<string, unknown>>('/api/config', {
    intervalMs: 30000,
    staleTimeMs: 15000,
  })

  const executorOnline = health && !health.offline

  return (
    <aside className="fixed left-0 top-0 h-screen w-[240px] bg-surface border-r border-border flex flex-col z-50">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center text-lg">
            🦞
          </div>
          <div>
            <h1 className="text-sm font-bold text-white">PolyClaw</h1>
            <p className="text-[10px] text-muted font-mono">Trading Dashboard</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="text-[9px] text-muted uppercase tracking-wider font-semibold px-3 mb-2">Dashboard</div>
        {navItems.map((item) => (
          <Link key={item.href} href={item.href}
            className={`nav-link ${pathname === item.href ? 'active' : ''}`}>
            <span className="text-base">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}

        <div className="text-[9px] text-muted uppercase tracking-wider font-semibold px-3 mt-4 mb-2">Ferramentas</div>
        {externalLinks.map((item) => (
          <a key={item.href} href={item.href} target="_blank" rel="noopener noreferrer"
            className="nav-link">
            <span className="text-base">{item.icon}</span>
            <span>{item.label}</span>
            <span className="ml-auto text-[9px] text-muted">↗</span>
          </a>
        ))}
      </nav>

      <div className="p-4 border-t border-border space-y-2">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${executorOnline ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs text-muted">
            {executorOnline ? 'Executor Online' : 'Executor Offline'}
          </span>
        </div>
        {config && (
          <div className="text-[10px] text-muted font-mono">
            {config.dryRun ? '🧪 Simulação' : '🔴 Live'} · min ${String(config.minTrade ?? '?')}
          </div>
        )}
      </div>
    </aside>
  )
}
