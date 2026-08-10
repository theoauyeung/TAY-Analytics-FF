import clsx from 'clsx'
import type { PlayerDetail } from '../../types'

interface Config { QB: number; RB: number; WR: number; TE: number }
interface Props { roster: PlayerDetail[]; rosterConfig: Config }

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

function strengthLabel(count: number, needed: number): { label: string; color: string } {
  if (count >= needed + 2) return { label: 'Elite',   color: 'text-green-400' }
  if (count >= needed + 1) return { label: 'Strong',  color: 'text-accent' }
  if (count >= needed)     return { label: 'Average', color: 'text-text-secondary' }
  return { label: 'Weak', color: 'text-yellow-400' }
}

export function PositionStrengthBars({ roster, rosterConfig }: Props) {
  return (
    <div className="space-y-3">
      {POSITIONS.map(pos => {
        const count  = roster.filter(p => p.position === pos).length
        const needed = rosterConfig[pos]
        const { label, color } = strengthLabel(count, needed)
        const pct = needed > 0 ? Math.min(100, Math.round((count / (needed + 2)) * 100)) : 0
        return (
          <div key={pos}>
            <div className="flex justify-between mb-1">
              <span className="text-xs text-text-secondary">{pos}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">{count}/{needed} starters</span>
                <span className={clsx('text-xs font-medium', color)}>{label}</span>
              </div>
            </div>
            <div className="h-1.5 bg-bg-elevated rounded-full">
              <div
                className="h-1.5 rounded-full bg-accent transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
