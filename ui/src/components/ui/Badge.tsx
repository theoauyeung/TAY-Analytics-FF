import clsx from 'clsx'
import type { Position } from '../../types'

type PositionBadgeProps = { position: Position }
type SignalBadgeProps = { signal: 'value' | 'avoid' | 'breakout' | 'injury' | 'confidence'; label: string }

const POS_STYLES: Record<Position, string> = {
  QB:  'bg-pos-qb/20 text-pos-qb',
  RB:  'bg-pos-rb/20 text-pos-rb',
  WR:  'bg-pos-wr/20 text-pos-wr',
  TE:  'bg-pos-te/20 text-pos-te',
  K:   'bg-pos-k/20 text-pos-k',
  DST: 'bg-pos-dst/20 text-pos-dst',
}

const SIGNAL_STYLES: Record<SignalBadgeProps['signal'], string> = {
  value:      'bg-accent-muted text-accent border border-accent/30',
  avoid:      'bg-red-900/30 text-red-400 border border-red-400/30',
  breakout:   'bg-green-900/30 text-green-400 border border-green-400/30',
  injury:     'bg-yellow-900/30 text-yellow-400 border border-yellow-400/30',
  confidence: 'bg-purple-900/30 text-purple-400 border border-purple-400/30',
}

export function PositionBadge({ position }: PositionBadgeProps) {
  return (
    <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold', POS_STYLES[position])}>
      {position}
    </span>
  )
}

export function SignalBadge({ signal, label }: SignalBadgeProps) {
  return (
    <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium', SIGNAL_STYLES[signal])}>
      {label}
    </span>
  )
}
