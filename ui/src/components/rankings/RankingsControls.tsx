import clsx from 'clsx'
import type { RankingFilters, Position } from '../../types'

interface Props {
  filters: RankingFilters
  onChange: (f: Partial<RankingFilters>) => void
}

const POSITIONS: Array<Position | 'ALL'> = ['ALL', 'QB', 'RB', 'WR', 'TE']
const FORMATS = [
  { value: 'ppr',      label: 'PPR' },
  { value: 'half_ppr', label: 'Half PPR' },
  { value: 'standard', label: 'Standard' },
] as const
const DRAFT_TYPES = [
  { value: 'redraft',   label: 'Redraft' },
  { value: 'best_ball', label: 'Best Ball' },
  { value: 'dynasty',   label: 'Dynasty' },
] as const

function SegmentedControl<T extends string>({
  options, value, onChange,
}: { options: Array<{ value: T; label: string }>; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            'px-3 py-1.5 text-xs font-medium transition-colors',
            value === o.value
              ? 'bg-accent text-bg-primary'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function RankingsControls({ filters, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <SegmentedControl options={DRAFT_TYPES} value={filters.draftType} onChange={(v) => onChange({ draftType: v })} />
      <SegmentedControl options={FORMATS} value={filters.format} onChange={(v) => onChange({ format: v })} />

      {/* Position tabs */}
      <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary">
        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => onChange({ position: pos })}
            className={clsx(
              'px-3 py-1.5 text-xs font-medium transition-colors',
              filters.position === pos
                ? 'bg-accent text-bg-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            )}
          >
            {pos}
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Search players…"
        value={filters.search}
        onChange={(e) => onChange({ search: e.target.value })}
        className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent w-48"
      />

      {/* Year */}
      <span className="text-xs text-text-secondary">
        2026 Projections
      </span>
    </div>
  )
}
