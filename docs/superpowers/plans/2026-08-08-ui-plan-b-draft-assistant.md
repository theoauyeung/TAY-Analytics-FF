# UI Plan B: Draft Assistant

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully interactive three-panel Draft Assistant page where the user can simulate a live snake draft — entering picks, seeing real-time roster updates, positional scarcity, and contextual recommendations powered by a mock draft-score engine.

**Architecture:** Live draft state lives in a React Context + useReducer store (scoped to the Draft Assistant page). A mock recommendation engine (`useMockRecommendation`) reads precomputed rankings + live draft state and returns a typed `RecommendationState` on every pick — the same interface the real backend will eventually return. All three panels (Available Players, Recommendation, My Roster) are driven by the same state; replacing the mock engine with a real API call later requires only swapping the hook body.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, existing types from `ui/src/types/`, existing mock data from `ui/src/data/`, clsx, lucide-react

## Global Constraints

- No `any` types anywhere
- Draft state lives only in `ui/src/state/draftState.ts` — no local state duplication across panels
- All panels consume state via `useDraftState()` hook — never import context directly in components
- `RecommendationState` shape must match `ui/src/types/recommendation.ts` exactly — this is the API contract
- Tailwind custom theme colors only — no hardcoded hex values in components
- Named exports throughout — no default exports on components or hooks
- `npm run build` must pass with zero TypeScript errors after every task
- Desktop-first layout: three panels side by side, full viewport height minus context bar

---

## File Map

```
ui/src/
├── state/
│   ├── draftState.ts          # DraftConfig, DraftedPick, LiveDraftState, reducer, DraftContext, DraftProvider, computeUserPickNumbers
│   └── index.ts               # barrel export
├── hooks/
│   ├── useDraftState.ts       # action creators wrapping dispatch + derived values
│   └── useMockRecommendation.ts  # mock draft-score engine → RecommendationState
├── data/
│   └── mockDraftConfig.ts     # DEFAULT_DRAFT_CONFIG — 12-team PPR, user at pick 6
├── components/
│   └── draft/
│       ├── DraftContextBar.tsx      # top bar: Round/Pick, picks until next, player count
│       ├── AvailablePlayers.tsx     # left panel: undrafted table with draft action
│       ├── RecommendationPanel.tsx  # center panel: top pick + explanation + alternatives
│       ├── AlternativeCard.tsx      # single alternative card used by RecommendationPanel
│       ├── MyRoster.tsx             # right panel: roster slots + strength assessment
│       ├── ScarcityBar.tsx          # positional scarcity visualization
│       └── MayNotMakeItBack.tsx     # players likely gone before next pick
└── pages/
    └── DraftAssistant.tsx     # three-panel assembly, DraftProvider wrapper
```

**Existing files modified:**
- `ui/src/types/draft.ts` — extend with `DraftConfig`, `DraftedPick`, `LiveDraftState`
- `ui/src/data/index.ts` — add `mockDraftConfig` export

---

## Task 1: Draft State — Types, Context, Reducer

**Files:**
- Modify: `ui/src/types/draft.ts`
- Create: `ui/src/state/draftState.ts`
- Create: `ui/src/state/index.ts`
- Create: `ui/src/data/mockDraftConfig.ts`
- Modify: `ui/src/data/index.ts`

**Interfaces:**
- Produces: `DraftConfig`, `DraftedPick`, `LiveDraftState`, `DraftAction`, `draftReducer`, `DraftContext`, `DraftProvider`, `computeUserPickNumbers` — all exported from `ui/src/state/draftState.ts`
- Produces: `DEFAULT_DRAFT_CONFIG: DraftConfig` from `ui/src/data/mockDraftConfig.ts`

- [ ] **Step 1: Extend `ui/src/types/draft.ts`**

Replace the entire file with:

```ts
import type { Position, PlayerDetail, ScoringFormat } from './player'

export interface RosterConfig {
  QB: number
  RB: number
  WR: number
  TE: number
  FLEX: number
  BENCH: number
  K: number
  DST: number
}

export interface RosterSlot {
  slotType: Position | 'FLEX' | 'BENCH' | 'IR'
  player: PlayerDetail | null
}

export interface Roster {
  slots: RosterSlot[]
  totalProjection: number
  floor: number
  ceiling: number
  positionalStrength: Record<Position, 'elite' | 'strong' | 'average' | 'weak' | 'empty'>
  primaryNeed: Position | null
}

export interface DraftConfig {
  teams: number               // e.g. 12
  userPickPosition: number    // 1-indexed pick in round 1 (e.g. 6)
  scoringFormat: ScoringFormat
  rosterConfig: RosterConfig
  totalRounds: number         // sum of all rosterConfig values
}

export interface DraftedPick {
  player: PlayerDetail
  overallPick: number         // 1-indexed overall pick number
  round: number
  pickInRound: number         // 1-indexed within the round
  teamNumber: number          // which team picked (1-indexed)
  isUserPick: boolean
}

export interface LiveDraftState {
  config: DraftConfig
  picks: DraftedPick[]        // all picks made so far in order
  currentOverallPick: number  // next pick to be made (1-indexed)
}

// Legacy — kept for type compatibility, not used by Draft Assistant
export interface DraftState {
  leagueId: string
  teams: number
  scoringFormat: ScoringFormat
  rosterConfig: Record<string, number>
  currentRound: number
  currentPick: number
  userDraftPosition: number
  picksUntilNextTurn: number
  draftedPlayerIds: string[]
  userRoster: Roster
}
```

- [ ] **Step 2: Create `ui/src/data/mockDraftConfig.ts`**

```ts
import type { DraftConfig } from '../types'

export const DEFAULT_DRAFT_CONFIG: DraftConfig = {
  teams: 12,
  userPickPosition: 6,
  scoringFormat: 'ppr',
  rosterConfig: {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    FLEX: 1,
    BENCH: 6,
    K: 0,
    DST: 0,
  },
  totalRounds: 13,   // 1+2+2+1+1+6 = 13
}
```

- [ ] **Step 3: Add to `ui/src/data/index.ts`**

Append this line:

```ts
export { DEFAULT_DRAFT_CONFIG } from './mockDraftConfig'
```

- [ ] **Step 4: Create `ui/src/state/draftState.ts`**

```ts
import { createContext, useContext, useReducer, type ReactNode } from 'react'
import type { DraftConfig, DraftedPick, LiveDraftState } from '../types'
import { DEFAULT_DRAFT_CONFIG } from '../data'

// ─── Snake-draft helpers ───────────────────────────────────────────────────

/** Team number picking at a given overall pick in a snake draft (1-indexed). */
export function getPickingTeam(overallPick: number, teams: number): number {
  const pickInRound = ((overallPick - 1) % teams) + 1
  const round = Math.ceil(overallPick / teams)
  return round % 2 === 1 ? pickInRound : teams - pickInRound + 1
}

/** All overall pick numbers where the user picks in a snake draft. */
export function computeUserPickNumbers(config: DraftConfig): number[] {
  const { teams, userPickPosition, totalRounds } = config
  return Array.from({ length: totalRounds }, (_, i) => {
    const round = i + 1
    const pickInRound = round % 2 === 1
      ? userPickPosition
      : teams - userPickPosition + 1
    return (round - 1) * teams + pickInRound
  })
}

/** Picks until the user's next selection (0 = it's the user's turn). */
export function picksUntilNextTurn(state: LiveDraftState): number {
  const userPicks = computeUserPickNumbers(state.config)
  const next = userPicks.find(n => n >= state.currentOverallPick)
  return next === undefined ? 0 : next - state.currentOverallPick
}

// ─── Reducer ──────────────────────────────────────────────────────────────

export type DraftAction =
  | { type: 'DRAFT_PLAYER'; player: import('../types').PlayerDetail; isUserPick: boolean }
  | { type: 'UNDO_LAST_PICK' }
  | { type: 'RESET_DRAFT' }
  | { type: 'UPDATE_CONFIG'; config: DraftConfig }

export function draftReducer(state: LiveDraftState, action: DraftAction): LiveDraftState {
  switch (action.type) {
    case 'DRAFT_PLAYER': {
      const { currentOverallPick, config } = state
      const round = Math.ceil(currentOverallPick / config.teams)
      const pickInRound = ((currentOverallPick - 1) % config.teams) + 1
      const teamNumber = action.isUserPick
        ? config.userPickPosition
        : getPickingTeam(currentOverallPick, config.teams)

      const pick: DraftedPick = {
        player: action.player,
        overallPick: currentOverallPick,
        round,
        pickInRound,
        teamNumber,
        isUserPick: action.isUserPick,
      }
      return {
        ...state,
        picks: [...state.picks, pick],
        currentOverallPick: currentOverallPick + 1,
      }
    }

    case 'UNDO_LAST_PICK':
      if (state.picks.length === 0) return state
      return {
        ...state,
        picks: state.picks.slice(0, -1),
        currentOverallPick: state.currentOverallPick - 1,
      }

    case 'RESET_DRAFT':
      return { ...state, picks: [], currentOverallPick: 1 }

    case 'UPDATE_CONFIG':
      return { ...state, config: action.config, picks: [], currentOverallPick: 1 }

    default:
      return state
  }
}

// ─── Context ──────────────────────────────────────────────────────────────

interface DraftContextValue {
  state: LiveDraftState
  dispatch: React.Dispatch<DraftAction>
}

export const DraftContext = createContext<DraftContextValue | null>(null)

export function useDraftContext(): DraftContextValue {
  const ctx = useContext(DraftContext)
  if (!ctx) throw new Error('useDraftContext must be used inside <DraftProvider>')
  return ctx
}

// ─── Provider ─────────────────────────────────────────────────────────────

const INITIAL_STATE: LiveDraftState = {
  config: DEFAULT_DRAFT_CONFIG,
  picks: [],
  currentOverallPick: 1,
}

export function DraftProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(draftReducer, INITIAL_STATE)
  return (
    <DraftContext.Provider value={{ state, dispatch }}>
      {children}
    </DraftContext.Provider>
  )
}
```

- [ ] **Step 5: Create `ui/src/state/index.ts`**

```ts
export {
  draftReducer,
  DraftContext,
  DraftProvider,
  useDraftContext,
  computeUserPickNumbers,
  picksUntilNextTurn,
  getPickingTeam,
} from './draftState'
export type { DraftAction } from './draftState'
```

- [ ] **Step 6: Verify TypeScript — no errors**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

Expected: no output (zero errors).

- [ ] **Step 7: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/types/draft.ts ui/src/state/ ui/src/data/mockDraftConfig.ts ui/src/data/index.ts
git commit -m "feat: add live draft state — context, reducer, snake-draft helpers"
```

---

## Task 2: useDraftState Hook

**Files:**
- Create: `ui/src/hooks/useDraftState.ts`

**Interfaces:**
- Consumes: `useDraftContext`, `computeUserPickNumbers`, `picksUntilNextTurn` from `ui/src/state/draftState.ts`; `PlayerDetail` from `ui/src/types`
- Produces: `useDraftState()` returning `{ state, config, picks, currentOverallPick, currentRound, picksUntilNext, userPicks, userRoster, draftedIds, draftPlayer, undoLastPick, resetDraft }`

- [ ] **Step 1: Create `ui/src/hooks/useDraftState.ts`**

```ts
import { useCallback } from 'react'
import { useDraftContext, computeUserPickNumbers, picksUntilNextTurn } from '../state/draftState'
import type { PlayerDetail } from '../types'

export function useDraftState() {
  const { state, dispatch } = useDraftContext()
  const { config, picks, currentOverallPick } = state

  const currentRound = Math.min(
    config.totalRounds,
    Math.ceil(currentOverallPick / config.teams)
  )

  const userPickNumbers = computeUserPickNumbers(config)
  const picksUntilNext = picksUntilNextTurn(state)

  const draftedIds = new Set(picks.map(p => p.player.id))
  const userRoster = picks.filter(p => p.isUserPick).map(p => p.player)

  const draftPlayer = useCallback(
    (player: PlayerDetail, isUserPick: boolean) => {
      dispatch({ type: 'DRAFT_PLAYER', player, isUserPick })
    },
    [dispatch]
  )

  const undoLastPick = useCallback(
    () => dispatch({ type: 'UNDO_LAST_PICK' }),
    [dispatch]
  )

  const resetDraft = useCallback(
    () => dispatch({ type: 'RESET_DRAFT' }),
    [dispatch]
  )

  const isUserTurn = picksUntilNext === 0 && currentOverallPick <= config.teams * config.totalRounds
  const isDraftComplete = currentOverallPick > config.teams * config.totalRounds

  return {
    state,
    config,
    picks,
    currentOverallPick,
    currentRound,
    picksUntilNext,
    userPickNumbers,
    draftedIds,
    userRoster,
    isUserTurn,
    isDraftComplete,
    draftPlayer,
    undoLastPick,
    resetDraft,
  }
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/hooks/useDraftState.ts
git commit -m "feat: add useDraftState hook with action creators and derived values"
```

---

## Task 3: Mock Recommendation Engine

**Files:**
- Create: `ui/src/hooks/useMockRecommendation.ts`

**Interfaces:**
- Consumes: `LiveDraftState` from `ui/src/types/draft.ts`; `MOCK_RANKINGS` from `ui/src/data`; `computeUserPickNumbers` from `ui/src/state`; `Ranking`, `RecommendationState`, `PositionalScarcity`, `FutureAvailability`, `RecommendationExplanation` from `ui/src/types`
- Produces: `useMockRecommendation(state: LiveDraftState): RecommendationState`

- [ ] **Step 1: Create `ui/src/hooks/useMockRecommendation.ts`**

```ts
import { useMemo } from 'react'
import type { LiveDraftState, RosterConfig } from '../types'
import type {
  Ranking, RecommendationState, PositionalScarcity,
  FutureAvailability, RecommendationExplanation,
} from '../types'
import { MOCK_RANKINGS } from '../data'
import { computeUserPickNumbers } from '../state'

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

/**
 * Roster fit score (0–1) for a position given the user's current roster.
 * Key insight: QBs have drastically lower marginal value after the first
 * in a 1-QB league — the model must reflect this.
 */
function rosterFitScore(
  position: string,
  userPositions: string[],
  config: RosterConfig
): number {
  const count = userPositions.filter(p => p === position).length

  if (position === 'QB') {
    if (count === 0) return 1.0
    if (count === 1) return 0.12   // backup QB has minimal value in 1-QB
    return 0.04
  }

  const starterSlots = (config[position as keyof RosterConfig] as number | undefined) ?? 0
  const flexSlots = (position === 'RB' || position === 'WR' || position === 'TE')
    ? config.FLEX : 0
  const benchSlots = Math.floor(config.BENCH / 4)   // rough bench depth allowance per position

  if (count < starterSlots) return 1.0
  if (count < starterSlots + flexSlots) return 0.72
  if (count < starterSlots + flexSlots + benchSlots) return 0.28
  return 0.05
}

interface ScoredRanking {
  ranking: Ranking
  draftScore: number
  rosterFit: number
  futureAvailability: FutureAvailability
  explanation: RecommendationExplanation[]
}

function buildExplanation(
  ranking: Ranking,
  components: { vor: number; fit: number; scarcity: number; urgency: number },
  pGone: number,
  userPositions: string[],
): RecommendationExplanation[] {
  const result: RecommendationExplanation[] = []
  const pos = ranking.player.position

  // Primary: projection value
  if (components.vor > 50) {
    result.push({
      factor: 'Strong Model Value',
      detail: `${ranking.projection.toFixed(0)} projected pts · VOR +${ranking.vor.toFixed(1)} · Model rank #${ranking.modelRank}`,
      weight: 'primary',
    })
  }

  // Roster fit
  if (components.fit > 65) {
    const count = userPositions.filter(p => p === pos).length
    result.push({
      factor: count === 0 ? `No ${pos} Yet` : `${pos} Depth`,
      detail: count === 0
        ? `You have no ${pos} — fills a critical starting slot`
        : `Adds depth at ${pos} — fills flex or bench need`,
      weight: 'secondary',
    })
  }

  // Scarcity
  if (components.scarcity > 55) {
    result.push({
      factor: `${pos} Scarcity`,
      detail: `Viable ${pos}s running low — positional run likely soon`,
      weight: 'secondary',
    })
  }

  // Urgency
  if (pGone > 0.64) {
    result.push({
      factor: 'May Not Make It Back',
      detail: `~${Math.round(pGone * 100)}% chance drafted before your next pick`,
      weight: 'primary',
    })
  }

  // Market value
  if (ranking.adpDelta >= 5) {
    result.push({
      factor: 'Undervalued',
      detail: `Model ranks ${ranking.adpDelta} spots ahead of ESPN ADP`,
      weight: 'secondary',
    })
  }

  // Risk flags
  if (ranking.player.injuryStatus && ranking.player.injuryStatus !== 'healthy') {
    result.push({
      factor: 'Injury Risk',
      detail: `Currently ${ranking.player.injuryStatus} — monitor before draft`,
      weight: 'risk',
    })
  }
  if (ranking.player.rookieYear) {
    result.push({
      factor: 'Rookie Uncertainty',
      detail: 'Higher variance — production range is wide',
      weight: 'risk',
    })
  }

  return result.slice(0, 5)   // cap at 5 explanation bullets
}

export function useMockRecommendation(state: LiveDraftState): RecommendationState | null {
  return useMemo(() => {
    const draftedIds = new Set(state.picks.map(p => p.player.id))
    const available = MOCK_RANKINGS.filter(r => !draftedIds.has(r.player.id))

    if (available.length === 0) return null

    const userPickNumbers = computeUserPickNumbers(state.config)
    const nextUserPick = userPickNumbers.find(n => n >= state.currentOverallPick)
    const picksUntilNext = nextUserPick === undefined ? 0 : nextUserPick - state.currentOverallPick

    const userPositions = state.picks
      .filter(p => p.isUserPick)
      .map(p => p.player.position as string)

    // VOR normalization
    const vors = available.map(r => r.vor)
    const maxVOR = Math.max(...vors)
    const minVOR = Math.min(...vors)
    const vorRange = Math.max(1, maxVOR - minVOR)

    // Viable player counts per position (VOR > 0 = "viable")
    const viableCounts: Record<string, number> = {}
    for (const r of available) {
      if (r.vor > 0) {
        viableCounts[r.player.position] = (viableCounts[r.player.position] ?? 0) + 1
      }
    }

    // Score every available player
    const scored: ScoredRanking[] = available.map(ranking => {
      const pos = ranking.player.position

      // Component 1: VOR (35%)
      const vorScore = clamp((ranking.vor - minVOR) / vorRange, 0, 1) * 100

      // Component 2: Roster Fit (30%)
      const fitRaw = rosterFitScore(pos, userPositions, state.config.rosterConfig)
      const fitScore = fitRaw * 100

      // Component 3: Positional Scarcity (20%) — higher score = more scarce
      const viable = viableCounts[pos] ?? 0
      const scarcityScore = clamp(1 - viable / 18, 0, 1) * 100

      // Component 4: Urgency / Future Availability (15%)
      // P(gone before next pick) — if ADP is near current pick and many picks until user's turn, very urgent
      const adpGap = Math.max(1, ranking.adp - state.currentOverallPick + 1)
      const pGone = clamp(picksUntilNext / adpGap, 0, 1)
      const urgencyScore = pGone * 100

      const draftScore = Math.round(
        vorScore    * 0.35 +
        fitScore    * 0.30 +
        scarcityScore * 0.20 +
        urgencyScore  * 0.15
      )

      const futureAvailability: FutureAvailability = {
        playerId: ranking.player.id,
        probability: pGone,
        label: pGone > 0.75 ? 'urgent' : pGone > 0.55 ? 'monitor' : 'safe',
      }

      const components = { vor: vorScore, fit: fitScore, scarcity: scarcityScore, urgency: urgencyScore }
      const explanation = buildExplanation(ranking, components, pGone, userPositions)

      return { ranking, draftScore, rosterFit: fitRaw, futureAvailability, explanation }
    })

    scored.sort((a, b) => b.draftScore - a.draftScore)
    const [top, ...rest] = scored

    // Positional scarcity output
    const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const
    const scarcity: PositionalScarcity[] = POSITIONS.map(pos => ({
      position: pos,
      viableRemaining: viableCounts[pos] ?? 0,
      scarcityScore: clamp(1 - (viableCounts[pos] ?? 0) / 18, 0, 1),
      tierRemaining: available.filter(r => r.player.position === pos && r.tier.number <= 3).length,
    }))

    // Positional needs (0–1 urgency score per position)
    const positionalNeeds = Object.fromEntries(
      POSITIONS.map(pos => [pos, rosterFitScore(pos, userPositions, state.config.rosterConfig)])
    ) as Record<string, number>

    // May Not Make It Back — P(gone) > 0.64
    const mayNotMakeItBack: FutureAvailability[] = available
      .map(r => {
        const gap = Math.max(1, r.adp - state.currentOverallPick + 1)
        const prob = clamp(picksUntilNext / gap, 0, 1)
        return { playerId: r.player.id, probability: prob, label: prob > 0.75 ? 'urgent' : 'monitor' } as FutureAvailability
      })
      .filter(x => x.probability > 0.64)
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 5)

    function toItem(s: ScoredRanking) {
      return {
        ...s.ranking,
        draftScore: s.draftScore,
        rosterFit: s.rosterFit,
        futureAvailability: s.futureAvailability,
        explanation: s.explanation,
      }
    }

    return {
      topPick: toItem(top),
      alternatives: rest.slice(0, 4).map(toItem),
      positionalNeeds,
      scarcity,
      mayNotMakeItBack,
    }
  }, [state])
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/hooks/useMockRecommendation.ts
git commit -m "feat: add mock draft-score recommendation engine"
```

---

## Task 4: Draft Context Bar

**Files:**
- Create: `ui/src/components/draft/DraftContextBar.tsx`

**Interfaces:**
- Consumes: `useDraftState()` from `ui/src/hooks/useDraftState.ts`; `MOCK_RANKINGS` for total player count
- Produces: `<DraftContextBar />` — fixed top bar showing round/pick, picks until next, player counts, undo/reset controls

- [ ] **Step 1: Create `ui/src/components/draft/DraftContextBar.tsx`**

```tsx
import { RotateCcw, Undo2, Users } from 'lucide-react'
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { MOCK_RANKINGS } from '../../data'

export function DraftContextBar() {
  const {
    currentRound, currentOverallPick, config,
    picksUntilNext, isUserTurn, isDraftComplete,
    picks, undoLastPick, resetDraft,
  } = useDraftState()

  const totalPicks = config.teams * config.totalRounds
  const draftedCount = picks.length
  const remainingCount = MOCK_RANKINGS.length - draftedCount

  return (
    <div className="h-14 flex-shrink-0 bg-bg-secondary border-b border-border flex items-center px-4 gap-6">
      {/* Round / Pick */}
      <div className="flex items-center gap-3">
        <div className="text-center">
          <div className="text-xs text-text-muted uppercase tracking-widest leading-tight">Round</div>
          <div className="text-lg font-bold text-text-primary leading-tight">{currentRound}</div>
        </div>
        <div className="w-px h-8 bg-border" />
        <div className="text-center">
          <div className="text-xs text-text-muted uppercase tracking-widest leading-tight">Pick</div>
          <div className="text-lg font-bold text-text-primary leading-tight">
            {Math.min(currentOverallPick, totalPicks)}
          </div>
        </div>
      </div>

      <div className="w-px h-8 bg-border" />

      {/* User turn indicator */}
      <div className={clsx(
        'px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide',
        isDraftComplete
          ? 'bg-border text-text-muted'
          : isUserTurn
            ? 'bg-accent text-bg-primary animate-pulse'
            : 'bg-bg-elevated text-text-secondary'
      )}>
        {isDraftComplete
          ? 'DRAFT COMPLETE'
          : isUserTurn
            ? 'YOUR PICK'
            : `YOUR PICK IN ${picksUntilNext}`
        }
      </div>

      {/* Players remaining */}
      <div className="flex items-center gap-2 text-text-secondary ml-auto">
        <Users size={14} />
        <span className="text-sm">{remainingCount} remaining</span>
        <span className="text-text-muted">·</span>
        <span className="text-sm text-text-muted">{draftedCount}/{totalPicks} picked</span>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={undoLastPick}
          disabled={picks.length === 0}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:text-text-primary hover:border-accent transition-colors disabled:opacity-40 disabled:pointer-events-none"
        >
          <Undo2 size={13} />
          Undo
        </button>
        <button
          onClick={resetDraft}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:text-red-400 hover:border-red-400 transition-colors"
        >
          <RotateCcw size={13} />
          Reset
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/draft/DraftContextBar.tsx
git commit -m "feat: add draft context bar (round/pick/turn indicator/controls)"
```

---

## Task 5: Available Players Panel

**Files:**
- Create: `ui/src/components/draft/AvailablePlayers.tsx`

**Interfaces:**
- Consumes: `useDraftState()`, `MOCK_RANKINGS`, `PositionBadge` from `ui/Badge.tsx`, `SignalBadge` from `ui/Badge.tsx`
- Produces: `<AvailablePlayers />` — left panel; filterable table of undrafted players; click row to get draft confirmation inline

- [ ] **Step 1: Create `ui/src/components/draft/AvailablePlayers.tsx`**

```tsx
import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'
import clsx from 'clsx'
import type { Position } from '../../types'
import { MOCK_RANKINGS } from '../../data'
import { useDraftState } from '../../hooks/useDraftState'
import { PositionBadge } from '../ui/Badge'

const POSITION_FILTERS: Array<Position | 'ALL'> = ['ALL', 'QB', 'RB', 'WR', 'TE']

export function AvailablePlayers() {
  const { draftedIds, draftPlayer, isUserTurn } = useDraftState()
  const [search, setSearch] = useState('')
  const [posFilter, setPosFilter] = useState<Position | 'ALL'>('ALL')
  const [pendingId, setPendingId] = useState<string | null>(null)

  const available = useMemo(() => {
    return MOCK_RANKINGS
      .filter(r => !draftedIds.has(r.player.id))
      .filter(r => posFilter === 'ALL' || r.player.position === posFilter)
      .filter(r => {
        if (!search) return true
        const q = search.toLowerCase()
        return r.player.name.toLowerCase().includes(q) || r.player.team.toLowerCase().includes(q)
      })
  }, [draftedIds, posFilter, search])

  function handleDraft(playerId: string, isMine: boolean) {
    const ranking = MOCK_RANKINGS.find(r => r.player.id === playerId)
    if (!ranking) return
    draftPlayer(ranking.player, isMine)
    setPendingId(null)
  }

  return (
    <div className="flex flex-col h-full border-r border-border w-80 flex-shrink-0">
      {/* Header */}
      <div className="px-3 pt-3 pb-2 border-b border-border flex-shrink-0">
        <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-2">
          Available Players
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-bg-elevated border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
          />
        </div>

        {/* Position filter */}
        <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary">
          {POSITION_FILTERS.map(pos => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={clsx(
                'flex-1 py-1 text-xs font-medium transition-colors',
                posFilter === pos
                  ? 'bg-accent text-bg-primary'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated'
              )}
            >
              {pos}
            </button>
          ))}
        </div>
      </div>

      {/* Player list */}
      <div className="flex-1 overflow-y-auto">
        {available.map(ranking => {
          const isPending = pendingId === ranking.player.id
          const adpDelta = ranking.adpDelta

          return (
            <div key={ranking.player.id}>
              {/* Player row */}
              <div
                onClick={() => setPendingId(isPending ? null : ranking.player.id)}
                className={clsx(
                  'flex items-center gap-2.5 px-3 py-2.5 cursor-pointer border-b border-border/40 transition-colors',
                  isPending ? 'bg-accent-muted' : 'hover:bg-bg-elevated'
                )}
              >
                {/* Rank */}
                <span className="text-xs font-mono text-text-muted w-6 text-right flex-shrink-0">
                  {ranking.rank}
                </span>

                {/* Headshot */}
                <div className="w-7 h-7 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
                  {ranking.player.imageUrl ? (
                    <img
                      src={ranking.player.imageUrl}
                      alt={ranking.player.name}
                      className="w-full h-full object-cover"
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xs font-bold text-text-muted">
                      {ranking.player.name.charAt(0)}
                    </div>
                  )}
                </div>

                {/* Name + team */}
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-text-primary truncate">
                    {ranking.player.name}
                  </div>
                  <div className="text-xs text-text-muted">{ranking.player.team}</div>
                </div>

                {/* Position badge */}
                <PositionBadge position={ranking.player.position} />

                {/* ADP delta */}
                {adpDelta !== 0 && (
                  <span className={clsx(
                    'text-xs font-mono',
                    adpDelta >= 5 ? 'text-green-400' : adpDelta <= -5 ? 'text-red-400' : 'text-text-muted'
                  )}>
                    {adpDelta > 0 ? '+' : ''}{adpDelta}
                  </span>
                )}
              </div>

              {/* Draft confirmation inline */}
              {isPending && (
                <div className="flex items-center gap-2 px-3 py-2 bg-accent-muted border-b border-accent/30">
                  <span className="text-xs text-text-secondary flex-1 truncate">
                    Draft {ranking.player.name}?
                  </span>
                  <button
                    onClick={() => handleDraft(ranking.player.id, true)}
                    className="px-2.5 py-1 text-xs font-bold bg-accent text-bg-primary rounded-lg hover:bg-accent-dim transition-colors"
                  >
                    Mine
                  </button>
                  <button
                    onClick={() => handleDraft(ranking.player.id, false)}
                    className="px-2.5 py-1 text-xs font-medium border border-border text-text-secondary rounded-lg hover:text-text-primary hover:border-accent transition-colors"
                  >
                    Other
                  </button>
                  <button
                    onClick={() => setPendingId(null)}
                    className="text-xs text-text-muted hover:text-text-primary"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>
          )
        })}

        {available.length === 0 && (
          <div className="flex items-center justify-center h-32 text-text-muted text-sm">
            No players found
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/draft/AvailablePlayers.tsx
git commit -m "feat: add available players panel with inline draft confirmation"
```

---

## Task 6: Recommendation Panel + Alternative Card

**Files:**
- Create: `ui/src/components/draft/AlternativeCard.tsx`
- Create: `ui/src/components/draft/RecommendationPanel.tsx`

**Interfaces:**
- Consumes: `useDraftState()`, `useMockRecommendation()`, `RecommendationState` top-pick and alternatives shapes, `PositionBadge`, `SignalBadge`
- Produces: `<RecommendationPanel />` — center panel; top pick with draft score + explanation + scarcity + "May Not Make It Back"; `<AlternativeCard />` for each alternative

- [ ] **Step 1: Create `ui/src/components/draft/AlternativeCard.tsx`**

```tsx
import clsx from 'clsx'
import type { RecommendationState } from '../../types'
import { PositionBadge } from '../ui/Badge'

type AlternativeItem = RecommendationState['alternatives'][number]

interface Props {
  alt: AlternativeItem
  rank: number
  isSelected: boolean
  onClick: () => void
}

export function AlternativeCard({ alt, rank, isSelected, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left p-3 rounded-xl border transition-colors',
        isSelected
          ? 'border-accent bg-accent-muted'
          : 'border-border bg-bg-elevated hover:border-accent/50 hover:bg-bg-elevated'
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <div className="w-6 h-6 rounded-full overflow-hidden bg-bg-card flex-shrink-0">
          {alt.player.imageUrl ? (
            <img
              src={alt.player.imageUrl}
              alt={alt.player.name}
              className="w-full h-full object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-xs font-bold text-text-muted">
              {alt.player.name.charAt(0)}
            </div>
          )}
        </div>
        <span className="text-sm font-semibold text-text-primary flex-1 truncate">
          {alt.player.name}
        </span>
        <PositionBadge position={alt.player.position} />
      </div>

      <div className="flex items-center gap-3 text-xs text-text-muted">
        <span>
          Draft Score: <span className="text-text-secondary font-medium">{alt.draftScore}</span>
        </span>
        <span>
          VOR: <span className={alt.vor >= 0 ? 'text-green-400' : 'text-red-400'}>
            {alt.vor >= 0 ? '+' : ''}{alt.vor.toFixed(1)}
          </span>
        </span>
        {alt.futureAvailability.probability > 0.55 && (
          <span className="text-yellow-400">
            {Math.round(alt.futureAvailability.probability * 100)}% gone
          </span>
        )}
      </div>
    </button>
  )
}
```

- [ ] **Step 2: Create `ui/src/components/draft/RecommendationPanel.tsx`**

```tsx
import { useState } from 'react'
import { Zap, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { useMockRecommendation } from '../../hooks/useMockRecommendation'
import { PositionBadge } from '../ui/Badge'
import { AlternativeCard } from './AlternativeCard'
import { ScarcityBar } from './ScarcityBar'
import { MayNotMakeItBack } from './MayNotMakeItBack'

export function RecommendationPanel() {
  const { state, draftPlayer, isDraftComplete } = useDraftState()
  const reco = useMockRecommendation(state)
  const [selectedAltIdx, setSelectedAltIdx] = useState<number | null>(null)

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

  if (!reco) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
        No players available
      </div>
    )
  }

  const displayed = selectedAltIdx !== null ? reco.alternatives[selectedAltIdx] : reco.topPick
  const isShowingAlt = selectedAltIdx !== null

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">

      {/* Header label */}
      <div className="flex items-center gap-2">
        <Zap size={14} className="text-accent" />
        <span className="text-xs font-bold tracking-widest text-accent uppercase">
          {isShowingAlt ? 'Alternative Pick' : 'Your Best Pick'}
        </span>
        {isShowingAlt && (
          <button
            onClick={() => setSelectedAltIdx(null)}
            className="ml-auto text-xs text-text-muted hover:text-text-primary"
          >
            ← Back to top pick
          </button>
        )}
      </div>

      {/* Main player card */}
      <div className="bg-bg-card border border-border rounded-2xl p-5">
        <div className="flex items-start gap-4 mb-4">
          {/* Headshot */}
          <div className="w-16 h-16 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
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
            { label: 'Proj', value: displayed.projection.toFixed(0) },
            { label: 'VOR', value: `${displayed.vor >= 0 ? '+' : ''}${displayed.vor.toFixed(1)}`, highlight: displayed.vor >= 20 },
            { label: 'ADP', value: displayed.adp },
            { label: 'Avail', value: `${Math.round((1 - displayed.futureAvailability.probability) * 100)}%`, highlight: displayed.futureAvailability.probability < 0.4 },
          ].map(m => (
            <div key={m.label} className="bg-bg-elevated rounded-xl p-2.5 text-center">
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
          className="w-full py-2.5 bg-accent text-bg-primary text-sm font-bold rounded-xl hover:bg-accent-dim transition-colors"
        >
          Draft {displayed.player.name} (Mine)
        </button>
      </div>

      {/* WHY? */}
      {displayed.explanation.length > 0 && (
        <div>
          <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-2">Why?</div>
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
          <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-2">
            Alternatives
          </div>
          <div className="space-y-2">
            {reco.alternatives.map((alt, i) => (
              <AlternativeCard
                key={alt.player.id}
                alt={alt}
                rank={i + 1}
                isSelected={selectedAltIdx === i}
                onClick={() => setSelectedAltIdx(selectedAltIdx === i ? null : i)}
              />
            ))}
          </div>
        </div>
      )}

      {/* May Not Make It Back */}
      <MayNotMakeItBack items={reco.mayNotMakeItBack} allRankings={[]} />

      {/* Scarcity */}
      <ScarcityBar scarcity={reco.scarcity} />
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

Note: this step will fail until Task 7 creates `ScarcityBar` and `MayNotMakeItBack`. If tsc fails only on those two missing imports, proceed to Task 7 immediately and verify after Task 7.

- [ ] **Step 4: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/draft/AlternativeCard.tsx ui/src/components/draft/RecommendationPanel.tsx
git commit -m "feat: add recommendation panel and alternative card"
```

---

## Task 7: Scarcity Bar + May Not Make It Back

**Files:**
- Create: `ui/src/components/draft/ScarcityBar.tsx`
- Create: `ui/src/components/draft/MayNotMakeItBack.tsx`

**Interfaces:**
- Consumes: `PositionalScarcity`, `FutureAvailability` from `ui/src/types`; `MOCK_RANKINGS` for player lookup in MayNotMakeItBack
- Produces: `<ScarcityBar scarcity={PositionalScarcity[]} />`, `<MayNotMakeItBack items={FutureAvailability[]} allRankings={Ranking[]} />`

- [ ] **Step 1: Create `ui/src/components/draft/ScarcityBar.tsx`**

```tsx
import clsx from 'clsx'
import type { PositionalScarcity } from '../../types'

interface Props {
  scarcity: PositionalScarcity[]
}

const MAX_VIABLE = 18   // baseline for 100% bar width

export function ScarcityBar({ scarcity }: Props) {
  if (scarcity.length === 0) return null

  return (
    <div>
      <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-3">
        Positional Scarcity
      </div>
      <div className="space-y-2.5">
        {scarcity.map(s => {
          const pctRemaining = Math.min(1, s.viableRemaining / MAX_VIABLE)
          const isLow = s.viableRemaining <= 6
          const isMed = s.viableRemaining > 6 && s.viableRemaining <= 12

          return (
            <div key={s.position}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-text-secondary">{s.position}</span>
                <span className={clsx(
                  'text-xs font-mono',
                  isLow ? 'text-red-400' : isMed ? 'text-yellow-400' : 'text-text-muted'
                )}>
                  {s.viableRemaining} viable
                </span>
              </div>
              <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    isLow ? 'bg-red-500' : isMed ? 'bg-yellow-500' : 'bg-accent'
                  )}
                  style={{ width: `${Math.round(pctRemaining * 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `ui/src/components/draft/MayNotMakeItBack.tsx`**

```tsx
import { AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import type { FutureAvailability, Ranking } from '../../types'
import { MOCK_RANKINGS } from '../../data'
import { PositionBadge } from '../ui/Badge'

interface Props {
  items: FutureAvailability[]
  allRankings: Ranking[]    // kept in interface for future real-data use; uses MOCK_RANKINGS internally for now
}

export function MayNotMakeItBack({ items }: Props) {
  if (items.length === 0) return null

  // Look up player details from MOCK_RANKINGS by playerId
  const withPlayers = items
    .map(item => ({
      item,
      ranking: MOCK_RANKINGS.find(r => r.player.id === item.playerId),
    }))
    .filter((x): x is { item: FutureAvailability; ranking: Ranking } => x.ranking !== undefined)

  if (withPlayers.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle size={13} className="text-yellow-400" />
        <span className="text-xs font-bold tracking-widest text-yellow-400 uppercase">
          May Not Make It Back
        </span>
      </div>
      <div className="space-y-1.5">
        {withPlayers.map(({ item, ranking }) => (
          <div
            key={item.playerId}
            className="flex items-center gap-2.5 px-3 py-2 bg-yellow-900/10 border border-yellow-400/20 rounded-lg"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text-primary truncate">
                  {ranking.player.name}
                </span>
                <PositionBadge position={ranking.player.position} />
              </div>
              <div className="text-xs text-text-muted">{ranking.player.team}</div>
            </div>
            <div className="text-right flex-shrink-0">
              <div className={clsx(
                'text-sm font-bold',
                item.probability > 0.80 ? 'text-red-400' : 'text-yellow-400'
              )}>
                {Math.round(item.probability * 100)}%
              </div>
              <div className="text-xs text-text-muted">gone</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript — full build**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

Expected: zero errors (RecommendationPanel's imports now resolve).

- [ ] **Step 4: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/draft/ScarcityBar.tsx ui/src/components/draft/MayNotMakeItBack.tsx
git commit -m "feat: add positional scarcity bar and may-not-make-it-back component"
```

---

## Task 8: My Roster Panel

**Files:**
- Create: `ui/src/components/draft/MyRoster.tsx`

**Interfaces:**
- Consumes: `useDraftState()`, `useMockRecommendation()`, `PositionBadge`
- Produces: `<MyRoster />` — right panel; roster slots by position, positional strength assessment, primary need label

- [ ] **Step 1: Create `ui/src/components/draft/MyRoster.tsx`**

```tsx
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { useMockRecommendation } from '../../hooks/useMockRecommendation'
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
  add('BN', 'BENCH', config.BENCH)
  return slots
}

function fillSlots(slots: SlotDef[], roster: PlayerDetail[]): Array<{ slot: SlotDef; player: PlayerDetail | null }> {
  const remaining = [...roster]
  return slots.map(slot => {
    const pos = slot.position
    const idx = remaining.findIndex(p =>
      pos === 'FLEX'
        ? (p.position === 'RB' || p.position === 'WR' || p.position === 'TE')
        : pos === 'BENCH'
          ? true
          : p.position === pos
    )
    if (idx === -1) return { slot, player: null }
    const [player] = remaining.splice(idx, 1)
    return { slot, player }
  })
}

function strengthLabel(count: number, needed: number): { label: string; color: string } {
  if (count === 0) return { label: 'Empty', color: 'text-text-muted' }
  if (count >= needed + 1) return { label: 'Strong', color: 'text-green-400' }
  if (count >= needed) return { label: 'OK', color: 'text-text-secondary' }
  return { label: 'Weak', color: 'text-yellow-400' }
}

export function MyRoster() {
  const { state, userRoster, config } = useDraftState()
  const reco = useMockRecommendation(state)

  const slots = buildSlots(config.rosterConfig)
  const filled = fillSlots(slots, userRoster)

  const POSITIONS: Position[] = ['QB', 'RB', 'WR', 'TE']
  const positionCounts = Object.fromEntries(
    POSITIONS.map(pos => [pos, userRoster.filter(p => p.position === pos).length])
  ) as Record<Position, number>

  const needed: Record<Position, number> = {
    QB: config.rosterConfig.QB,
    RB: config.rosterConfig.RB,
    WR: config.rosterConfig.WR,
    TE: config.rosterConfig.TE,
    K: 0,
    DST: 0,
  }

  const primaryNeed = reco
    ? POSITIONS.reduce((best, pos) => {
        const need = (reco.positionalNeeds as Record<string, number>)[pos] ?? 0
        const bestNeed = (reco.positionalNeeds as Record<string, number>)[best] ?? 0
        return need > bestNeed ? pos : best
      }, 'RB' as Position)
    : null

  return (
    <div className="w-72 flex-shrink-0 border-l border-border flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-3 pb-2 border-b border-border flex-shrink-0">
        <div className="text-xs font-bold tracking-widest text-text-muted uppercase">My Roster</div>
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
              <span className="text-xs text-text-muted italic">Empty</span>
            )}
          </div>
        ))}
      </div>

      {/* Roster assessment */}
      <div className="border-t border-border px-4 py-3 space-y-1.5 flex-shrink-0">
        <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-2">
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
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/draft/MyRoster.tsx
git commit -m "feat: add my roster panel with slot filling and strength assessment"
```

---

## Task 9: Draft Assistant Page Assembly

**Files:**
- Modify: `ui/src/pages/DraftAssistant.tsx`

**Interfaces:**
- Consumes: `DraftProvider` from `ui/src/state`; `DraftContextBar`, `AvailablePlayers`, `RecommendationPanel`, `MyRoster` from `ui/src/components/draft/`
- Produces: fully interactive `/draft` page with three-panel layout and working draft simulation

- [ ] **Step 1: Replace `ui/src/pages/DraftAssistant.tsx`**

```tsx
import { DraftProvider } from '../state'
import { DraftContextBar } from '../components/draft/DraftContextBar'
import { AvailablePlayers } from '../components/draft/AvailablePlayers'
import { RecommendationPanel } from '../components/draft/RecommendationPanel'
import { MyRoster } from '../components/draft/MyRoster'

function DraftAssistantInner() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <DraftContextBar />
      <div className="flex flex-1 overflow-hidden">
        <AvailablePlayers />
        <RecommendationPanel />
        <MyRoster />
      </div>
    </div>
  )
}

export default function DraftAssistant() {
  return (
    <DraftProvider>
      <DraftAssistantInner />
    </DraftProvider>
  )
}
```

- [ ] **Step 2: Run full build to verify zero errors**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npm run build 2>&1 | tail -15
```

Expected: `✓ built in <N>ms`, no TypeScript errors.

- [ ] **Step 3: Verify the Draft Assistant manually**

Start the dev server (`npm run dev`), navigate to `http://localhost:5173/draft`, and verify:

- [ ] Three panels visible side by side
- [ ] "YOUR PICK" badge pulses when it's the user's turn (pick 6)
- [ ] Top recommendation shows a non-QB player at pick 1 (QBs deprioritized before user's turn)
- [ ] Clicking a player in the left panel shows inline "Mine" / "Other" confirmation
- [ ] Clicking "Other" advances the pick counter and removes the player from the available list
- [ ] Clicking "Mine" adds the player to the My Roster panel and removes them from available
- [ ] After drafting some players, "WHY?" explanation bullets update based on actual roster state
- [ ] Positional Scarcity bars decrease as players are drafted
- [ ] May Not Make It Back section shows when picks until user's turn is high enough
- [ ] Undo button reverts the last pick
- [ ] Reset button clears all picks

- [ ] **Step 4: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/pages/DraftAssistant.tsx
git commit -m "feat: assemble complete Draft Assistant page — live three-panel draft room"
```

---

## Self-Review

**Spec coverage check:**

- ✅ Three-panel layout: Available Players (left) / Recommendation (center) / My Roster (right)
- ✅ Draft State with current round, pick, picks-until-next, drafted players, user roster
- ✅ Click player → "Mine" / "Other Team" inline confirmation
- ✅ Undo last pick, Reset draft
- ✅ Draft Context Bar: Round/Pick, picks until next, "YOUR PICK" indicator, player counts
- ✅ Recommendation panel: Draft Score, projection, VOR, ADP, availability %, draft button
- ✅ "WHY?" explanation bullets driven by actual factor values (not templates)
- ✅ 2–4 alternative picks with AlternativeCard — click to compare
- ✅ QB deprioritized in 1-QB league via `rosterFitScore` (0.12 after first QB)
- ✅ Draft Score is not dominated by raw projection — VOR 35%, roster fit 30%, scarcity 20%, urgency 15%
- ✅ My Roster: position slots filled in order, strength assessment, primary need
- ✅ Positional Scarcity bars with color coding (red < 6, yellow 6–12, blue > 12)
- ✅ May Not Make It Back: P(gone) > 64%, sorted by probability, capped at 5
- ✅ Mock recommendation engine returns `RecommendationState` — same interface real backend will use
- ✅ `DraftProvider` is page-scoped — doesn't pollute global app state
- ✅ `useDraftState` is the only access point — no direct context imports in components
- ✅ No `any` types

**Type consistency check:**

- `DraftedPick.player` → `PlayerDetail` ✅
- `useDraftState().draftPlayer(player: PlayerDetail, isUserPick: boolean)` matches `DRAFT_PLAYER` action ✅
- `useMockRecommendation` returns `RecommendationState | null` — consumers handle null ✅
- `PositionalScarcity.position` is `Position` type ✅
- `FutureAvailability.label` is `'safe' | 'monitor' | 'urgent'` matching type definition ✅
- `ScarcityBar` props: `{ scarcity: PositionalScarcity[] }` ✅
- `MayNotMakeItBack` props: `{ items: FutureAvailability[]; allRankings: Ranking[] }` ✅
- `AlternativeCard` consumes `RecommendationState['alternatives'][number]` ✅

**Note for Task 6 implementer:** `RecommendationPanel` imports `ScarcityBar` and `MayNotMakeItBack` which are created in Task 7. The TypeScript check in Task 6 Step 3 will fail until Task 7 is complete — implement Task 7 immediately after committing Task 6 files, then run `tsc --noEmit` once both tasks are done.
