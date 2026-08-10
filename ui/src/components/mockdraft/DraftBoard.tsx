import { useDraftState } from '../../hooks'
import { PositionBadge } from '../ui/Badge'

export function DraftBoard() {
  const { state } = useDraftState()
  const { teams, totalRounds, userPickPosition } = state.config

  // Build a map from overallPick → DraftedPick
  const pickMap = new Map(state.picks.map(p => [p.overallPick, p]))

  // User's column for each round (1-indexed slot within the round)
  function userSlotInRound(round: number): number {
    return round % 2 === 1 ? userPickPosition : teams - userPickPosition + 1
  }

  return (
    <div className="overflow-auto">
      <table className="text-xs border-collapse min-w-full">
        <thead>
          <tr>
            <th className="text-text-muted px-2 py-1 text-left w-8">Rd</th>
            {Array.from({ length: teams }, (_, i) => (
              <th key={i} className="text-text-muted px-1 py-1 text-center min-w-[80px]">
                T{i + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: totalRounds }, (_, ri) => {
            const round = ri + 1
            const userSlot = userSlotInRound(round)
            return (
              <tr key={round} className="border-t border-border/30">
                <td className="text-text-muted px-2 py-1.5 font-medium">{round}</td>
                {Array.from({ length: teams }, (_, si) => {
                  const slot = si + 1
                  const overall = (round - 1) * teams + slot
                  const pick = pickMap.get(overall)
                  const isUserSlot = slot === userSlot
                  return (
                    <td
                      key={slot}
                      className={`px-1 py-1.5 text-center ${isUserSlot ? 'bg-accent/10 ring-1 ring-accent' : ''}`}
                    >
                      {pick ? (
                        <div className="flex flex-col items-center gap-0.5">
                          <PositionBadge position={pick.player.position} />
                          <span className={`text-xs truncate max-w-[72px] ${pick.isUserPick ? 'text-accent font-medium' : 'text-text-secondary'}`}>
                            {pick.player.name.split(' ').slice(-1)[0]}
                          </span>
                        </div>
                      ) : (
                        <span className={`text-text-muted/40 ${isUserSlot ? 'text-accent/30' : ''}`}>
                          {isUserSlot ? '●' : '—'}
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
