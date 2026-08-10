import clsx from 'clsx'

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'] as const

interface Props {
  search: string
  position: string
  onSearchChange: (s: string) => void
  onPositionChange: (p: string) => void
}

export function PlayerSearch({ search, position, onSearchChange, onPositionChange }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <input
        type="text"
        placeholder="Search players…"
        value={search}
        onChange={e => onSearchChange(e.target.value)}
        className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
      />
      <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary">
        {POSITIONS.map(pos => (
          <button
            key={pos}
            onClick={() => onPositionChange(pos)}
            className={clsx(
              'flex-1 py-1.5 text-xs font-medium transition-colors',
              position === pos
                ? 'bg-accent text-bg-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            )}
          >
            {pos}
          </button>
        ))}
      </div>
    </div>
  )
}
