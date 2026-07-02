'use client'

interface HintTooltipProps {
  hint: string
  skill?: string
  danger?: boolean
  className?: string
}

export function HintTooltip({ hint, skill, danger, className = '' }: HintTooltipProps) {
  return (
    <span className={`relative inline-flex items-center group ${className}`}>
      <span
        title={hint}
        className={`inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold cursor-help select-none border ${
          danger
            ? 'border-red-500/40 text-red-400 bg-red-500/10'
            : 'border-border text-muted bg-surface-2 hover:text-accent hover:border-accent/40'
        }`}
        aria-label={hint}
      >
        i
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-[100] mb-2 w-64 -translate-x-1/2 rounded-lg border border-border bg-[#0f172a] px-3 py-2 text-[11px] leading-relaxed text-slate-200 opacity-0 shadow-xl transition-opacity group-hover:opacity-100"
      >
        {skill && (
          <span className="mb-1 block text-[9px] font-semibold uppercase tracking-wide text-accent">
            skill: {skill}
          </span>
        )}
        {hint}
      </span>
    </span>
  )
}

interface HintLabelProps {
  label: string
  hint: string
  skill?: string
  danger?: boolean
}

export function HintLabel({ label, hint, skill, danger }: HintLabelProps) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span>{label}</span>
      <HintTooltip hint={hint} skill={skill} danger={danger} />
    </span>
  )
}
