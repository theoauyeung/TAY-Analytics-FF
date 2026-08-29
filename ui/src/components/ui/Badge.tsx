import clsx from 'clsx'
import type { Position } from '../../types'

type PositionBadgeProps = { position: Position }
type SignalBadgeProps = { signal: 'value' | 'avoid' | 'breakout' | 'injury' | 'confidence'; label: string }

const POS_COLORS: Record<Position, string> = {
  QB:  'text-pos-qb',
  RB:  'text-pos-rb',
  WR:  'text-pos-wr',
  TE:  'text-pos-te',
  K:   'text-pos-k',
  DST: 'text-pos-dst',
}

const SIGNAL_COLORS: Record<SignalBadgeProps['signal'], string> = {
  value:      'text-accent',
  avoid:      'text-red-400',
  breakout:   'text-green-400',
  injury:     'text-yellow-400',
  confidence: 'text-purple-400',
}

export function PositionBadge({ position }: PositionBadgeProps) {
  return (
    <span className={clsx('text-xs font-bold font-condensed tracking-wide', POS_COLORS[position])}>
      {position}
    </span>
  )
}

export function SignalBadge({ signal, label }: SignalBadgeProps) {
  return (
    <span className={clsx('text-xs font-medium', SIGNAL_COLORS[signal])}>
      {label}
    </span>
  )
}
