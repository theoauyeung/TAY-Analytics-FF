import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { useRecommendation } from '../../hooks/useRecommendation'
import { useRankings } from '../../hooks/useRankings'
import { ApiError } from '../../api/client'
import { PositionBadge } from '../ui/Badge'
import { AlternativeCard } from './AlternativeCard'
import { ScarcityBar } from './ScarcityBar'
import { MayNotMakeItBack } from './MayNotMakeItBack'

export function RecommendationPanel() {
  const { state, draftPlayer } = useDraftState()
  const { recommendation: reco, error: recoError } = useRecommendation()
  const { rankings } = useRankings({ position: 'ALL', search: '', format: 'ppr', draftType: 'redraft', year: 2026, tierFilter: null })
  const [selectedAltIdx, setSelectedAltIdx] = useState<number | null>(null)

  const totalPicks = state.config.teams * state.config.totalRounds
  const isDraftComplete = state.currentOverallPick > totalPicks

  if (isDraftComplete) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted">
        <div className="text-center">
          <div className="text-2xl font-bold mb-2">Draft Complete</div>
          <div className="text-sm">All rounds filled. Check your roster in the right panel.</div>
        </div>
      </div>
    )
  }

  if (recoError instanceof ApiError && recoError.status === 422) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted">
        <div className="text-center">
          <div className="text-lg font-bold mb-1">Draft Pool Exhausted</div>
          <div className="text-sm">No available players to recommend.</div>
        </div>
      </div>
    )
  }

  if (!reco) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
        Loading recommendations...
      </div>
    )
  }

  const displayed = selectedAltIdx !== null ? reco.alternatives[selectedAltIdx] : reco.topPick
  const isShowingAlt = selectedAltIdx !== null

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">

      {/* Header label */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold tracking-wide text-accent uppercase">
          {isShowingAlt ? 'Alternative Pick' : 'Your Pick'}
        </span>
        {isShowingAlt && (
          <button
            onClick={() => setSelectedAltIdx(null)}
            className="ml-auto text-xs text-text-muted hover:text-text-primary"
          >
            Back to top pick
          </button>
        )}
      </div>

      {/* Main player card */}
      <div className="bg-bg-card border border-border rounded-lg p-5">
        <div className="flex items-start gap-4 mb-4">
          {/* Headshot */}
          <div className="w-12 h-12 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
            {displayed.player.imageUrl ? (
              <img
                src={displayed.player.imageUrl}
                alt={displayed.player.name}
                className="w-full h-full object-cover"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xl font-bold text-text-muted">
                {displayed.player.name.charAt(0)}
              </div>
            )}
          </div>

          {/* Name + team + position */}
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-text-primary leading-tight">
              {displayed.player.name}
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <PositionBadge position={displayed.player.position} />
              <span className="text-sm text-text-secondary">{displayed.player.team}</span>
              <span className="text-text-muted">·</span>
              <span className="text-sm text-text-muted">Bye {displayed.player.byeWeek}</span>
            </div>
          </div>

          {/* Draft Score */}
          <div className="text-right flex-shrink-0">
            <div className="text-xs text-text-muted mb-0.5">Draft Score</div>
            <div className="text-3xl font-bold text-accent">{displayed.draftScore}</div>
          </div>
        </div>

        {/* Key metrics row */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            { label: 'Proj', value: displayed.projection.toFixed(0), highlight: false },
            { label: 'VOR', value: `${displayed.vor >= 0 ? '+' : ''}${displayed.vor.toFixed(1)}`, highlight: displayed.vor >= 20 },
            { label: 'ADP', value: String(displayed.adp), highlight: false },
            { label: 'Avail', value: `${Math.round((1 - displayed.futureAvailability.probability) * 100)}%`, highlight: displayed.futureAvailability.probability < 0.4 },
          ].map(m => (
            <div key={m.label} className="bg-bg-elevated rounded-md p-2.5 text-center">
              <div className="text-xs text-text-muted mb-0.5">{m.label}</div>
              <div className={clsx('text-base font-bold', m.highlight ? 'text-accent' : 'text-text-primary')}>
                {m.value}
              </div>
            </div>
          ))}
        </div>

        {/* Draft button */}
        <button
          onClick={() => draftPlayer(displayed.player, true)}
          className="w-full py-2.5 bg-accent text-bg-primary text-sm font-bold rounded-md hover:bg-accent-dim transition-colors"
        >
          Draft {displayed.player.name} (Mine)
        </button>
      </div>

      {/* WHY? */}
      {displayed.explanation.length > 0 && (
        <div>
          <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">Why?</div>
          <div className="space-y-1.5">
            {displayed.explanation.map((ex, i) => (
              <div
                key={i}
                className={clsx(
                  'flex items-start gap-2.5 p-2.5 rounded-lg text-xs',
                  ex.weight === 'primary' ? 'bg-accent-muted border border-accent/20' :
                  ex.weight === 'risk' ? 'bg-red-900/20 border border-red-400/20' :
                  'bg-bg-elevated border border-border'
                )}
              >
                {ex.weight === 'risk' && <AlertTriangle size={12} className="text-red-400 flex-shrink-0 mt-0.5" />}
                <div>
                  <span className={clsx(
                    'font-semibold',
                    ex.weight === 'primary' ? 'text-accent' :
                    ex.weight === 'risk' ? 'text-red-400' :
                    'text-text-primary'
                  )}>
                    {ex.factor}
                  </span>
                  <span className="text-text-secondary ml-1.5">{ex.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alternatives */}
      {reco.alternatives.length > 0 && (
        <div>
          <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">
            Alternatives
          </div>
          <div className="space-y-2">
            {reco.alternatives.slice(0, 5).map((alt, i) => (
              <AlternativeCard
                key={alt.player.id}
                player={{ player: alt.player, score: alt.draftScore / 100, explanation: alt.explanation }}
                isSelected={selectedAltIdx === i}
                onClick={() => setSelectedAltIdx(selectedAltIdx === i ? null : i)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Scarcity Bar */}
      {reco.scarcity.length > 0 && (
        <div>
          <ScarcityBar scarcity={reco.scarcity} />
        </div>
      )}

      {/* May Not Make It Back */}
      {reco.mayNotMakeItBack.length > 0 && (
        <div>
          <MayNotMakeItBack items={reco.mayNotMakeItBack} allRankings={rankings} />
        </div>
      )}
    </div>
  )
}
