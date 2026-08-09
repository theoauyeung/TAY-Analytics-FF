import { useState } from 'react'
import clsx from 'clsx'

interface StatCellProps {
  value: string | number | null
  label?: string
  detail?: React.ReactNode
  className?: string
  positive?: boolean   // green tint
  negative?: boolean   // red tint
}

export function StatCell({ value, label, detail, className, positive, negative }: StatCellProps) {
  const [open, setOpen] = useState(false)

  if (value === null) return <span className="text-text-muted">—</span>

  return (
    <span className="relative inline-block">
      <button
        onClick={() => detail && setOpen((v) => !v)}
        className={clsx(
          'tabular-nums text-sm transition-colors',
          detail && 'underline decoration-dotted underline-offset-2 cursor-pointer',
          positive && 'text-green-400',
          negative && 'text-red-400',
          !positive && !negative && 'text-text-primary',
          className
        )}
      >
        {value}
        {label && <span className="text-text-muted text-xs ml-0.5">{label}</span>}
      </button>
      {open && detail && (
        <div className="absolute z-50 top-6 left-0 w-56 bg-bg-elevated border border-border rounded-lg p-3 shadow-xl text-xs text-text-secondary">
          {detail}
          <button onClick={() => setOpen(false)} className="mt-2 text-text-muted hover:text-text-primary">✕ close</button>
        </div>
      )}
    </span>
  )
}
