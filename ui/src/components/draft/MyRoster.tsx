import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { useRecommendation } from '../../hooks/useRecommendation'
import { PositionBadge } from '../ui/Badge'
import type { Position, PlayerDetail, RosterConfig } from '../../types'

interface SlotDef {
  label: string
  position: Position | 'FLEX' | 'BENCH'
}

function buildSlots(config: RosterConfig): SlotDef[] {
  const slots: SlotDef[] = []
  const add = (label: string, position: Position | 'FLEX' | 'BENCH', count: number) => {
    for (let i = 0; i < count; i++) {
      slots.push({ label: count > 1 ? `${label}${i + 1}` : label, position })
    }
  }
  add('QB', 'QB', config.QB)
  add('RB', 'RB', config.RB)
  add('WR', 'WR', config.WR)
  add('TE', 'TE', config.TE)
  add('FLEX', 'FLEX', config.FLEX)
  if (config.K > 0) add('K', 'K', config.K)
  if (config.DST > 0) add('DST', 'DST', config.DST)
  add('BN', 'BENCH', config.BENCH)
  return slots
}

function fillSlots(
  slots: SlotDef[],
  roster: PlayerDetail[]
): Array<{ slot: SlotDef; player: PlayerDetail | null }> {
  const remaining = [...roster]
  return slots.map(slot => {
    const pos = slot.position
    const idx = remaining.findIndex(p =>
      pos === 'FLEX'
        ? (p.position === 'RB' || p.position === 'WR' || p.position === 'TE')
        : pos === 'BENCH'
          ? true
          : p.position === (pos as string)
    )
    if (idx === -1) return { slot, player: null }
    const [player] = remaining.splice(idx, 1)
    return { slot, player }
  })
}

function strengthLabel(count: number, needed: number): { label: string; color: string } {
  if (count === 0) return { label: 'Weak', color: 'text-yellow-400' }
  if (count >= needed + 2) return { label: 'Elite', color: 'text-green-400' }
  if (count >= needed + 1) return { label: 'Strong', color: 'text-green-400' }
  if (count >= needed) return { label: 'Average', color: 'text-text-secondary' }
  return { label: 'Weak', color: 'text-yellow-400' }
}

export function MyRoster() {
  const { state, userPicks } = useDraftState()
  const { recommendation: reco } = useRecommendation()

  const config = state.config
  const userRoster: PlayerDetail[] = userPicks.map(p => p.player)

  const slots = buildSlots(config.rosterConfig)
  const filled = fillSlots(slots, userRoster)

  const POSITIONS: Position[] = [
    'QB', 'RB', 'WR', 'TE',
    ...(config.rosterConfig.K > 0 ? ['K' as Position] : []),
    ...(config.rosterConfig.DST > 0 ? ['DST' as Position] : []),
  ]
  const positionCounts = Object.fromEntries(
    POSITIONS.map(pos => [pos, userRoster.filter(p => p.position === pos).length])
  ) as Record<Position, number>

  const needed: Record<Position, number> = {
    QB: config.rosterConfig.QB,
    RB: config.rosterConfig.RB,
    WR: config.rosterConfig.WR,
    TE: config.rosterConfig.TE,
    K: config.rosterConfig.K,
    DST: config.rosterConfig.DST,
  }

  const primaryNeed = reco
    ? POSITIONS.reduce((best, pos) => {
        const need = (reco.positionalNeeds as Record<string, number>)[pos] ?? 0
        const bestNeed = (reco.positionalNeeds as Record<string, number>)[best] ?? 0
        return need > bestNeed ? pos : best
      }, POSITIONS[0])
    : null

  return (
    <div className="w-72 flex-shrink-0 border-l border-border flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-3 pb-2 border-b border-border flex-shrink-0">
        <div className="text-xs font-bold tracking-wide text-text-muted uppercase">My Roster</div>
        <div className="text-xs text-text-muted mt-0.5">
          {userRoster.length} / {config.totalRounds} picks
        </div>
      </div>

      {/* Roster slots */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {filled.map(({ slot, player }, i) => (
          <div
            key={i}
            className={clsx(
              'flex items-center gap-2.5 px-2.5 py-2 rounded-lg',
              player ? 'bg-bg-elevated' : 'bg-bg-secondary border border-dashed border-border/50'
            )}
          >
            {/* Slot label */}
            <span className="text-xs font-mono text-text-muted w-10 flex-shrink-0">
              {slot.label}
            </span>

            {player ? (
              <>
                <div className="w-6 h-6 rounded-full overflow-hidden bg-bg-card flex-shrink-0">
                  {player.imageUrl ? (
                    <img
                      src={player.imageUrl}
                      alt={player.name}
                      className="w-full h-full object-cover"
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xs font-bold text-text-muted">
                      {player.name.charAt(0)}
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-text-primary truncate">{player.name}</div>
                  <div className="text-xs text-text-muted">{player.team}</div>
                </div>
                <PositionBadge position={player.position} />
              </>
            ) : (
              <span className="text-xs text-text-muted italic">Available</span>
            )}
          </div>
        ))}
      </div>

      {/* Roster assessment */}
      <div className="border-t border-border px-4 py-3 space-y-1.5 flex-shrink-0">
        <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">
          Assessment
        </div>
        {POSITIONS.map(pos => {
          const { label, color } = strengthLabel(positionCounts[pos], needed[pos])
          return (
            <div key={pos} className="flex items-center justify-between">
              <span className="text-xs text-text-secondary">{pos}</span>
              <span className={clsx('text-xs font-medium', color)}>{label}</span>
            </div>
          )
        })}
        {primaryNeed && (
          <div className="mt-2 pt-2 border-t border-border/50 flex items-center justify-between">
            <span className="text-xs text-text-muted">Priority</span>
            <span className="text-xs font-bold text-accent">{primaryNeed}</span>
          </div>
        )}
      </div>
    </div>
  )
}
