import { useState, useMemo } from 'react'
import { MOCK_RANKINGS } from '../../data'
import { PositionBadge } from '../ui/Badge'
import type { PlayerDetail } from '../../types'
import { X } from 'lucide-react'

interface Props {
  roster: PlayerDetail[]
  onAdd: (p: PlayerDetail) => void
  onRemove: (id: string) => void
}

export function RosterBuilder({ roster, onAdd, onRemove }: Props) {
  const [search, setSearch] = useState('')
  const rosterIds = new Set(roster.map(p => p.id))

  const suggestions = useMemo(() => {
    if (!search.trim()) return []
    const q = search.toLowerCase()
    return MOCK_RANKINGS
      .filter(r => !rosterIds.has(r.player.id) &&
        (r.player.name.toLowerCase().includes(q) || r.player.team.toLowerCase().includes(q))
      )
      .slice(0, 8)
  }, [search, rosterIds])

  return (
    <div className="flex flex-col gap-3">
      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Add player…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
        />
        {suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 z-20 bg-bg-elevated border border-border rounded-lg mt-1 shadow-xl overflow-hidden">
            {suggestions.map(r => (
              <button
                key={r.player.id}
                onClick={() => { onAdd(r.player); setSearch('') }}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-bg-card transition-colors"
              >
                <PositionBadge position={r.player.position} />
                <span className="text-sm text-text-primary flex-1 text-left">{r.player.name}</span>
                <span className="text-xs text-text-muted">{r.player.team}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Roster list */}
      <div className="space-y-1">
        {roster.length === 0 && (
          <p className="text-sm text-text-muted text-center py-4">Add players above</p>
        )}
        {roster.map(p => (
          <div key={p.id} className="flex items-center gap-2 bg-bg-card border border-border rounded-lg px-3 py-2">
            <PositionBadge position={p.position} />
            <span className="text-sm text-text-primary flex-1 truncate">{p.name}</span>
            <span className="text-xs text-text-muted">{p.team}</span>
            <button onClick={() => onRemove(p.id)} className="text-text-muted hover:text-text-primary ml-1">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
