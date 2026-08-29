import clsx from 'clsx'
import type { RankingFilters, Position } from '../../types'

interface Props {
  filters: RankingFilters
  onChange: (f: Partial<RankingFilters>) => void
}

const POSITIONS: Array<Position | 'ALL'> = ['ALL', 'QB', 'RB', 'WR', 'TE']
const FORMATS = [
  { value: 'ppr', label: 'PPR' },
] as const
const DRAFT_TYPES = [
  { value: 'redraft', label: 'Redraft' },
] as const

function TabGroup<T extends string>({
  options, value, onChange,
}: { options: ReadonlyArray<{ readonly value: T; readonly label: string }>; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex gap-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            'px-2.5 py-1 text-xs transition-colors border-b',
            value === o.value
              ? 'text-text-primary font-semibold border-accent'
              : 'text-text-muted hover:text-text-secondary border-transparent'
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
    <div className="flex flex-wrap items-center gap-5">
      <TabGroup options={DRAFT_TYPES} value={filters.draftType} onChange={(v) => onChange({ draftType: v })} />
      <TabGroup options={FORMATS} value={filters.format} onChange={(v) => onChange({ format: v })} />

      {/* Position tabs */}
      <div className="flex gap-0.5">
        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => onChange({ position: pos })}
            className={clsx(
              'px-2.5 py-1 text-xs transition-colors border-b',
              filters.position === pos
                ? 'text-text-primary font-semibold border-accent'
                : 'text-text-muted hover:text-text-secondary border-transparent'
            )}
          >
            {pos}
          </button>
        ))}
      </div>

      <input
        type="text"
        placeholder="Search players…"
        value={filters.search}
        onChange={(e) => onChange({ search: e.target.value })}
        className="bg-transparent border-b border-border px-1 py-1 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent w-40"
      />
    </div>
  )
}
