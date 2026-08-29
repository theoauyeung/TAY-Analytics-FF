import { useState, useMemo, useEffect } from 'react'
import type { Ranking } from '../types'
import { useRankings } from '../hooks/useRankings'
import { PlayerSearch, PlayerListRow, ProjectionChart, ComparablePlayers } from '../components/players'
import { PositionBadge } from '../components/ui/Badge'

export default function Players() {
  const [search, setSearch] = useState('')
  const [position, setPosition] = useState('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { rankings, isLoading, error, refetch } = useRankings({
    position: position as 'ALL' | 'QB' | 'RB' | 'WR' | 'TE',
    search,
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })

  useEffect(() => {
    if (rankings.length > 0 && selectedId === null) {
      setSelectedId(rankings[0].player.id)
    }
  }, [rankings, selectedId])

  const selectedRanking: Ranking | undefined = useMemo(
    () => rankings.find(r => r.player.id === selectedId),
    [rankings, selectedId]
  )

  if (error) {
    return (
      <div className="flex h-full items-center justify-center flex-col gap-3 text-text-secondary">
        <p>Failed to load players</p>
        <button onClick={() => refetch()} className="text-sm text-accent underline">Retry</button>
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: search + list */}
      <div className="w-72 flex-shrink-0 flex flex-col border-r border-border bg-bg-secondary overflow-hidden">
        <div className="p-3 border-b border-border">
          <PlayerSearch
            search={search}
            position={position}
            onSearchChange={setSearch}
            onPositionChange={setPosition}
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <p className="text-sm text-text-muted p-4 text-center">Loading…</p>
          )}
          {rankings.map(r => (
            <PlayerListRow
              key={r.player.id}
              ranking={r}
              selected={r.player.id === selectedId}
              onClick={() => setSelectedId(r.player.id)}
            />
          ))}
          {!isLoading && rankings.length === 0 && (
            <p className="text-sm text-text-muted p-4 text-center">No players found</p>
          )}
        </div>
      </div>

      {/* Right: player detail */}
      {selectedRanking ? (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-start gap-4">
            {selectedRanking.player.imageUrl && (
              <img
                src={selectedRanking.player.imageUrl}
                alt=""
                className="w-16 h-16 rounded-full object-cover bg-bg-elevated flex-shrink-0"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            )}
            <div>
              <h1 className="text-2xl font-bold text-text-primary">{selectedRanking.player.name}</h1>
              <div className="flex items-center gap-2 mt-1">
                <PositionBadge position={selectedRanking.player.position} />
                <span className="text-sm text-text-secondary">{selectedRanking.player.team}</span>
                {selectedRanking.player.byeWeek > 0 && (
                  <span className="text-sm text-text-muted">· Bye {selectedRanking.player.byeWeek}</span>
                )}
                {selectedRanking.player.age > 0 && (
                  <span className="text-sm text-text-muted">· Age {selectedRanking.player.age}</span>
                )}
              </div>
            </div>
            <div className="ml-auto text-right">
              <div className="text-2xl font-bold text-text-primary tabular-nums">
                {selectedRanking.projection.toFixed(0)}
              </div>
              <div className="text-xs text-text-secondary">Projected pts</div>
              <div className="text-xs text-accent tabular-nums mt-0.5">
                VOR {selectedRanking.vor.toFixed(0)}
              </div>
            </div>
          </div>

          <div className="bg-bg-card border border-border rounded-md p-4">
            <ProjectionChart player={selectedRanking.player} />
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'ADP', value: selectedRanking.adp },
              { label: 'Model Rank', value: selectedRanking.modelRank },
              { label: 'ADP Delta', value: selectedRanking.adpDelta < 0 ? `+${Math.abs(selectedRanking.adpDelta)}` : `${selectedRanking.adpDelta}` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-bg-card border border-border rounded-lg p-3 text-center">
                <div className="text-xs text-text-secondary mb-1">{label}</div>
                <div className="text-lg font-bold text-text-primary">{value}</div>
              </div>
            ))}
          </div>

          <div className="bg-bg-card border border-border rounded-md p-4">
            <ComparablePlayers ranking={selectedRanking} allRankings={rankings} />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
          {isLoading ? 'Loading…' : 'Select a player'}
        </div>
      )}
    </div>
  )
}
