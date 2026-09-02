import { createContext, useContext, useEffect, useReducer, type ReactNode } from 'react'
import type { DraftConfig, DraftedPick, LiveDraftState } from '../types'

const DEFAULT_DRAFT_CONFIG: DraftConfig = {
  teams: 12,
  userPickPosition: 6,
  scoringFormat: 'ppr',
  rosterConfig: {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    FLEX: 2,
    BENCH: 5,
    K: 1,
    DST: 1,
  },
  totalRounds: 15,
}

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
  | { type: 'DRAFT_PLAYER'; payload: import('../types').PlayerDetail; isUserPick?: boolean }
  | { type: 'UNDO_LAST_PICK' }
  | { type: 'RESET_DRAFT' }
  | { type: 'UPDATE_CONFIG'; config: DraftConfig }
  | { type: 'START_DRAFT' }

export function draftReducer(state: LiveDraftState, action: DraftAction): LiveDraftState {
  switch (action.type) {
    case 'DRAFT_PLAYER': {
      const { currentOverallPick, config } = state
      const round = Math.ceil(currentOverallPick / config.teams)
      const pickInRound = ((currentOverallPick - 1) % config.teams) + 1
      const userPickNumbers = computeUserPickNumbers(config)
      const isUserPick = action.isUserPick !== undefined
        ? action.isUserPick
        : userPickNumbers.includes(currentOverallPick)
      const teamNumber = isUserPick
        ? config.userPickPosition
        : getPickingTeam(currentOverallPick, config.teams)

      const pick: DraftedPick = {
        player: action.payload,
        overallPick: currentOverallPick,
        round,
        pickInRound,
        teamNumber,
        isUserPick,
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

    case 'START_DRAFT':
      return { ...state, draftPhase: 'active' }

    case 'RESET_DRAFT':
      return { ...state, picks: [], currentOverallPick: 1, draftPhase: 'setup' }

    case 'UPDATE_CONFIG':
      return { ...state, config: action.config, picks: [], currentOverallPick: 1, draftPhase: 'setup' }

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

const DRAFT_STORAGE_KEY = 'tay-draft-state'

const INITIAL_STATE: LiveDraftState = {
  config: DEFAULT_DRAFT_CONFIG,
  picks: [],
  currentOverallPick: 1,
  draftPhase: 'setup',
}

function loadPersistedState(): LiveDraftState {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY)
    if (!raw) return INITIAL_STATE
    const parsed = JSON.parse(raw) as LiveDraftState
    if (!parsed.config || !Array.isArray(parsed.picks)) return INITIAL_STATE
    return { ...INITIAL_STATE, ...parsed, draftPhase: parsed.draftPhase ?? 'setup' }
  } catch {
    return INITIAL_STATE
  }
}

export function DraftProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(draftReducer, undefined, loadPersistedState)

  // Persist every state change to localStorage
  useEffect(() => {
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(state))
  }, [state])

  return (
    <DraftContext.Provider value={{ state, dispatch }}>
      {children}
    </DraftContext.Provider>
  )
}
