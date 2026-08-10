# UI Plan C — Remaining Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all five remaining UI pages — Dashboard, Settings, Player Explorer, Mock Draft, and Roster Analyzer — using mock data so the full app is navigable before the backend is wired.

**Architecture:** Each page is self-contained with its own component folder. All data flows through the existing mock data layer (`ui/src/data/`) and TanStack Query hooks — the same swap-boundary established in Plans A and B. Mock Draft reuses `DraftProvider` from Plan B; new auto-pick logic is a pure function in a separate file. Roster Analyzer maintains its own local state (no dependency on Draft state).

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS 3 (custom theme), Recharts 3 (already installed), TanStack Query v5, existing `DraftProvider` + `useDraftState` from Plan B.

## Global Constraints

- Working directory for all UI work: `ui/` inside the project root
- TypeScript strict mode — `npx tsc --noEmit` must pass after every task
- Tailwind theme tokens (exact values): `bg-bg-primary: '#0F1117'`, `bg-bg-secondary: '#161B22'`, `bg-bg-card: '#1C2230'`, `bg-bg-elevated: '#222B3A'`, `border-border: '#2D3748'`, `text-accent: '#60B4FF'`, `bg-accent: '#60B4FF'`, `bg-accent-muted: '#1E3A5F'`, `text-text-primary: '#E8EDF5'`, `text-text-secondary: '#8B98A8'`, `text-text-muted: '#556070'`, position colors: `text-pos-qb: '#E8844A'`, `text-pos-rb: '#4AE8A0'`, `text-pos-wr: '#60B4FF'`, `text-pos-te: '#C47EE8'`
- No new dependencies — Recharts already in `package.json`
- No test suite exists — verify with `npx tsc --noEmit` and visual check in running dev server
- Commit after each task with `feat:` or `fix:` prefix
- All new component folders must have an `index.ts` barrel export
- `PositionBadge` is always imported from `'../ui/Badge'` (or `'../../components/ui/Badge'` from pages)
- `Spinner` is in `'../ui/Spinner'`
- Existing types live in `ui/src/types/` — never redefine them

## Existing Infrastructure (read before implementing)

- Types: `ui/src/types/player.ts` (`PlayerDetail`, `Projection`, `Position`, `ScoringFormat`), `ui/src/types/ranking.ts` (`Ranking`, `RankingFilters`)
- Mock data: `ui/src/data/mockPlayers.ts` (120 players), `ui/src/data/mockRankings.ts` (`MOCK_RANKINGS: Ranking[]` sorted by VOR descending)
- `Ranking` fields: `rank`, `positionRank`, `player: PlayerDetail`, `tier`, `projection`, `vor`, `adp`, `modelRank`, `adpDelta`, `floor`, `ceiling`, `targetShare`, `rushShare`, `snapPct`, `routePct`, `redZoneUsage`, `tdProjection`, `gamesPlayed`, `modelConfidence`
- `PlayerDetail` fields: `id`, `name`, `position`, `team`, `byeWeek`, `age`, `experience`, `imageUrl`, `injuryStatus`, `projection: Projection`, `opportunity: OpportunityMetrics`, `efficiency: EfficiencyMetrics`, `modelConfidence`, `breakoutProbability`, `bustRisk`, `rookieYear`
- `Projection` fields: `mean`, `median`, `floor`, `ceiling`, `p10`, `p25`, `p75`, `p90`, `stdDev`, `boomProbability`, `bustProbability`, `gamesPlayed`
- Plan B exports: `DraftProvider`, `useDraftContext`, `getPickingTeam`, `computeUserPickNumbers`, `picksUntilNextTurn` from `ui/src/state/draftState.ts`; `useDraftState` from `ui/src/hooks/useDraftState.ts`; `DraftContextBar`, `AvailablePlayers`, `RecommendationPanel`, `MyRoster` from `ui/src/components/draft/`
- `DEFAULT_DRAFT_CONFIG` from `ui/src/data/mockDraftConfig.ts` — 12 teams, userPickPosition 6, PPR, 13 rounds, `{QB:1, RB:2, WR:2, TE:1, FLEX:1, BENCH:6}`
- `useRankings(filters: RankingFilters)` returns `{ rankings: Ranking[], isLoading: boolean }` from `ui/src/hooks/useRankings.ts`

---

## File Structure

```
ui/src/
├── data/
│   └── mockDashboard.ts          [NEW] derived stats for dashboard
├── hooks/
│   ├── useLeagueSettings.ts      [NEW] localStorage-backed league config
│   └── index.ts                  [MODIFY] add useLeagueSettings export
├── types/
│   └── settings.ts               [NEW] LeagueSettings interface
├── components/
│   ├── dashboard/
│   │   ├── TopValuesCard.tsx      [NEW] best VOR vs ADP picks
│   │   ├── PositionLeadersCard.tsx [NEW] top player per position
│   │   ├── ScarcityCard.tsx       [NEW] viable players remaining per position
│   │   ├── ModelMoversCard.tsx    [NEW] rising/falling vs ADP
│   │   └── index.ts               [NEW]
│   ├── players/
│   │   ├── PlayerSearch.tsx       [NEW] search + position filter input
│   │   ├── PlayerListRow.tsx      [NEW] compact row in explorer list
│   │   ├── ProjectionChart.tsx    [NEW] Recharts bar chart (p10–p90)
│   │   ├── ComparablePlayers.tsx  [NEW] same-position similar-VOR list
│   │   └── index.ts               [NEW]
│   ├── mockdraft/
│   │   ├── DraftBoard.tsx         [NEW] rounds × teams pick grid
│   │   ├── PreDraftConfig.tsx     [NEW] pick position + start button
│   │   └── index.ts               [NEW]
│   └── roster/
│       ├── RosterBuilder.tsx      [NEW] searchable player adder
│       ├── RosterProjection.tsx   [NEW] projected points / floor / ceiling
│       ├── PositionStrengthBars.tsx [NEW] Elite/Strong/Average/Weak per pos
│       └── index.ts               [NEW]
├── state/
│   └── mockDraftSimulator.ts      [NEW] bestAvailablePlayer pure function
└── pages/
    ├── Dashboard.tsx              [REPLACE stub]
    ├── Settings.tsx               [REPLACE stub]
    ├── Players.tsx                [REPLACE stub]
    ├── MockDraft.tsx              [REPLACE stub]
    └── RosterAnalyzer.tsx         [REPLACE stub]
```

---

### Task 1: Dashboard data layer

**Files:**
- Create: `ui/src/data/mockDashboard.ts`
- Modify: `ui/src/data/index.ts`

**Interfaces:**
- Consumes: `MOCK_RANKINGS: Ranking[]` from `'./mockRankings'`
- Produces (consumed by Task 2):
  - `TOP_VALUES: Ranking[]` — players where `adpDelta < -5` (model rank better than ADP by 5+), sorted by `adpDelta` ascending (most undervalued first), max 8
  - `POSITION_LEADERS: Record<'QB'|'RB'|'WR'|'TE', Ranking>` — top VOR player per position
  - `SCARCITY_OVERVIEW: Record<'QB'|'RB'|'WR'|'TE', number>` — count of players with `vor > 0` per position
  - `MODEL_MOVERS: { rising: Ranking[], falling: Ranking[] }` — rising: `adpDelta < -8` (model loves), falling: `adpDelta > 8` (model hates), up to 5 each

Note: `adpDelta = modelRank - adp`. Negative means model rank is better than ADP (undervalued). Positive means ADP is better than model rank (overvalued).

- [ ] **Step 1: Create `ui/src/data/mockDashboard.ts`**

```typescript
import { MOCK_RANKINGS } from './mockRankings'
import type { Ranking } from '../types'

// Undervalued: model rank (modelRank) is better than ADP — adpDelta is negative (modelRank - adp < 0)
export const TOP_VALUES: Ranking[] = MOCK_RANKINGS
  .filter(r => r.adpDelta < -5)
  .sort((a, b) => a.adpDelta - b.adpDelta)
  .slice(0, 8)

// Top player at each starter position by VOR
export const POSITION_LEADERS: Record<string, Ranking> = Object.fromEntries(
  (['QB', 'RB', 'WR', 'TE'] as const).map(pos => [
    pos,
    MOCK_RANKINGS.find(r => r.player.position === pos)!,
  ])
)

// Viable players (VOR > 0) remaining per position
export const SCARCITY_OVERVIEW: Record<string, number> = Object.fromEntries(
  (['QB', 'RB', 'WR', 'TE'] as const).map(pos => [
    pos,
    MOCK_RANKINGS.filter(r => r.player.position === pos && r.vor > 0).length,
  ])
)

// Model movers: biggest difference between model opinion and market ADP
export const MODEL_MOVERS: { rising: Ranking[], falling: Ranking[] } = {
  rising:  MOCK_RANKINGS.filter(r => r.adpDelta < -8).slice(0, 5),
  falling: MOCK_RANKINGS.filter(r => r.adpDelta > 8).slice(0, 5),
}
```

- [ ] **Step 2: Add export to `ui/src/data/index.ts`**

Append to the end of the file:
```typescript
export { TOP_VALUES, POSITION_LEADERS, SCARCITY_OVERVIEW, MODEL_MOVERS } from './mockDashboard'
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add ui/src/data/mockDashboard.ts ui/src/data/index.ts
git commit -m "feat: add dashboard mock data layer (values, leaders, scarcity, movers)"
```

---

### Task 2: Dashboard components

**Files:**
- Create: `ui/src/components/dashboard/TopValuesCard.tsx`
- Create: `ui/src/components/dashboard/PositionLeadersCard.tsx`
- Create: `ui/src/components/dashboard/ScarcityCard.tsx`
- Create: `ui/src/components/dashboard/ModelMoversCard.tsx`
- Create: `ui/src/components/dashboard/index.ts`

**Interfaces:**
- Consumes (from Task 1): `TOP_VALUES`, `POSITION_LEADERS`, `SCARCITY_OVERVIEW`, `MODEL_MOVERS`
- Produces (consumed by Task 3): four named exports

- [ ] **Step 1: Create `TopValuesCard.tsx`**

```typescript
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props { rankings: Ranking[] }

export function TopValuesCard({ rankings }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Best Values
      </div>
      <div className="space-y-2">
        {rankings.map(r => (
          <div key={r.player.id} className="flex items-center gap-2">
            <span className="text-xs text-text-muted w-5 text-right">{r.rank}</span>
            <PositionBadge position={r.player.position} />
            <span className="text-sm text-text-primary flex-1 truncate">{r.player.name}</span>
            <span className="text-xs text-text-secondary">{r.player.team}</span>
            <span className="text-xs font-medium text-accent tabular-nums">
              {r.adpDelta < 0 ? `+${Math.abs(r.adpDelta)}` : `-${r.adpDelta}`}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `PositionLeadersCard.tsx`**

```typescript
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props { leaders: Record<string, Ranking> }

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

export function PositionLeadersCard({ leaders }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Position Leaders
      </div>
      <div className="space-y-3">
        {POSITIONS.map(pos => {
          const r = leaders[pos]
          if (!r) return null
          return (
            <div key={pos} className="flex items-center gap-2">
              <PositionBadge position={pos} />
              <span className="text-sm text-text-primary flex-1 truncate">{r.player.name}</span>
              <span className="text-xs text-text-secondary tabular-nums">{r.projection.toFixed(0)} pts</span>
              <span className="text-xs text-text-muted tabular-nums">VOR {r.vor.toFixed(0)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `ScarcityCard.tsx`**

```typescript
interface Props { scarcity: Record<string, number> }

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const
const MAX_VIABLE = 30

function barColor(count: number): string {
  if (count < 6)  return 'bg-red-500'
  if (count <= 12) return 'bg-yellow-500'
  return 'bg-accent'
}

export function ScarcityCard({ scarcity }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Positional Scarcity
      </div>
      <div className="space-y-3">
        {POSITIONS.map(pos => {
          const count = scarcity[pos] ?? 0
          const width = Math.min(100, Math.round((count / MAX_VIABLE) * 100))
          return (
            <div key={pos}>
              <div className="flex justify-between mb-1">
                <span className="text-xs text-text-secondary">{pos}</span>
                <span className="text-xs text-text-muted">{count} viable</span>
              </div>
              <div className="h-1.5 bg-bg-elevated rounded-full">
                <div
                  className={`h-1.5 rounded-full transition-all ${barColor(count)}`}
                  style={{ width: `${width}%` }}
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

- [ ] **Step 4: Create `ModelMoversCard.tsx`**

```typescript
import { TrendingUp, TrendingDown } from 'lucide-react'
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props {
  rising: Ranking[]
  falling: Ranking[]
}

export function ModelMoversCard({ rising, falling }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Model vs Market
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="flex items-center gap-1 text-xs text-green-400 mb-2">
            <TrendingUp size={12} /> Rising
          </div>
          <div className="space-y-2">
            {rising.map(r => (
              <div key={r.player.id} className="flex items-center gap-1.5">
                <PositionBadge position={r.player.position} />
                <span className="text-xs text-text-primary truncate flex-1">{r.player.name}</span>
                <span className="text-xs text-green-400 tabular-nums">
                  +{Math.abs(r.adpDelta)}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 text-xs text-red-400 mb-2">
            <TrendingDown size={12} /> Falling
          </div>
          <div className="space-y-2">
            {falling.map(r => (
              <div key={r.player.id} className="flex items-center gap-1.5">
                <PositionBadge position={r.player.position} />
                <span className="text-xs text-text-primary truncate flex-1">{r.player.name}</span>
                <span className="text-xs text-red-400 tabular-nums">
                  -{r.adpDelta}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create `ui/src/components/dashboard/index.ts`**

```typescript
export { TopValuesCard } from './TopValuesCard'
export { PositionLeadersCard } from './PositionLeadersCard'
export { ScarcityCard } from './ScarcityCard'
export { ModelMoversCard } from './ModelMoversCard'
```

- [ ] **Step 6: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add ui/src/components/dashboard/
git commit -m "feat: add dashboard display components (values, leaders, scarcity, movers)"
```

---

### Task 3: Dashboard page

**Files:**
- Modify: `ui/src/pages/Dashboard.tsx` (replace stub entirely)

**Interfaces:**
- Consumes (from Tasks 1–2): `TOP_VALUES`, `POSITION_LEADERS`, `SCARCITY_OVERVIEW`, `MODEL_MOVERS` from `'../data'`; four card components from `'../components/dashboard'`

- [ ] **Step 1: Replace `ui/src/pages/Dashboard.tsx`**

```typescript
import { TopValuesCard, PositionLeadersCard, ScarcityCard, ModelMoversCard } from '../components/dashboard'
import { TOP_VALUES, POSITION_LEADERS, SCARCITY_OVERVIEW, MODEL_MOVERS } from '../data'

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-0.5">2026 Season — Mock Data</p>
      </div>

      {/* Top row: values + movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TopValuesCard rankings={TOP_VALUES} />
        <ModelMoversCard rising={MODEL_MOVERS.rising} falling={MODEL_MOVERS.falling} />
      </div>

      {/* Bottom row: leaders + scarcity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PositionLeadersCard leaders={POSITION_LEADERS} />
        <ScarcityCard scarcity={SCARCITY_OVERVIEW} />
      </div>

      {/* Model status placeholder */}
      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Model Status
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-yellow-400" />
          <span className="text-sm text-text-secondary">Running on mock data — backend not connected</span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/Dashboard.tsx
git commit -m "feat: build Dashboard page with values, movers, leaders, scarcity cards"
```

---

### Task 4: League settings hook

**Files:**
- Create: `ui/src/types/settings.ts`
- Create: `ui/src/hooks/useLeagueSettings.ts`
- Modify: `ui/src/types/index.ts` (add settings export)
- Modify: `ui/src/hooks/index.ts` (add useLeagueSettings export)

**Interfaces:**
- Produces (consumed by Tasks 5, 9): `LeagueSettings` type, `useLeagueSettings()` hook

- [ ] **Step 1: Create `ui/src/types/settings.ts`**

```typescript
import type { ScoringFormat } from './player'

export interface RosterConfig {
  QB: number
  RB: number
  WR: number
  TE: number
  FLEX: number
  BENCH: number
}

export interface LeagueSettings {
  teams: number          // 8–16
  format: ScoringFormat  // 'ppr' | 'half_ppr' | 'standard'
  rosterConfig: RosterConfig
}

export const DEFAULT_LEAGUE_SETTINGS: LeagueSettings = {
  teams: 12,
  format: 'ppr',
  rosterConfig: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, BENCH: 6 },
}
```

- [ ] **Step 2: Add to `ui/src/types/index.ts`**

Append to the end:
```typescript
export type { LeagueSettings, RosterConfig } from './settings'
export { DEFAULT_LEAGUE_SETTINGS } from './settings'
```

- [ ] **Step 3: Create `ui/src/hooks/useLeagueSettings.ts`**

```typescript
import { useState, useEffect, useCallback } from 'react'
import type { LeagueSettings } from '../types'
import { DEFAULT_LEAGUE_SETTINGS } from '../types'

const STORAGE_KEY = 'tay-league-settings'

function load(): LeagueSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULT_LEAGUE_SETTINGS, ...JSON.parse(raw) }
  } catch {
    // ignore parse errors
  }
  return DEFAULT_LEAGUE_SETTINGS
}

export function useLeagueSettings() {
  const [settings, setSettings] = useState<LeagueSettings>(load)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }, [settings])

  const update = useCallback((patch: Partial<LeagueSettings>) => {
    setSettings(prev => ({ ...prev, ...patch }))
  }, [])

  const reset = useCallback(() => {
    setSettings(DEFAULT_LEAGUE_SETTINGS)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  return { settings, update, reset }
}
```

- [ ] **Step 4: Add export to `ui/src/hooks/index.ts`**

Append:
```typescript
export { useLeagueSettings } from './useLeagueSettings'
```

- [ ] **Step 5: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/types/settings.ts ui/src/types/index.ts ui/src/hooks/useLeagueSettings.ts ui/src/hooks/index.ts
git commit -m "feat: add LeagueSettings type and useLeagueSettings hook with localStorage persistence"
```

---

### Task 5: Settings page

**Files:**
- Modify: `ui/src/pages/Settings.tsx` (replace stub entirely)

**Interfaces:**
- Consumes (from Task 4): `useLeagueSettings()` from `'../hooks'`
- `useLeagueSettings()` returns `{ settings: LeagueSettings, update: (patch: Partial<LeagueSettings>) => void, reset: () => void }`

- [ ] **Step 1: Replace `ui/src/pages/Settings.tsx`**

```typescript
import clsx from 'clsx'
import { useLeagueSettings } from '../hooks'
import type { ScoringFormat } from '../types'

const FORMATS: Array<{ value: ScoringFormat; label: string }> = [
  { value: 'ppr',      label: 'PPR' },
  { value: 'half_ppr', label: 'Half PPR' },
  { value: 'standard', label: 'Standard' },
]

const TEAM_COUNTS = [8, 10, 12, 14, 16]

const ROSTER_SLOTS = [
  { key: 'QB',   label: 'QB' },
  { key: 'RB',   label: 'RB' },
  { key: 'WR',   label: 'WR' },
  { key: 'TE',   label: 'TE' },
  { key: 'FLEX', label: 'FLEX' },
  { key: 'BENCH', label: 'Bench' },
] as const

export default function Settings() {
  const { settings, update, reset } = useLeagueSettings()

  return (
    <div className="p-6 max-w-2xl space-y-8 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Settings</h1>
        <p className="text-sm text-text-secondary mt-0.5">League configuration — saved automatically</p>
      </div>

      {/* Scoring Format */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-3">Scoring Format</h2>
        <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary w-fit">
          {FORMATS.map(f => (
            <button
              key={f.value}
              onClick={() => update({ format: f.value })}
              className={clsx(
                'px-4 py-2 text-sm font-medium transition-colors',
                settings.format === f.value
                  ? 'bg-accent text-bg-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </section>

      {/* League Size */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-3">League Size</h2>
        <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary w-fit">
          {TEAM_COUNTS.map(n => (
            <button
              key={n}
              onClick={() => update({ teams: n })}
              className={clsx(
                'px-4 py-2 text-sm font-medium transition-colors',
                settings.teams === n
                  ? 'bg-accent text-bg-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </section>

      {/* Roster Configuration */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-3">Roster Slots</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {ROSTER_SLOTS.map(({ key, label }) => (
            <div key={key} className="bg-bg-card border border-border rounded-lg p-3">
              <label className="text-xs text-text-secondary block mb-1">{label}</label>
              <input
                type="number"
                min={0}
                max={key === 'BENCH' ? 12 : 4}
                value={settings.rosterConfig[key]}
                onChange={e => update({
                  rosterConfig: {
                    ...settings.rosterConfig,
                    [key]: Math.max(0, parseInt(e.target.value) || 0),
                  }
                })}
                className="w-full bg-bg-elevated border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </div>
          ))}
        </div>
      </section>

      {/* Reset */}
      <section className="border-t border-border pt-6">
        <button
          onClick={reset}
          className="px-4 py-2 text-sm text-text-secondary border border-border rounded-lg hover:text-text-primary hover:border-accent transition-colors"
        >
          Reset to Defaults
        </button>
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/Settings.tsx
git commit -m "feat: build Settings page with scoring format, league size, roster config"
```

---

### Task 6: Player Explorer search + list

**Files:**
- Create: `ui/src/components/players/PlayerSearch.tsx`
- Create: `ui/src/components/players/PlayerListRow.tsx`
- Create: `ui/src/components/players/index.ts`

**Interfaces:**
- Consumes: `Ranking` from types, `PositionBadge` from `'../ui/Badge'`
- Produces (consumed by Task 8):
  - `PlayerSearch` props: `{ search: string, position: string, onSearchChange: (s: string) => void, onPositionChange: (p: string) => void }`
  - `PlayerListRow` props: `{ ranking: Ranking, selected: boolean, onClick: () => void }`

- [ ] **Step 1: Create `ui/src/components/players/PlayerSearch.tsx`**

```typescript
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
```

- [ ] **Step 2: Create `ui/src/components/players/PlayerListRow.tsx`**

```typescript
import clsx from 'clsx'
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props {
  ranking: Ranking
  selected: boolean
  onClick: () => void
}

export function PlayerListRow({ ranking, selected, onClick }: Props) {
  const { player, rank, projection, vor, adpDelta } = ranking
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full flex items-center gap-2 px-3 py-2 text-left transition-colors border-b border-border/50',
        selected
          ? 'bg-accent-muted border-l-2 border-accent'
          : 'hover:bg-bg-elevated'
      )}
    >
      <span className="text-xs text-text-muted w-6 text-right flex-shrink-0">{rank}</span>
      {player.imageUrl && (
        <img
          src={player.imageUrl}
          alt=""
          className="w-7 h-7 rounded-full object-cover flex-shrink-0 bg-bg-elevated"
          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-text-primary truncate">{player.name}</div>
        <div className="flex items-center gap-1 mt-0.5">
          <PositionBadge position={player.position} />
          <span className="text-xs text-text-muted">{player.team}</span>
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="text-xs text-text-primary tabular-nums">{projection.toFixed(0)}</div>
        <div className={clsx('text-xs tabular-nums', adpDelta < 0 ? 'text-accent' : adpDelta > 0 ? 'text-red-400' : 'text-text-muted')}>
          VOR {vor.toFixed(0)}
        </div>
      </div>
    </button>
  )
}
```

- [ ] **Step 3: Create `ui/src/components/players/index.ts`**

```typescript
export { PlayerSearch } from './PlayerSearch'
export { PlayerListRow } from './PlayerListRow'
```

(ProjectionChart and ComparablePlayers will be added in Task 7.)

- [ ] **Step 4: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/players/
git commit -m "feat: add player explorer search input and list row components"
```

---

### Task 7: Projection chart + comparable players

**Files:**
- Create: `ui/src/components/players/ProjectionChart.tsx`
- Create: `ui/src/components/players/ComparablePlayers.tsx`
- Modify: `ui/src/components/players/index.ts`

**Interfaces:**
- Consumes: `PlayerDetail`, `Ranking`, `MOCK_RANKINGS` from `'../../data'`
- Produces (consumed by Task 8):
  - `ProjectionChart` props: `{ player: PlayerDetail }`
  - `ComparablePlayers` props: `{ ranking: Ranking; allRankings: Ranking[] }`

- [ ] **Step 1: Create `ui/src/components/players/ProjectionChart.tsx`**

Uses Recharts BarChart to show the 5 projection percentile points (p10, p25, median, p75, p90).

```typescript
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import type { PlayerDetail } from '../../types'

interface Props { player: PlayerDetail }

const PERCENTILE_COLORS = ['#556070', '#3A7FBF', '#60B4FF', '#3A7FBF', '#556070']

export function ProjectionChart({ player }: Props) {
  const { p10, p25, median, p75, p90 } = player.projection
  const data = [
    { label: 'p10',    value: Math.round(p10) },
    { label: 'p25',    value: Math.round(p25) },
    { label: 'Median', value: Math.round(median) },
    { label: 'p75',    value: Math.round(p75) },
    { label: 'p90',    value: Math.round(p90) },
  ]

  return (
    <div>
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
        Projection Distribution
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: -20 }}>
          <XAxis
            dataKey="label"
            tick={{ fill: '#8B98A8', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#8B98A8', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{ background: '#1C2230', border: '1px solid #2D3748', borderRadius: 8 }}
            labelStyle={{ color: '#E8EDF5', fontSize: 12 }}
            itemStyle={{ color: '#60B4FF', fontSize: 12 }}
            formatter={(v: number) => [`${v} pts`, 'Projection']}
          />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={PERCENTILE_COLORS[i]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex justify-between mt-1">
        <div className="text-center">
          <div className="text-xs text-text-muted">Floor</div>
          <div className="text-sm font-medium text-text-primary">{Math.round(player.projection.floor)}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted">Boom%</div>
          <div className="text-sm font-medium text-text-primary">
            {Math.round(player.projection.boomProbability * 100)}%
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted">Bust%</div>
          <div className="text-sm font-medium text-text-primary">
            {Math.round(player.projection.bustProbability * 100)}%
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted">Ceiling</div>
          <div className="text-sm font-medium text-text-primary">{Math.round(player.projection.ceiling)}</div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `ui/src/components/players/ComparablePlayers.tsx`**

Finds 3 players at the same position with the closest VOR.

```typescript
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props {
  ranking: Ranking
  allRankings: Ranking[]
}

export function ComparablePlayers({ ranking, allRankings }: Props) {
  const comps = allRankings
    .filter(r =>
      r.player.id !== ranking.player.id &&
      r.player.position === ranking.player.position
    )
    .sort((a, b) => Math.abs(a.vor - ranking.vor) - Math.abs(b.vor - ranking.vor))
    .slice(0, 3)

  if (comps.length === 0) return null

  return (
    <div>
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
        Comparable Players
      </div>
      <div className="space-y-2">
        {comps.map(r => (
          <div key={r.player.id} className="flex items-center gap-2">
            <PositionBadge position={r.player.position} />
            <span className="text-sm text-text-primary flex-1 truncate">{r.player.name}</span>
            <span className="text-xs text-text-secondary">{r.player.team}</span>
            <span className="text-xs text-text-muted tabular-nums">VOR {r.vor.toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update `ui/src/components/players/index.ts`**

```typescript
export { PlayerSearch } from './PlayerSearch'
export { PlayerListRow } from './PlayerListRow'
export { ProjectionChart } from './ProjectionChart'
export { ComparablePlayers } from './ComparablePlayers'
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/players/
git commit -m "feat: add player projection chart (Recharts) and comparable players component"
```

---

### Task 8: Player Explorer page

**Files:**
- Modify: `ui/src/pages/Players.tsx` (replace stub entirely)

**Interfaces:**
- Consumes (from Tasks 6–7): `PlayerSearch`, `PlayerListRow`, `ProjectionChart`, `ComparablePlayers` from `'../components/players'`
- Consumes: `MOCK_RANKINGS` from `'../data'`, `PositionBadge` from `'../components/ui/Badge'`

- [ ] **Step 1: Replace `ui/src/pages/Players.tsx`**

```typescript
import { useState, useMemo } from 'react'
import { MOCK_RANKINGS } from '../data'
import type { Ranking } from '../types'
import { PlayerSearch, PlayerListRow, ProjectionChart, ComparablePlayers } from '../components/players'
import { PositionBadge } from '../components/ui/Badge'

export default function Players() {
  const [search, setSearch]     = useState('')
  const [position, setPosition] = useState('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_RANKINGS[0]?.player.id ?? null)

  const filtered = useMemo(() =>
    MOCK_RANKINGS.filter(r => {
      if (position !== 'ALL' && r.player.position !== position) return false
      if (search) {
        const q = search.toLowerCase()
        return r.player.name.toLowerCase().includes(q) ||
               r.player.team.toLowerCase().includes(q)
      }
      return true
    }),
    [search, position]
  )

  const selectedRanking: Ranking | undefined = useMemo(
    () => MOCK_RANKINGS.find(r => r.player.id === selectedId),
    [selectedId]
  )

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
          {filtered.map(r => (
            <PlayerListRow
              key={r.player.id}
              ranking={r}
              selected={r.player.id === selectedId}
              onClick={() => setSelectedId(r.player.id)}
            />
          ))}
          {filtered.length === 0 && (
            <p className="text-sm text-text-muted p-4 text-center">No players found</p>
          )}
        </div>
      </div>

      {/* Right: player detail */}
      {selectedRanking ? (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Header */}
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
                <span className="text-sm text-text-muted">· Bye {selectedRanking.player.byeWeek}</span>
                <span className="text-sm text-text-muted">· Age {selectedRanking.player.age}</span>
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

          {/* Projection distribution */}
          <div className="bg-bg-card border border-border rounded-xl p-4">
            <ProjectionChart player={selectedRanking.player} />
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Model Confidence', value: `${Math.round(selectedRanking.player.modelConfidence * 100)}%` },
              { label: 'Breakout Prob', value: `${Math.round(selectedRanking.player.breakoutProbability * 100)}%` },
              { label: 'Bust Risk', value: `${Math.round(selectedRanking.player.bustRisk * 100)}%` },
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

          {/* Comparable players */}
          <div className="bg-bg-card border border-border rounded-xl p-4">
            <ComparablePlayers ranking={selectedRanking} allRankings={MOCK_RANKINGS} />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
          Select a player
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/Players.tsx
git commit -m "feat: build Player Explorer with search, list, projection chart, and comparables"
```

---

### Task 9: Mock Draft auto-pick engine

**Files:**
- Create: `ui/src/state/mockDraftSimulator.ts`
- Modify: `ui/src/state/index.ts`

**Interfaces:**
- Consumes: `MOCK_RANKINGS` from `'../data'`, `PlayerDetail` from types
- Produces (consumed by Tasks 10–11):
  - `bestAvailablePlayer(draftedIds: string[]): PlayerDetail | null` — pure function, returns highest-VOR undrafted player
  - `useAutoAdvance(): { autoAdvancing: boolean; startAutoAdvance: () => void; stopAutoAdvance: () => void }` — React hook that auto-picks opponent players until `isUserTurn` is true

- [ ] **Step 1: Create `ui/src/state/mockDraftSimulator.ts`**

```typescript
import { useState, useEffect } from 'react'
import { MOCK_RANKINGS } from '../data'
import type { PlayerDetail } from '../types'
import { useDraftState } from '../hooks/useDraftState'

/** Pure function — returns the highest-VOR undrafted player. */
export function bestAvailablePlayer(draftedIds: string[]): PlayerDetail | null {
  const pick = MOCK_RANKINGS.find(r => !draftedIds.includes(r.player.id))
  return pick?.player ?? null
}

/**
 * Fires one auto-pick per render frame (via setTimeout) until isUserTurn is
 * true or the draft is complete. Calling startAutoAdvance() begins the loop;
 * it stops automatically when the user's turn arrives.
 */
export function useAutoAdvance() {
  const { state, draftPlayer, isUserTurn } = useDraftState()
  const [autoAdvancing, setAutoAdvancing] = useState(false)

  const isDraftComplete =
    state.currentOverallPick > state.config.teams * state.config.totalRounds

  useEffect(() => {
    if (!autoAdvancing) return
    if (isUserTurn || isDraftComplete) {
      setAutoAdvancing(false)
      return
    }
    const pick = bestAvailablePlayer(state.draftedPlayerIds)
    if (!pick) {
      setAutoAdvancing(false)
      return
    }
    // 150ms delay gives a visual "picks happening" feel
    const timer = setTimeout(() => draftPlayer(pick, false), 150)
    return () => clearTimeout(timer)
  }, [autoAdvancing, isUserTurn, isDraftComplete, state.draftedPlayerIds, draftPlayer])

  return {
    autoAdvancing,
    startAutoAdvance: () => setAutoAdvancing(true),
    stopAutoAdvance: () => setAutoAdvancing(false),
  }
}
```

- [ ] **Step 2: Add export to `ui/src/state/index.ts`**

Append:
```typescript
export { bestAvailablePlayer, useAutoAdvance } from './mockDraftSimulator'
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add ui/src/state/mockDraftSimulator.ts ui/src/state/index.ts
git commit -m "feat: add mock draft auto-pick engine and useAutoAdvance hook"
```

---

### Task 10: Mock Draft board + pre-draft config

**Files:**
- Create: `ui/src/components/mockdraft/DraftBoard.tsx`
- Create: `ui/src/components/mockdraft/PreDraftConfig.tsx`
- Create: `ui/src/components/mockdraft/index.ts`

**Interfaces:**
- Consumes: `useDraftState()` from `'../../hooks'`, `useAutoAdvance()` from `'../../state'`, `PositionBadge` from `'../ui/Badge'`, `DraftConfig` from types
- `DraftBoard` props: none (reads from `useDraftState()`)
- `PreDraftConfig` props: `{ onStart: (pickPosition: number) => void }`

- [ ] **Step 1: Create `ui/src/components/mockdraft/DraftBoard.tsx`**

Displays a rounds × pick-slots grid. The `overallPick` for round R, slot S is `(R-1)*teams + S`. Marks the user's pick slots with accent color. Each cell shows the last name of the picked player (if any).

```typescript
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
                      className={`px-1 py-1.5 text-center ${isUserSlot ? 'bg-accent-muted/30' : ''}`}
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
```

- [ ] **Step 2: Create `ui/src/components/mockdraft/PreDraftConfig.tsx`**

```typescript
import { useState } from 'react'
import clsx from 'clsx'

interface Props { onStart: (pickPosition: number) => void }

const PICK_POSITIONS = Array.from({ length: 12 }, (_, i) => i + 1)

export function PreDraftConfig({ onStart }: Props) {
  const [pickPos, setPickPos] = useState(6)

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 p-8">
      <div className="text-center">
        <h2 className="text-xl font-bold text-text-primary">Configure Mock Draft</h2>
        <p className="text-sm text-text-secondary mt-1">12-team PPR · 13 rounds</p>
      </div>

      <div>
        <div className="text-sm font-medium text-text-secondary mb-3 text-center">
          Your Draft Position
        </div>
        <div className="grid grid-cols-6 gap-2">
          {PICK_POSITIONS.map(n => (
            <button
              key={n}
              onClick={() => setPickPos(n)}
              className={clsx(
                'w-10 h-10 rounded-lg text-sm font-medium transition-colors',
                pickPos === n
                  ? 'bg-accent text-bg-primary'
                  : 'bg-bg-card border border-border text-text-secondary hover:text-text-primary hover:border-accent'
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={() => onStart(pickPos)}
        className="px-8 py-3 bg-accent text-bg-primary text-sm font-semibold rounded-lg hover:opacity-90 transition-opacity"
      >
        Start Mock Draft
      </button>
    </div>
  )
}
```

- [ ] **Step 3: Create `ui/src/components/mockdraft/index.ts`**

```typescript
export { DraftBoard } from './DraftBoard'
export { PreDraftConfig } from './PreDraftConfig'
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/mockdraft/
git commit -m "feat: add mock draft board (rounds × teams grid) and pre-draft config screen"
```

---

### Task 11: Mock Draft page assembly

**Files:**
- Modify: `ui/src/pages/MockDraft.tsx` (replace stub entirely)

**Interfaces:**
- Consumes (from Tasks 9–10): `DraftBoard`, `PreDraftConfig` from `'../components/mockdraft'`
- Consumes (from Plan B): `DraftProvider` from `'../state'`, `DraftContextBar`, `AvailablePlayers`, `RecommendationPanel` from `'../components/draft'`
- Consumes (from Task 9): `useAutoAdvance` from `'../state'`
- Consumes: `useDraftState` from `'../hooks'`

The page has two modes:
1. **Pre-draft config** — shown until user clicks "Start Mock Draft"
2. **Draft mode** — DraftContextBar + three-column layout (AvailablePlayers | RecommendationPanel | DraftBoard)

The `onStart` callback uses `updateConfig` to apply the selected pick position, then transitions to draft mode.

- [ ] **Step 1: Replace `ui/src/pages/MockDraft.tsx`**

```typescript
import { useState } from 'react'
import { DraftProvider } from '../state'
import { useDraftState } from '../hooks'
import { useAutoAdvance } from '../state'
import { DraftContextBar, AvailablePlayers, RecommendationPanel } from '../components/draft'
import { DraftBoard, PreDraftConfig } from '../components/mockdraft'

function MockDraftInner() {
  const [started, setStarted] = useState(false)
  const { updateConfig, state, isUserTurn } = useDraftState()
  const { autoAdvancing, startAutoAdvance, stopAutoAdvance } = useAutoAdvance()

  const isDraftComplete =
    state.currentOverallPick > state.config.teams * state.config.totalRounds

  function handleStart(pickPosition: number) {
    updateConfig({ userPickPosition: pickPosition })
    setStarted(true)
  }

  if (!started) {
    return <PreDraftConfig onStart={handleStart} />
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <DraftContextBar />

      {/* Auto-advance bar */}
      {!isDraftComplete && (
        <div className="flex items-center gap-3 px-4 py-2 bg-bg-secondary border-b border-border">
          {isUserTurn ? (
            <span className="text-sm text-accent font-medium animate-pulse">Your pick — select from the left panel</span>
          ) : autoAdvancing ? (
            <>
              <span className="text-sm text-text-secondary">Auto-picking opponents…</span>
              <button
                onClick={stopAutoAdvance}
                className="text-xs px-3 py-1 border border-border rounded hover:border-accent text-text-secondary hover:text-text-primary transition-colors"
              >
                Pause
              </button>
            </>
          ) : (
            <button
              onClick={startAutoAdvance}
              className="text-xs px-3 py-1 bg-accent-muted border border-accent/30 text-accent rounded hover:bg-accent hover:text-bg-primary transition-colors"
            >
              Simulate to my turn →
            </button>
          )}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <AvailablePlayers />
        <RecommendationPanel />
        {/* Draft board scrollable right panel */}
        <div className="w-96 border-l border-border bg-bg-secondary overflow-hidden flex flex-col">
          <div className="px-3 py-2 border-b border-border">
            <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Draft Board</span>
          </div>
          <div className="flex-1 overflow-auto p-2">
            <DraftBoard />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MockDraft() {
  return (
    <DraftProvider>
      <MockDraftInner />
    </DraftProvider>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/MockDraft.tsx
git commit -m "feat: assemble Mock Draft page with auto-pick, draft board, and pre-draft config"
```

---

### Task 12: Roster Analyzer components

**Files:**
- Create: `ui/src/components/roster/RosterBuilder.tsx`
- Create: `ui/src/components/roster/RosterProjection.tsx`
- Create: `ui/src/components/roster/PositionStrengthBars.tsx`
- Create: `ui/src/components/roster/index.ts`

**Interfaces:**
- Consumes: `MOCK_RANKINGS` from `'../../data'`, `PlayerDetail` from types, `PositionBadge` from `'../ui/Badge'`
- Produces (consumed by Task 13):
  - `RosterBuilder` props: `{ roster: PlayerDetail[], onAdd: (p: PlayerDetail) => void, onRemove: (id: string) => void }`
  - `RosterProjection` props: `{ roster: PlayerDetail[], rosterConfig: { QB:number, RB:number, WR:number, TE:number, FLEX:number, BENCH:number } }`
  - `PositionStrengthBars` props: `{ roster: PlayerDetail[], rosterConfig: { QB:number, RB:number, WR:number, TE:number } }`

Roster slot filling uses the same greedy algorithm as `MyRoster` in Plan B (fill QB→RB→WR→TE→FLEX→BENCH; FLEX accepts RB/WR/TE overflow).

- [ ] **Step 1: Create `ui/src/components/roster/RosterBuilder.tsx`**

```typescript
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
```

- [ ] **Step 2: Create `ui/src/components/roster/RosterProjection.tsx`**

Fills starter slots greedily (QB→RB→WR→TE→FLEX→BENCH) and sums projected points for starters.

```typescript
import type { PlayerDetail } from '../../types'

interface Config { QB: number; RB: number; WR: number; TE: number; FLEX: number; BENCH: number }
interface Props { roster: PlayerDetail[]; rosterConfig: Config }

const FLEX_ELIGIBLE: PlayerDetail['position'][] = ['RB', 'WR', 'TE']

function fillStarters(roster: PlayerDetail[], config: Config): PlayerDetail[] {
  const pool = [...roster]
  const starters: PlayerDetail[] = []
  const slots: Array<{ pos: PlayerDetail['position'] | 'FLEX', count: number }> = [
    { pos: 'QB', count: config.QB },
    { pos: 'RB', count: config.RB },
    { pos: 'WR', count: config.WR },
    { pos: 'TE', count: config.TE },
    { pos: 'FLEX', count: config.FLEX },
  ]
  for (const { pos, count } of slots) {
    for (let i = 0; i < count; i++) {
      const idx = pool.findIndex(p =>
        pos === 'FLEX' ? FLEX_ELIGIBLE.includes(p.position) : p.position === pos
      )
      if (idx === -1) break
      starters.push(pool.splice(idx, 1)[0])
    }
  }
  return starters
}

export function RosterProjection({ roster, rosterConfig }: Props) {
  const starters = fillStarters(roster, rosterConfig)
  const total = starters.reduce((s, p) => s + p.projection.mean, 0)
  const floor  = starters.reduce((s, p) => s + p.projection.floor, 0)
  const ceiling = starters.reduce((s, p) => s + p.projection.ceiling, 0)

  if (starters.length === 0) {
    return (
      <div className="text-sm text-text-muted text-center py-6">
        Add starters to see projections
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-3">
      {[
        { label: 'Projected', value: total.toFixed(0), color: 'text-text-primary' },
        { label: 'Floor',     value: floor.toFixed(0),  color: 'text-text-secondary' },
        { label: 'Ceiling',   value: ceiling.toFixed(0), color: 'text-accent' },
      ].map(({ label, value, color }) => (
        <div key={label} className="bg-bg-card border border-border rounded-lg p-3 text-center">
          <div className="text-xs text-text-muted mb-1">{label}</div>
          <div className={`text-2xl font-bold tabular-nums ${color}`}>{value}</div>
          <div className="text-xs text-text-muted">pts</div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Create `ui/src/components/roster/PositionStrengthBars.tsx`**

```typescript
import type { PlayerDetail } from '../../types'
import clsx from 'clsx'

interface Config { QB: number; RB: number; WR: number; TE: number }
interface Props { roster: PlayerDetail[]; rosterConfig: Config }

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

function strengthLabel(count: number, needed: number): { label: string; color: string } {
  if (count >= needed + 2) return { label: 'Elite',   color: 'text-green-400' }
  if (count >= needed + 1) return { label: 'Strong',  color: 'text-accent' }
  if (count >= needed)     return { label: 'Average', color: 'text-text-secondary' }
  return { label: 'Weak', color: 'text-yellow-400' }
}

export function PositionStrengthBars({ roster, rosterConfig }: Props) {
  return (
    <div className="space-y-3">
      {POSITIONS.map(pos => {
        const count  = roster.filter(p => p.position === pos).length
        const needed = rosterConfig[pos]
        const { label, color } = strengthLabel(count, needed)
        const pct = needed > 0 ? Math.min(100, Math.round((count / (needed + 2)) * 100)) : 0
        return (
          <div key={pos}>
            <div className="flex justify-between mb-1">
              <span className="text-xs text-text-secondary">{pos}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">{count}/{needed} starters</span>
                <span className={clsx('text-xs font-medium', color)}>{label}</span>
              </div>
            </div>
            <div className="h-1.5 bg-bg-elevated rounded-full">
              <div
                className="h-1.5 rounded-full bg-accent transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Create `ui/src/components/roster/index.ts`**

```typescript
export { RosterBuilder } from './RosterBuilder'
export { RosterProjection } from './RosterProjection'
export { PositionStrengthBars } from './PositionStrengthBars'
```

- [ ] **Step 5: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/roster/
git commit -m "feat: add roster analyzer components (builder, projection, position strength)"
```

---

### Task 13: Roster Analyzer page

**Files:**
- Modify: `ui/src/pages/RosterAnalyzer.tsx` (replace stub entirely)

**Interfaces:**
- Consumes (from Task 12): `RosterBuilder`, `RosterProjection`, `PositionStrengthBars` from `'../components/roster'`
- Consumes (from Task 4): `useLeagueSettings` from `'../hooks'`

The page maintains a `roster: PlayerDetail[]` in local state. Left column has the builder; right shows projection totals, position strength bars, and a "primary needs" callout.

- [ ] **Step 1: Replace `ui/src/pages/RosterAnalyzer.tsx`**

```typescript
import { useState } from 'react'
import type { PlayerDetail } from '../types'
import { RosterBuilder, RosterProjection, PositionStrengthBars } from '../components/roster'
import { useLeagueSettings } from '../hooks'

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

export default function RosterAnalyzer() {
  const [roster, setRoster] = useState<PlayerDetail[]>([])
  const { settings } = useLeagueSettings()
  const config = settings.rosterConfig

  function addPlayer(p: PlayerDetail) {
    setRoster(prev => prev.find(x => x.id === p.id) ? prev : [...prev, p])
  }

  function removePlayer(id: string) {
    setRoster(prev => prev.filter(p => p.id !== id))
  }

  // Primary need: first position where drafted count < required starters
  const primaryNeed = POSITIONS.find(pos => {
    const count = roster.filter(p => p.position === pos).length
    return count < config[pos]
  }) ?? null

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: roster builder */}
      <div className="w-80 flex-shrink-0 flex flex-col border-r border-border bg-bg-secondary overflow-hidden p-4 gap-4">
        <div>
          <h2 className="text-sm font-semibold text-text-primary mb-0.5">Build Your Roster</h2>
          <p className="text-xs text-text-secondary">
            {roster.length} players · {settings.teams}-team {settings.format.toUpperCase()}
          </p>
        </div>
        <RosterBuilder roster={roster} onAdd={addPlayer} onRemove={removePlayer} />
      </div>

      {/* Right: analysis */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Roster Analysis</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Starter projections based on your league settings
          </p>
        </div>

        {/* Projected totals */}
        <section>
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
            Starter Projections
          </h2>
          <RosterProjection roster={roster} rosterConfig={config} />
        </section>

        {/* Position strength */}
        <section>
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
            Positional Strength
          </h2>
          <div className="bg-bg-card border border-border rounded-xl p-4">
            <PositionStrengthBars roster={roster} rosterConfig={config} />
          </div>
        </section>

        {/* Primary need */}
        {primaryNeed && (
          <section>
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
              Primary Need
            </h2>
            <div className="bg-bg-card border border-accent/30 rounded-xl p-4">
              <div className="text-sm text-text-primary">
                You need more <span className="font-semibold text-accent">{primaryNeed}</span> — starter slot unfilled
              </div>
            </div>
          </section>
        )}

        {roster.length === 0 && (
          <div className="text-center text-text-muted text-sm pt-8">
            Add players from the left panel to begin analysis
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/RosterAnalyzer.tsx
git commit -m "feat: build Roster Analyzer page with projection totals, strength bars, and primary need"
```

---

## Self-Review

### 1. Spec Coverage

From design spec section 12 (React UI pages):

| Requirement | Covered |
|-------------|---------|
| Dashboard: team summary, model movers, best values, scarcity overview | ✅ Tasks 1–3 |
| Rankings: already built (Plan A) | — |
| Draft Assistant: already built (Plan B) | — |
| Mock Draft: draft board, user picks, auto-picks for other teams | ✅ Tasks 9–11 |
| Roster Analyzer: overall projections, floor/ceiling, positional strength bars | ✅ Tasks 12–13 |
| Player Explorer: searchable, projection distribution chart, comparables | ✅ Tasks 6–8 |
| Settings: league scoring, roster configuration | ✅ Tasks 4–5 |

All spec requirements for the remaining pages are covered.

### 2. Placeholder Scan

No TBDs, TODOs, or incomplete code blocks. All component code is complete.

### 3. Type Consistency

- `LeagueSettings.rosterConfig` matches the `RosterBuilder`/`RosterProjection`/`PositionStrengthBars` prop types exactly
- `Ranking` fields (`adpDelta`, `vor`, `projection`, `modelRank`, `player`) are used correctly throughout — `adpDelta = modelRank - adp` (negative = undervalued), confirmed against `mockRankings.ts`
- `PlayerDetail.projection` has `mean`, `median`, `floor`, `ceiling`, `p10`, `p25`, `p75`, `p90` — all used correctly in `ProjectionChart`
- `DraftProvider` → `useDraftState` → `useAutoAdvance` dependency chain is consistent with Plan B exports
- `bestAvailablePlayer` takes `draftedIds: string[]` and returns `PlayerDetail | null` — consistent with call sites in `useAutoAdvance`
