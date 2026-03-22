'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'

const navItems = [
  { href: '/', label: 'Dashboard', icon: '📊' },
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
]

export function Sidebar() {
  const pathname = usePathname()
  const [health, setHealth] = useState<any>(null)
  const [config, setConfig] = useState<any>(null)

  useEffect(() => {
    const fetchStatus = () => {
      fetch('/api/data?type=health').then(r => r.json()).then(setHealth).catch(() => {})
      fetch('/api/config').then(r => r.json()).then(setConfig).catch(() => {})
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 15000)
    return () => clearInterval(interval)
  }, [])

  const executorOnline = health && !health.offline

  return (
    <aside className="fixed left-0 top-0 h-screen w-[240px] bg-surface border-r border-border flex flex-col z-50">
      {/* Logo */}
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

      {/* Nav */}
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

      {/* Status footer */}
      <div className="p-4 border-t border-border space-y-2">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${executorOnline ? 'bg-success animate-pulse-slow' : 'bg-danger'}`} />
          <span className="text-xs text-muted">{executorOnline ? 'Executor Online' : 'Executor Offline'}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${health?.dry_run ? 'bg-warning' : 'bg-success'}`} />
          <span className="text-xs text-muted">{health?.dry_run ? 'Dry Run' : 'Live Mode'}</span>
        </div>
        {config && (
          <div className="text-[10px] text-muted font-mono pt-1 border-t border-border/50">
            Meta: ${config.goal?.toLocaleString()} / {config.goalDays}d
          </div>
        )}
      </div>
    </aside>
  )
}
