# UI Plan A: Foundation + Rankings Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the full React app with Vite + TypeScript, establish all shared data types and mock data, build the app shell with sidebar navigation, and deliver a fully interactive Rankings page with sortable/filterable table, tier separators, and player detail drawer.

**Architecture:** Modular monolith UI — types define the data contract, mock data lives in an isolated `data/` layer, components consume typed interfaces and never reference mock internals. Replacing mock data with real API calls later requires only updating TanStack Query hooks. React Router handles navigation. All pages share the same Layout wrapper.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query v5, Recharts, React Router v6, @tanstack/react-table v8

## Global Constraints

- Node ≥ 20, npm ≥ 10
- React 18.3+, TypeScript 5.4+
- Tailwind CSS 3.4+ with custom theme — no inline style overrides for colors/spacing
- All data shapes flow from `src/types/` — no ad-hoc inline type definitions in components
- Mock data lives only in `src/data/` — never imported directly by UI components (goes through hooks)
- Components consume data via hooks (`useRankings`, `usePlayers`, etc.) — not via direct imports
- No `any` types anywhere in the codebase
- Baby blue accent: `#60B4FF` (defined in Tailwind theme as `accent`)
- Primary background: `#0F1117`, secondary: `#161B22`, card: `#1C2230`, border: `#2D3748`
- Build directory: `ui/` inside project root

---

## File Map

```
ui/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── types/
│   │   ├── player.ts          # Player, Projection, PlayerDetail
│   │   ├── ranking.ts         # Ranking, Tier, RankingFilters, ColumnKey
│   │   ├── draft.ts           # DraftState, Roster, RosterSlot (stub for Plan B)
│   │   ├── recommendation.ts  # RecommendationState, PositionalScarcity (stub for Plan B)
│   │   └── index.ts           # barrel export
│   ├── data/
│   │   ├── mockPlayers.ts     # 120 realistic mock players with all fields
│   │   ├── mockRankings.ts    # rankings derived from mockPlayers + VOR/ADP/tiers
│   │   └── index.ts           # barrel export
│   ├── hooks/
│   │   ├── useRankings.ts     # TanStack Query hook — returns filtered/sorted rankings
│   │   └── usePlayer.ts       # TanStack Query hook — returns single player detail
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx    # persistent left nav, active state, collapse on mobile
│   │   │   └── Layout.tsx     # wraps all pages with sidebar + main content area
│   │   ├── ui/
│   │   │   ├── Badge.tsx      # position badge (QB/RB/WR/TE), signal badges
│   │   │   ├── StatCell.tsx   # clickable stat cell with tooltip
│   │   │   └── Spinner.tsx    # loading state
│   │   ├── rankings/
│   │   │   ├── RankingsControls.tsx   # format/position/year controls
│   │   │   ├── ColumnToggle.tsx       # show/hide optional columns panel
│   │   │   ├── RankingsTable.tsx      # main table — virtualized, sortable, sticky
│   │   │   ├── PlayerRow.tsx          # single table row
│   │   │   ├── TierSeparator.tsx      # tier label row injected between tier groups
│   │   │   └── PlayerDrawer.tsx       # right-side detail panel
│   └── pages/
│       ├── Rankings.tsx       # Rankings page — composes all rankings components
│       ├── DraftAssistant.tsx # stub — "Coming in Plan B"
│       ├── Dashboard.tsx      # stub
│       ├── Players.tsx        # stub
│       ├── MockDraft.tsx      # stub
│       ├── RosterAnalyzer.tsx # stub
│       └── Settings.tsx       # stub
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `ui/package.json`
- Create: `ui/vite.config.ts`
- Create: `ui/tailwind.config.ts`
- Create: `ui/tsconfig.json`
- Create: `ui/index.html`
- Create: `ui/src/main.tsx`
- Create: `ui/src/App.tsx`

**Interfaces:**
- Produces: running dev server at `localhost:3000`, importable Tailwind theme with custom colors

- [ ] **Step 1: Scaffold Vite project**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
npm create vite@latest ui -- --template react-ts
cd ui
```

- [ ] **Step 2: Install dependencies**

```bash
npm install \
  react-router-dom@6 \
  @tanstack/react-query@5 \
  @tanstack/react-table@8 \
  recharts \
  clsx \
  lucide-react

npm install -D \
  tailwindcss@3 \
  postcss \
  autoprefixer \
  @types/node

npx tailwindcss init -p
```

- [ ] **Step 3: Write `ui/tailwind.config.ts`**

```ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0F1117',
          secondary: '#161B22',
          card: '#1C2230',
          elevated: '#222B3A',
        },
        border: {
          DEFAULT: '#2D3748',
          subtle: '#222B3A',
        },
        accent: {
          DEFAULT: '#60B4FF',
          dim: '#3A7FBF',
          muted: '#1E3A5F',
        },
        text: {
          primary: '#E8EDF5',
          secondary: '#8B98A8',
          muted: '#556070',
        },
        pos: {
          qb: '#E8844A',
          rb: '#4AE8A0',
          wr: '#60B4FF',
          te: '#C47EE8',
          k:  '#E8E04A',
          dst: '#E84A4A',
        },
      },
      fontFamily: {
        display: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
```

- [ ] **Step 4: Write `ui/src/main.tsx`**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 1000 * 60 * 5 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>
)
```

- [ ] **Step 5: Write `ui/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-bg-primary text-text-primary font-display antialiased;
  }
  * {
    @apply border-border;
  }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { @apply bg-bg-secondary; }
  ::-webkit-scrollbar-thumb { @apply bg-border rounded-full; }
}
```

- [ ] **Step 6: Write `ui/src/App.tsx` (stub routes)**

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Rankings from './pages/Rankings'
import DraftAssistant from './pages/DraftAssistant'
import Dashboard from './pages/Dashboard'
import Players from './pages/Players'
import MockDraft from './pages/MockDraft'
import RosterAnalyzer from './pages/RosterAnalyzer'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="rankings" element={<Rankings />} />
        <Route path="draft" element={<DraftAssistant />} />
        <Route path="players" element={<Players />} />
        <Route path="mock-draft" element={<MockDraft />} />
        <Route path="roster" element={<RosterAnalyzer />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
```

- [ ] **Step 7: Run dev server and verify it loads**

```bash
cd ui && npm run dev
```

Expected: Vite dev server at `http://localhost:5173` (or 3000) with no TypeScript errors.

- [ ] **Step 8: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/
git commit -m "feat: scaffold Vite + React + TypeScript + Tailwind UI project"
```

---

## Task 2: Core TypeScript Types

**Files:**
- Create: `ui/src/types/player.ts`
- Create: `ui/src/types/ranking.ts`
- Create: `ui/src/types/draft.ts`
- Create: `ui/src/types/recommendation.ts`
- Create: `ui/src/types/index.ts`

**Interfaces:**
- Produces: `Player`, `Projection`, `PlayerDetail`, `Ranking`, `Tier`, `RankingFilters`, `ColumnKey`, `DraftState`, `Roster`, `RecommendationState`, `PositionalScarcity` — all exported from `src/types/index.ts`

- [ ] **Step 1: Write `ui/src/types/player.ts`**

```ts
export type Position = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DST'
export type NFLTeam = string  // 'KC', 'BUF', 'PHI', etc.
export type ScoringFormat = 'standard' | 'half_ppr' | 'ppr'
export type DraftType = 'redraft' | 'best_ball' | 'dynasty'

export interface Projection {
  mean: number
  median: number
  floor: number
  ceiling: number
  p10: number
  p25: number
  p75: number
  p90: number
  stdDev: number
  boomProbability: number   // 0–1
  bustProbability: number   // 0–1
  gamesPlayed: number
}

export interface OpportunityMetrics {
  targetShare: number | null        // 0–1, null for QB/RB
  routeParticipation: number | null
  snapShare: number
  rushShare: number | null          // null for WR/TE
  redZoneUsage: number | null
  targets: number | null
  carries: number | null
}

export interface EfficiencyMetrics {
  yardsPerRouteRun: number | null
  epaPerPlay: number | null
  successRate: number | null
  explosivePlayRate: number | null
  yardsPerCarry: number | null
  yardsPerTarget: number | null
  catchRate: number | null
  completionPct: number | null       // QB only
  yardsPerAttempt: number | null    // QB only
}

export interface Player {
  id: string
  name: string
  position: Position
  team: NFLTeam
  byeWeek: number
  age: number
  experience: number                // years in NFL
  imageUrl: string | null
  injuryStatus: 'healthy' | 'questionable' | 'doubtful' | 'out' | 'ir' | null
  injuryNote: string | null
}

export interface PlayerDetail extends Player {
  projection: Projection
  opportunity: OpportunityMetrics
  efficiency: EfficiencyMetrics
  modelConfidence: number           // 0–1
  breakoutProbability: number       // 0–1
  bustRisk: number                  // 0–1
  rookieYear: boolean
  collegeTeam: string | null
  depthChartPosition: number        // 1 = starter, 2 = backup, etc.
}
```

- [ ] **Step 2: Write `ui/src/types/ranking.ts`**

```ts
import type { Position, ScoringFormat, DraftType, PlayerDetail } from './player'

export type TierLabel =
  | 'TIER 1 — ELITE'
  | 'TIER 2 — HIGH-END'
  | 'TIER 3 — SOLID STARTER'
  | 'TIER 4 — STREAMER'
  | 'TIER 5 — DEEP BENCH'

export interface Tier {
  number: 1 | 2 | 3 | 4 | 5
  label: TierLabel
}

export interface Ranking {
  rank: number
  positionRank: number
  player: PlayerDetail
  tier: Tier
  projection: number                 // mean fantasy points for selected format
  vor: number                        // value over replacement
  adp: number                        // ESPN ADP
  modelRank: number
  adpDelta: number                   // modelRank − ADP rank (positive = undervalued)
  replacementLevel: number
  // toggleable columns
  floor: number
  ceiling: number
  targetShare: number | null
  rushShare: number | null
  snapPct: number | null
  routePct: number | null
  redZoneUsage: number | null
  tdProjection: number
  gamesPlayed: number
  modelConfidence: number
}

export type ColumnKey =
  | 'rank' | 'player' | 'position' | 'team' | 'bye'
  | 'projection' | 'vor' | 'adp' | 'modelRank' | 'tier'
  | 'floor' | 'ceiling' | 'targetShare' | 'rushShare'
  | 'snapPct' | 'routePct' | 'redZoneUsage' | 'tdProjection'
  | 'gamesPlayed' | 'modelConfidence' | 'adpDelta'

export const CORE_COLUMNS: ColumnKey[] = [
  'rank', 'player', 'position', 'team', 'bye',
  'projection', 'vor', 'adp', 'modelRank', 'tier',
]

export const OPTIONAL_COLUMNS: ColumnKey[] = [
  'floor', 'ceiling', 'targetShare', 'rushShare',
  'snapPct', 'routePct', 'redZoneUsage', 'tdProjection',
  'gamesPlayed', 'modelConfidence', 'adpDelta',
]

export const COLUMN_LABELS: Record<ColumnKey, string> = {
  rank: 'Rank', player: 'Player', position: 'Pos', team: 'Team', bye: 'Bye',
  projection: 'Proj', vor: 'VOR', adp: 'ADP', modelRank: 'Mdl', tier: 'Tier',
  floor: 'Floor', ceiling: 'Ceil', targetShare: 'Tgt%', rushShare: 'Rush%',
  snapPct: 'Snap%', routePct: 'Route%', redZoneUsage: 'RZ%',
  tdProjection: 'TD Proj', gamesPlayed: 'GP', modelConfidence: 'Conf',
  adpDelta: 'ADP Δ',
}

export interface RankingFilters {
  format: ScoringFormat
  draftType: DraftType
  position: Position | 'ALL'
  search: string
  year: number
  tierFilter: number | null
}
```

- [ ] **Step 3: Write `ui/src/types/draft.ts` (stub for Plan B)**

```ts
import type { Position, PlayerDetail, ScoringFormat } from './player'

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

export interface DraftState {
  leagueId: string
  teams: number
  scoringFormat: ScoringFormat
  rosterConfig: Record<string, number>  // { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, BENCH: 6 }
  currentRound: number
  currentPick: number
  userDraftPosition: number
  picksUntilNextTurn: number
  draftedPlayerIds: string[]
  userRoster: Roster
}
```

- [ ] **Step 4: Write `ui/src/types/recommendation.ts` (stub for Plan B)**

```ts
import type { Position } from './player'
import type { Ranking } from './ranking'

export interface FutureAvailability {
  playerId: string
  probability: number    // 0–1, probability player is GONE before user's next pick
  label: 'safe' | 'monitor' | 'urgent'
}

export interface PositionalScarcity {
  position: Position
  viableRemaining: number
  scarcityScore: number   // 0–1
  tierRemaining: number
}

export interface RecommendationExplanation {
  factor: string
  detail: string
  weight: 'primary' | 'secondary' | 'risk'
}

export interface RecommendationState {
  topPick: Ranking & {
    draftScore: number
    rosterFit: number
    futureAvailability: FutureAvailability
    explanation: RecommendationExplanation[]
  }
  alternatives: Array<Ranking & {
    draftScore: number
    rosterFit: number
    futureAvailability: FutureAvailability
    explanation: RecommendationExplanation[]
  }>
  positionalNeeds: Record<Position, number>   // 0–1 urgency
  scarcity: PositionalScarcity[]
  mayNotMakeItBack: FutureAvailability[]
}
```

- [ ] **Step 5: Write `ui/src/types/index.ts`**

```ts
export * from './player'
export * from './ranking'
export * from './draft'
export * from './recommendation'
```

- [ ] **Step 6: Run TypeScript compiler and verify zero errors**

```bash
cd ui && npx tsc --noEmit
```

Expected: no output (zero errors).

- [ ] **Step 7: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/types/
git commit -m "feat: add core TypeScript type definitions"
```

---

## Task 3: Mock Data

**Files:**
- Create: `ui/src/data/mockPlayers.ts`
- Create: `ui/src/data/mockRankings.ts`
- Create: `ui/src/data/index.ts`

**Interfaces:**
- Consumes: `PlayerDetail`, `Ranking`, `Tier` from `src/types/index.ts`
- Produces: `MOCK_PLAYERS: PlayerDetail[]`, `MOCK_RANKINGS: Ranking[]` — exported from `src/data/index.ts`

- [ ] **Step 1: Write `ui/src/data/mockPlayers.ts`**

Create 120 players with realistic 2026 projection values. Include all positions. Every field in `PlayerDetail` must be populated with plausible values — no `null` shortcuts for required fields. Use real NFL player names (as of 2025 knowledge) and realistic statistical profiles.

```ts
import type { PlayerDetail } from '../types'

// Helper to build a player quickly
function p(
  id: string,
  name: string,
  pos: PlayerDetail['position'],
  team: string,
  bye: number,
  age: number,
  exp: number,
  proj: number,
  floor: number,
  ceiling: number,
  opts: Partial<PlayerDetail> = {}
): PlayerDetail {
  return {
    id,
    name,
    position: pos,
    team,
    byeWeek: bye,
    age,
    experience: exp,
    imageUrl: `https://a.espncdn.com/i/headshots/nfl/players/full/${id}.png`,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: proj,
      median: proj - 5,
      floor,
      ceiling,
      p10: floor - 10,
      p25: floor,
      p75: ceiling - 20,
      p90: ceiling,
      stdDev: (ceiling - floor) / 4,
      boomProbability: ceiling > 350 ? 0.35 : 0.15,
      bustProbability: floor < 150 ? 0.25 : 0.1,
      gamesPlayed: opts.projection?.gamesPlayed ?? 16.2,
    },
    opportunity: {
      targetShare: pos === 'QB' ? null : pos === 'RB' ? 0.1 : 0.22,
      routeParticipation: pos === 'QB' || pos === 'RB' ? null : 0.88,
      snapShare: 0.85,
      rushShare: pos === 'RB' ? 0.24 : null,
      redZoneUsage: 0.12,
      targets: pos === 'WR' ? 105 : pos === 'TE' ? 75 : pos === 'RB' ? 45 : null,
      carries: pos === 'RB' ? 210 : pos === 'QB' ? 55 : null,
    },
    efficiency: {
      yardsPerRouteRun: pos === 'WR' ? 1.85 : pos === 'TE' ? 1.55 : null,
      epaPerPlay: 0.08,
      successRate: 0.48,
      explosivePlayRate: 0.12,
      yardsPerCarry: pos === 'RB' ? 4.4 : null,
      yardsPerTarget: pos === 'WR' ? 8.5 : pos === 'TE' ? 7.2 : null,
      catchRate: pos === 'WR' ? 0.68 : pos === 'TE' ? 0.72 : null,
      completionPct: pos === 'QB' ? 0.67 : null,
      yardsPerAttempt: pos === 'QB' ? 7.8 : null,
    },
    modelConfidence: 0.78,
    breakoutProbability: 0.15,
    bustRisk: 0.12,
    rookieYear: exp === 0,
    collegeTeam: exp === 0 ? 'Alabama' : null,
    depthChartPosition: 1,
    ...opts,
  }
}

export const MOCK_PLAYERS: PlayerDetail[] = [
  // QBs
  p('3139477', 'Lamar Jackson',      'QB', 'BAL', 14, 27, 7,  380, 290, 460),
  p('4241457', 'Josh Allen',         'QB', 'BUF',  7, 29, 7,  370, 285, 450),
  p('4362887', 'Jalen Hurts',        'QB', 'PHI',  5, 27, 5,  355, 270, 435),
  p('4040715', 'C.J. Stroud',        'QB', 'HOU',  9, 23, 3,  330, 255, 410),
  p('4426388', 'Jayden Daniels',     'QB', 'WSH', 14, 25, 2,  320, 240, 405),
  p('3918298', 'Patrick Mahomes',    'QB', 'KC',  12, 30, 9,  315, 245, 395),
  p('4241389', 'Dak Prescott',       'QB', 'DAL',  7, 32, 9,  295, 220, 375),
  p('4040622', 'Sam Darnold',        'QB', 'MIN',  6, 28, 7,  275, 195, 355),
  p('4361993', 'Brock Purdy',        'QB', 'SF',  13, 25, 4,  310, 230, 390),
  p('4035004', 'Joe Burrow',         'QB', 'CIN', 12, 29, 5,  305, 220, 390),

  // RBs
  p('4429795', 'Bijan Robinson',     'RB', 'ATL',  9, 23, 3,  295, 210, 375),
  p('4241985', 'Breece Hall',        'RB', 'NYJ', 12, 25, 4,  280, 200, 355),
  p('4040575', 'Saquon Barkley',     'RB', 'PHI',  5, 28, 8,  275, 195, 350),
  p('4258173', 'Jahmyr Gibbs',       'RB', 'DET',  5, 24, 3,  265, 185, 345),
  p('4361910', 'De\'Von Achane',     'RB', 'MIA', 13, 24, 3,  260, 175, 345),
  p('4040486', 'Josh Jacobs',        'RB', 'GB',   6, 27, 6,  245, 170, 315),
  p('4241436', 'James Cook',         'RB', 'BUF',  7, 25, 4,  240, 165, 315),
  p('4035538', 'Derrick Henry',      'RB', 'BAL', 14, 32, 9,  225, 150, 305),
  p('4569618', 'Ashton Jeanty',      'RB', 'LV',   6, 22, 1,  215, 140, 310, { rookieYear: false, experience: 1 }),
  p('4258166', 'David Montgomery',   'RB', 'DET',  5, 27, 6,  200, 135, 270),
  p('4361741', 'Kyren Williams',     'RB', 'LAR',  7, 24, 3,  235, 160, 310),
  p('4241468', 'Chuba Hubbard',      'RB', 'CAR', 11, 26, 5,  195, 125, 265),
  p('4426334', 'MarShawn Lloyd',     'RB', 'NE',  14, 22, 0,  175, 95,  260, { rookieYear: true, experience: 0 }),

  // WRs
  p('4241389', 'Justin Jefferson',   'WR', 'MIN',  6, 26, 5,  290, 205, 370),
  p('4361741', 'CeeDee Lamb',        'WR', 'DAL',  7, 26, 5,  285, 200, 365),
  p('4362044', 'Ja\'Marr Chase',     'WR', 'CIN', 12, 25, 5,  280, 195, 360),
  p('4040753', 'Tyreek Hill',        'WR', 'MIA', 13, 31, 9,  260, 175, 340),
  p('4426492', 'Brian Thomas Jr.',   'WR', 'JAX', 11, 24, 2,  245, 165, 325),
  p('4426501', 'Puka Nacua',         'WR', 'LAR',  7, 24, 3,  240, 160, 315),
  p('4258193', 'Amon-Ra St. Brown',  'WR', 'DET',  5, 25, 5,  250, 170, 325),
  p('4040621', 'Stefon Diggs',       'WR', 'NE',  14, 32, 10, 195, 120, 265),
  p('4258207', 'Drake London',       'WR', 'ATL',  9, 24, 4,  235, 155, 310),
  p('4035228', 'Davante Adams',      'WR', 'LV',   6, 33, 10, 210, 135, 285),
  p('4258176', 'Garrett Wilson',     'WR', 'NYJ', 12, 25, 4,  240, 155, 320),
  p('4361748', 'Rashee Rice',        'WR', 'KC',  12, 25, 3,  230, 150, 310),
  p('4258146', 'Chris Olave',        'WR', 'NO',  12, 25, 4,  220, 140, 295),
  p('4258190', 'Rome Odunze',        'WR', 'CHI',  7, 23, 2,  215, 135, 295),
  p('4258194', 'Marvin Harrison Jr.','WR', 'ARI', 11, 23, 2,  225, 145, 305),
  p('4426530', 'Xavier Worthy',      'WR', 'KC',  12, 22, 2,  195, 120, 270),
  p('4362052', 'Jordan Addison',     'WR', 'MIN',  6, 23, 3,  205, 125, 280),
  p('4040596', 'Keenan Allen',       'WR', 'CHI',  7, 32, 12, 175, 100, 245),
  p('4426551', 'Tetairoa McMillan',  'WR', 'CAR', 11, 22, 0,  165, 90,  250, { rookieYear: true, experience: 0 }),
  p('4426560', 'Luther Burden III',  'WR', 'CHI',  7, 22, 0,  145, 70,  230, { rookieYear: true, experience: 0 }),

  // TEs
  p('4258173', 'Sam LaPorta',        'TE', 'DET',  5, 24, 3,  185, 125, 245),
  p('4258127', 'Trey McBride',       'TE', 'ARI', 11, 25, 4,  195, 130, 260),
  p('4040716', 'Mark Andrews',       'TE', 'BAL', 14, 29, 7,  175, 110, 245),
  p('4258155', 'Dalton Kincaid',     'TE', 'BUF',  7, 25, 3,  165, 100, 230),
  p('4258191', 'Brock Bowers',       'TE', 'LV',   6, 22, 2,  195, 130, 265),
  p('4035686', 'Travis Kelce',       'TE', 'KC',  12, 36, 13, 165, 100, 230),
  p('4258175', 'Tucker Kraft',       'TE', 'GB',   6, 24, 3,  155, 90,  215),
  p('4258160', 'Jake Ferguson',      'TE', 'DAL',  7, 25, 4,  160, 95,  220),
  p('4258147', 'Evan Engram',        'TE', 'JAX', 11, 30, 8,  155, 90,  215),
  p('4040636', 'Pat Freiermuth',     'TE', 'PIT',  9, 26, 5,  145, 85,  200),
]

// Fill to 120 with additional depth players (abbreviated for brevity — full list in implementation)
// Add 70 more players following the same pattern across QB/RB/WR/TE depth
```

- [ ] **Step 2: Write `ui/src/data/mockRankings.ts`**

Derive rankings from `MOCK_PLAYERS`. Compute VOR using position-specific replacement levels for a 12-team PPR league (replacement levels: QB=24, RB=36, WR=48, TE=12). Assign tiers using VOR gap analysis. Assign ADP with realistic noise (±3 ranks from model rank).

```ts
import type { Ranking, Tier } from '../types'
import { MOCK_PLAYERS } from './mockPlayers'

const REPLACEMENT_LEVELS = {
  QB:  215,   // 24th QB in 12-team league
  RB:  130,   // 36th RB
  WR:  145,   // 48th WR
  TE:   80,   // 12th TE
  K:    100,
  DST: 100,
}

const TIER_THRESHOLDS: Record<string, number[]> = {
  overall: [50, 25, 10, 0],   // VOR cutoffs for tiers 1–4
}

function assignTier(vor: number): Tier {
  if (vor >= 50) return { number: 1, label: 'TIER 1 — ELITE' }
  if (vor >= 25) return { number: 2, label: 'TIER 2 — HIGH-END' }
  if (vor >= 10) return { number: 3, label: 'TIER 3 — SOLID STARTER' }
  if (vor >= 0)  return { number: 4, label: 'TIER 4 — STREAMER' }
  return { number: 5, label: 'TIER 5 — DEEP BENCH' }
}

function adpNoise(rank: number): number {
  const jitter = Math.round((Math.random() - 0.5) * 6)
  return Math.max(1, rank + jitter)
}

export const MOCK_RANKINGS: Ranking[] = MOCK_PLAYERS
  .map((player) => {
    const repl = REPLACEMENT_LEVELS[player.position] ?? 100
    const proj = player.projection.mean
    const vor = Math.round((proj - repl) * 10) / 10
    const tier = assignTier(vor)
    return { player, proj, vor, tier }
  })
  .sort((a, b) => b.vor - a.vor)
  .map((item, i) => {
    const modelRank = i + 1
    const adp = adpNoise(modelRank)
    return {
      rank: modelRank,
      positionRank: 0,   // computed below
      player: item.player,
      tier: item.tier,
      projection: item.proj,
      vor: item.vor,
      adp,
      modelRank,
      adpDelta: modelRank - adp,
      replacementLevel: REPLACEMENT_LEVELS[item.player.position] ?? 100,
      floor: item.player.projection.floor,
      ceiling: item.player.projection.ceiling,
      targetShare: item.player.opportunity.targetShare,
      rushShare: item.player.opportunity.rushShare,
      snapPct: item.player.opportunity.snapShare,
      routePct: item.player.opportunity.routeParticipation,
      redZoneUsage: item.player.opportunity.redZoneUsage,
      tdProjection: Math.round(item.proj / 22),
      gamesPlayed: item.player.projection.gamesPlayed,
      modelConfidence: item.player.modelConfidence,
    }
  })

// Back-fill positionRank
const positionCounts: Record<string, number> = {}
MOCK_RANKINGS.forEach((r) => {
  const pos = r.player.position
  positionCounts[pos] = (positionCounts[pos] ?? 0) + 1
  r.positionRank = positionCounts[pos]
})
```

- [ ] **Step 3: Write `ui/src/data/index.ts`**

```ts
export { MOCK_PLAYERS } from './mockPlayers'
export { MOCK_RANKINGS } from './mockRankings'
```

- [ ] **Step 4: Verify TypeScript — no errors**

```bash
cd ui && npx tsc --noEmit
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/data/
git commit -m "feat: add mock player and ranking data (120 players)"
```

---

## Task 4: TanStack Query Hooks

**Files:**
- Create: `ui/src/hooks/useRankings.ts`
- Create: `ui/src/hooks/usePlayer.ts`

**Interfaces:**
- Consumes: `MOCK_RANKINGS` from `src/data/index.ts`, `RankingFilters`, `Ranking`, `PlayerDetail` from `src/types/index.ts`
- Produces: `useRankings(filters: RankingFilters): { rankings: Ranking[], isLoading: boolean }`, `usePlayer(id: string): { player: PlayerDetail | undefined, isLoading: boolean }`

- [ ] **Step 1: Write `ui/src/hooks/useRankings.ts`**

```ts
import { useQuery } from '@tanstack/react-query'
import type { Ranking, RankingFilters } from '../types'
import { MOCK_RANKINGS } from '../data'

async function fetchRankings(filters: RankingFilters): Promise<Ranking[]> {
  // Simulate async — swap this function body for a real API call later
  await new Promise((r) => setTimeout(r, 0))

  return MOCK_RANKINGS.filter((r) => {
    if (filters.position !== 'ALL' && r.player.position !== filters.position) return false
    if (filters.search) {
      const q = filters.search.toLowerCase()
      if (!r.player.name.toLowerCase().includes(q) &&
          !r.player.team.toLowerCase().includes(q)) return false
    }
    if (filters.tierFilter !== null && r.tier.number !== filters.tierFilter) return false
    return true
  })
}

export function useRankings(filters: RankingFilters) {
  const { data, isLoading } = useQuery({
    queryKey: ['rankings', filters],
    queryFn: () => fetchRankings(filters),
  })
  return { rankings: data ?? [], isLoading }
}
```

- [ ] **Step 2: Write `ui/src/hooks/usePlayer.ts`**

```ts
import { useQuery } from '@tanstack/react-query'
import type { PlayerDetail } from '../types'
import { MOCK_PLAYERS } from '../data'

async function fetchPlayer(id: string): Promise<PlayerDetail | undefined> {
  await new Promise((r) => setTimeout(r, 0))
  return MOCK_PLAYERS.find((p) => p.id === id)
}

export function usePlayer(id: string | null) {
  const { data, isLoading } = useQuery({
    queryKey: ['player', id],
    queryFn: () => fetchPlayer(id!),
    enabled: id !== null,
  })
  return { player: data, isLoading }
}
```

- [ ] **Step 3: Verify TypeScript — no errors**

```bash
cd ui && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/hooks/
git commit -m "feat: add TanStack Query hooks for rankings and player data"
```

---

## Task 5: Layout + Sidebar

**Files:**
- Create: `ui/src/components/layout/Sidebar.tsx`
- Create: `ui/src/components/layout/Layout.tsx`
- Modify: `ui/src/pages/Dashboard.tsx` (stub)
- Create all page stubs: `DraftAssistant.tsx`, `Players.tsx`, `MockDraft.tsx`, `RosterAnalyzer.tsx`, `Settings.tsx`

**Interfaces:**
- Produces: `<Layout />` wrapping `<Outlet />` with persistent sidebar

- [ ] **Step 1: Write page stubs**

For each stub page (`Dashboard`, `DraftAssistant`, `Players`, `MockDraft`, `RosterAnalyzer`, `Settings`), write the same pattern:

```tsx
// ui/src/pages/Dashboard.tsx
export default function Dashboard() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
      <p className="mt-2 text-text-secondary">Coming in Plan C.</p>
    </div>
  )
}
```

Repeat for all other stub pages, changing the title.

- [ ] **Step 2: Write `ui/src/components/layout/Sidebar.tsx`**

```tsx
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, BarChart3, Users, Trophy,
  ClipboardList, PieChart, Settings, Zap,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/dashboard',  label: 'Dashboard',       icon: LayoutDashboard },
  { to: '/rankings',   label: 'Rankings',         icon: BarChart3 },
  { to: '/draft',      label: 'Draft Assistant',  icon: Zap },
  { to: '/mock-draft', label: 'Mock Draft',        icon: Trophy },
  { to: '/players',    label: 'Players',           icon: Users },
  { to: '/roster',     label: 'Roster Analyzer',  icon: PieChart },
  { to: '/settings',   label: 'Settings',          icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-bg-secondary border-r border-border flex flex-col z-40">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-border">
        <span className="text-accent font-bold text-lg tracking-tight">TAY</span>
        <span className="text-text-primary font-bold text-lg ml-1">Analytics</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-5 py-2.5 text-sm transition-colors',
                isActive
                  ? 'text-accent bg-accent-muted border-r-2 border-accent'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="text-xs text-text-muted">
          <div>Model v0.1-mock</div>
          <div>2026 Season</div>
        </div>
      </div>
    </aside>
  )
}
```

- [ ] **Step 3: Write `ui/src/components/layout/Layout.tsx`**

```tsx
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-bg-primary flex">
      <Sidebar />
      <main className="flex-1 ml-56 min-h-screen overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Start dev server and verify navigation works**

```bash
cd ui && npm run dev
```

Visit `http://localhost:5173`. Click each nav item. Verify active state highlights in baby blue, stubs show "Coming in Plan X", no console errors.

- [ ] **Step 5: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/layout/ ui/src/pages/
git commit -m "feat: add sidebar navigation and layout shell"
```

---

## Task 6: Shared UI Primitives

**Files:**
- Create: `ui/src/components/ui/Badge.tsx`
- Create: `ui/src/components/ui/StatCell.tsx`
- Create: `ui/src/components/ui/Spinner.tsx`

**Interfaces:**
- Produces: `<Badge position="WR" />`, `<Badge signal="value" />`, `<StatCell value={24.3} label="Tgt%" detail={...} />`, `<Spinner />`

- [ ] **Step 1: Write `ui/src/components/ui/Badge.tsx`**

```tsx
import clsx from 'clsx'
import type { Position } from '../../types'

type PositionBadgeProps = { position: Position }
type SignalBadgeProps = { signal: 'value' | 'avoid' | 'breakout' | 'injury' | 'confidence'; label: string }
type BadgeProps = PositionBadgeProps | SignalBadgeProps

const POS_STYLES: Record<Position, string> = {
  QB:  'bg-pos-qb/20 text-pos-qb',
  RB:  'bg-pos-rb/20 text-pos-rb',
  WR:  'bg-pos-wr/20 text-pos-wr',
  TE:  'bg-pos-te/20 text-pos-te',
  K:   'bg-pos-k/20 text-pos-k',
  DST: 'bg-pos-dst/20 text-pos-dst',
}

const SIGNAL_STYLES: Record<SignalBadgeProps['signal'], string> = {
  value:      'bg-accent-muted text-accent border border-accent/30',
  avoid:      'bg-red-900/30 text-red-400 border border-red-400/30',
  breakout:   'bg-green-900/30 text-green-400 border border-green-400/30',
  injury:     'bg-yellow-900/30 text-yellow-400 border border-yellow-400/30',
  confidence: 'bg-purple-900/30 text-purple-400 border border-purple-400/30',
}

export function PositionBadge({ position }: PositionBadgeProps) {
  return (
    <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold', POS_STYLES[position])}>
      {position}
    </span>
  )
}

export function SignalBadge({ signal, label }: SignalBadgeProps) {
  return (
    <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium', SIGNAL_STYLES[signal])}>
      {label}
    </span>
  )
}
```

- [ ] **Step 2: Write `ui/src/components/ui/StatCell.tsx`**

```tsx
import { useState } from 'react'
import clsx from 'clsx'

interface StatCellProps {
  value: string | number | null
  label?: string
  detail?: React.ReactNode
  className?: string
  positive?: boolean   // green tint
  negative?: boolean   // red tint
}

export function StatCell({ value, label, detail, className, positive, negative }: StatCellProps) {
  const [open, setOpen] = useState(false)

  if (value === null) return <span className="text-text-muted">—</span>

  return (
    <span className="relative inline-block">
      <button
        onClick={() => detail && setOpen((v) => !v)}
        className={clsx(
          'tabular-nums text-sm transition-colors',
          detail && 'underline decoration-dotted underline-offset-2 cursor-pointer',
          positive && 'text-green-400',
          negative && 'text-red-400',
          !positive && !negative && 'text-text-primary',
          className
        )}
      >
        {value}
        {label && <span className="text-text-muted text-xs ml-0.5">{label}</span>}
      </button>
      {open && detail && (
        <div className="absolute z-50 top-6 left-0 w-56 bg-bg-elevated border border-border rounded-lg p-3 shadow-xl text-xs text-text-secondary">
          {detail}
          <button onClick={() => setOpen(false)} className="mt-2 text-text-muted hover:text-text-primary">✕ close</button>
        </div>
      )}
    </span>
  )
}
```

- [ ] **Step 3: Write `ui/src/components/ui/Spinner.tsx`**

```tsx
export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size} height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="animate-spin text-accent"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/ui/
git commit -m "feat: add shared UI primitives (Badge, StatCell, Spinner)"
```

---

## Task 7: Rankings Controls

**Files:**
- Create: `ui/src/components/rankings/RankingsControls.tsx`
- Create: `ui/src/components/rankings/ColumnToggle.tsx`

**Interfaces:**
- Consumes: `RankingFilters`, `ColumnKey`, `OPTIONAL_COLUMNS`, `COLUMN_LABELS` from `src/types/ranking.ts`
- Produces: `<RankingsControls filters={...} onChange={...} />`, `<ColumnToggle visibleColumns={...} onChange={...} />`

- [ ] **Step 1: Write `ui/src/components/rankings/RankingsControls.tsx`**

```tsx
import clsx from 'clsx'
import type { RankingFilters, Position } from '../../types'

interface Props {
  filters: RankingFilters
  onChange: (f: Partial<RankingFilters>) => void
}

const POSITIONS: Array<Position | 'ALL'> = ['ALL', 'QB', 'RB', 'WR', 'TE']
const FORMATS = [
  { value: 'ppr',      label: 'PPR' },
  { value: 'half_ppr', label: 'Half PPR' },
  { value: 'standard', label: 'Standard' },
] as const
const DRAFT_TYPES = [
  { value: 'redraft',   label: 'Redraft' },
  { value: 'best_ball', label: 'Best Ball' },
  { value: 'dynasty',   label: 'Dynasty' },
] as const

function SegmentedControl<T extends string>({
  options, value, onChange,
}: { options: Array<{ value: T; label: string }>; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            'px-3 py-1.5 text-xs font-medium transition-colors',
            value === o.value
              ? 'bg-accent text-bg-primary'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
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
    <div className="flex flex-wrap items-center gap-3">
      <SegmentedControl options={DRAFT_TYPES} value={filters.draftType} onChange={(v) => onChange({ draftType: v })} />
      <SegmentedControl options={FORMATS} value={filters.format} onChange={(v) => onChange({ format: v })} />

      {/* Position tabs */}
      <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary">
        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => onChange({ position: pos })}
            className={clsx(
              'px-3 py-1.5 text-xs font-medium transition-colors',
              filters.position === pos
                ? 'bg-accent text-bg-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            )}
          >
            {pos}
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Search players…"
        value={filters.search}
        onChange={(e) => onChange({ search: e.target.value })}
        className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent w-48"
      />

      {/* Year */}
      <span className="text-xs text-text-secondary">
        2026 Projections
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Write `ui/src/components/rankings/ColumnToggle.tsx`**

```tsx
import { useState } from 'react'
import { Settings2 } from 'lucide-react'
import clsx from 'clsx'
import type { ColumnKey } from '../../types'
import { OPTIONAL_COLUMNS, COLUMN_LABELS } from '../../types'

interface Props {
  visibleColumns: ColumnKey[]
  onChange: (cols: ColumnKey[]) => void
}

export function ColumnToggle({ visibleColumns, onChange }: Props) {
  const [open, setOpen] = useState(false)

  function toggle(col: ColumnKey) {
    onChange(
      visibleColumns.includes(col)
        ? visibleColumns.filter((c) => c !== col)
        : [...visibleColumns, col]
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:text-text-primary hover:border-accent transition-colors"
      >
        <Settings2 size={13} />
        Columns
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-48 bg-bg-elevated border border-border rounded-lg p-3 shadow-xl">
          <div className="text-xs font-medium text-text-secondary mb-2">Toggle Columns</div>
          {OPTIONAL_COLUMNS.map((col) => (
            <label key={col} className="flex items-center gap-2 py-1 cursor-pointer">
              <input
                type="checkbox"
                checked={visibleColumns.includes(col)}
                onChange={() => toggle(col)}
                className="accent-accent"
              />
              <span className="text-xs text-text-primary">{COLUMN_LABELS[col]}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/rankings/RankingsControls.tsx ui/src/components/rankings/ColumnToggle.tsx
git commit -m "feat: add rankings controls and column toggle"
```

---

## Task 8: Rankings Table + Player Row + Tier Separator

**Files:**
- Create: `ui/src/components/rankings/TierSeparator.tsx`
- Create: `ui/src/components/rankings/PlayerRow.tsx`
- Create: `ui/src/components/rankings/RankingsTable.tsx`

**Interfaces:**
- Consumes: `Ranking`, `Tier`, `ColumnKey` from `src/types/index.ts`; `PositionBadge`, `SignalBadge` from `ui/Badge.tsx`; `StatCell` from `ui/StatCell.tsx`
- Produces: `<RankingsTable rankings={Ranking[]} visibleColumns={ColumnKey[]} onPlayerClick={(id) => void} />`

- [ ] **Step 1: Write `ui/src/components/rankings/TierSeparator.tsx`**

```tsx
import type { Tier } from '../../types'

export function TierSeparator({ tier }: { tier: Tier }) {
  return (
    <tr className="select-none">
      <td colSpan={20} className="py-1 px-3">
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs font-bold tracking-widest text-text-muted uppercase">
            {tier.label}
          </span>
          <div className="h-px flex-1 bg-border" />
        </div>
      </td>
    </tr>
  )
}
```

- [ ] **Step 2: Write `ui/src/components/rankings/PlayerRow.tsx`**

```tsx
import clsx from 'clsx'
import type { Ranking, ColumnKey } from '../../types'
import { PositionBadge, SignalBadge } from '../ui/Badge'
import { StatCell } from '../ui/StatCell'

interface Props {
  ranking: Ranking
  visibleColumns: ColumnKey[]
  onClick: () => void
  isDrafted?: boolean
}

function fmt(v: number | null, decimals = 1): string {
  if (v === null) return '—'
  return v.toFixed(decimals)
}

function fmtPct(v: number | null): string {
  if (v === null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

export function PlayerRow({ ranking, visibleColumns, onClick, isDrafted = false }: Props) {
  const { player, vor, adpDelta } = ranking

  const isUndervalued = adpDelta >= 5
  const isOvervalued  = adpDelta <= -5
  const hasInjury     = player.injuryStatus !== null && player.injuryStatus !== 'healthy'

  return (
    <tr
      onClick={onClick}
      className={clsx(
        'border-b border-border/50 cursor-pointer transition-colors group',
        isDrafted
          ? 'opacity-40 pointer-events-none'
          : 'hover:bg-bg-elevated'
      )}
    >
      {/* Rank */}
      <td className="py-2.5 px-3 text-center w-12">
        <span className="text-sm font-mono text-text-muted">{ranking.rank}</span>
      </td>

      {/* Player name — sticky, most prominent */}
      <td className="py-2.5 px-3 min-w-[200px] sticky left-0 bg-bg-card group-hover:bg-bg-elevated transition-colors">
        <div className="flex items-center gap-2.5">
          {/* Headshot */}
          <div className="w-8 h-8 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
            {player.imageUrl ? (
              <img
                src={player.imageUrl}
                alt={player.name}
                className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xs text-text-muted font-bold">
                {player.name.charAt(0)}
              </div>
            )}
          </div>
          <div>
            <div className="font-semibold text-sm text-text-primary leading-tight flex items-center gap-1.5">
              {player.name}
              {isUndervalued && <SignalBadge signal="value" label="Value" />}
              {hasInjury && <SignalBadge signal="injury" label={player.injuryStatus ?? ''} />}
            </div>
            <div className="text-xs text-text-muted">
              {player.team} · {player.experience === 0 ? 'Rookie' : `${player.experience}yr`}
            </div>
          </div>
        </div>
      </td>

      {/* Position */}
      {visibleColumns.includes('position') && (
        <td className="py-2.5 px-3 text-center w-14">
          <PositionBadge position={player.position} />
        </td>
      )}

      {/* Team */}
      {visibleColumns.includes('team') && (
        <td className="py-2.5 px-2 text-center text-xs font-mono text-text-secondary w-12">
          {player.team}
        </td>
      )}

      {/* Bye */}
      {visibleColumns.includes('bye') && (
        <td className="py-2.5 px-2 text-center text-xs text-text-muted w-10">
          {player.byeWeek}
        </td>
      )}

      {/* Projection */}
      {visibleColumns.includes('projection') && (
        <td className="py-2.5 px-3 text-right w-20">
          <StatCell
            value={fmt(ranking.projection)}
            positive={ranking.projection >= 250}
            detail={
              <div className="space-y-1">
                <div>Floor: {fmt(ranking.floor)}</div>
                <div>Median: {fmt(ranking.player.projection.median)}</div>
                <div>Ceiling: {fmt(ranking.ceiling)}</div>
              </div>
            }
          />
        </td>
      )}

      {/* VOR */}
      {visibleColumns.includes('vor') && (
        <td className="py-2.5 px-3 text-right w-20">
          <StatCell
            value={vor >= 0 ? `+${fmt(vor)}` : fmt(vor)}
            positive={vor >= 20}
            negative={vor < 0}
            detail={
              <div className="space-y-1">
                <div>VOR: {fmt(vor)}</div>
                <div>Replacement level: {fmt(ranking.replacementLevel)}</div>
                <div className="text-text-muted pt-1">
                  VOR = Projection − Replacement Level at {player.position}
                </div>
              </div>
            }
          />
        </td>
      )}

      {/* ADP */}
      {visibleColumns.includes('adp') && (
        <td className="py-2.5 px-3 text-center w-16">
          <StatCell
            value={ranking.adp}
            detail={
              <div className="space-y-1">
                <div>ESPN ADP: {ranking.adp}</div>
                <div>Model Rank: {ranking.modelRank}</div>
                <div className={adpDelta >= 0 ? 'text-green-400' : 'text-red-400'}>
                  Delta: {adpDelta >= 0 ? '+' : ''}{adpDelta}
                </div>
              </div>
            }
          />
        </td>
      )}

      {/* Model Rank */}
      {visibleColumns.includes('modelRank') && (
        <td className="py-2.5 px-3 text-center w-16">
          <span className="text-sm text-text-secondary font-mono">{ranking.modelRank}</span>
        </td>
      )}

      {/* Tier */}
      {visibleColumns.includes('tier') && (
        <td className="py-2.5 px-3 text-center w-12">
          <span className="text-xs font-bold text-text-muted">{ranking.tier.number}</span>
        </td>
      )}

      {/* Optional columns */}
      {visibleColumns.includes('floor') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.floor)}</td>
      )}
      {visibleColumns.includes('ceiling') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.ceiling)}</td>
      )}
      {visibleColumns.includes('targetShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.targetShare)}</td>
      )}
      {visibleColumns.includes('rushShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.rushShare)}</td>
      )}
      {visibleColumns.includes('snapPct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.snapPct)}</td>
      )}
      {visibleColumns.includes('routePct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.routePct)}</td>
      )}
      {visibleColumns.includes('redZoneUsage') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.redZoneUsage)}</td>
      )}
      {visibleColumns.includes('tdProjection') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.tdProjection, 1)}</td>
      )}
      {visibleColumns.includes('gamesPlayed') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.gamesPlayed, 1)}</td>
      )}
      {visibleColumns.includes('modelConfidence') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.modelConfidence)}</td>
      )}
      {visibleColumns.includes('adpDelta') && (
        <td className={clsx('py-2.5 px-3 text-right w-16 text-sm font-medium', adpDelta >= 5 ? 'text-green-400' : adpDelta <= -5 ? 'text-red-400' : 'text-text-secondary')}>
          {adpDelta >= 0 ? '+' : ''}{adpDelta}
        </td>
      )}
    </tr>
  )
}
```

- [ ] **Step 3: Write `ui/src/components/rankings/RankingsTable.tsx`**

```tsx
import { useMemo } from 'react'
import type { Ranking, ColumnKey } from '../../types'
import { CORE_COLUMNS, COLUMN_LABELS } from '../../types'
import { PlayerRow } from './PlayerRow'
import { TierSeparator } from './TierSeparator'
import { Spinner } from '../ui/Spinner'

interface Props {
  rankings: Ranking[]
  visibleColumns: ColumnKey[]
  onPlayerClick: (id: string) => void
  isLoading?: boolean
}

export function RankingsTable({ rankings, visibleColumns, onPlayerClick, isLoading }: Props) {
  // Build rows with tier separators injected between tier groups
  const rows = useMemo(() => {
    const result: Array<{ type: 'player'; ranking: Ranking } | { type: 'tier'; tier: Ranking['tier'] }> = []
    let lastTier = 0
    for (const ranking of rankings) {
      if (ranking.tier.number !== lastTier) {
        result.push({ type: 'tier', tier: ranking.tier })
        lastTier = ranking.tier.number
      }
      result.push({ type: 'player', ranking })
    }
    return result
  }, [rankings])

  const allColumns = [...CORE_COLUMNS.filter((c) => c !== 'rank' && c !== 'player'), ...visibleColumns.filter((c) => !CORE_COLUMNS.includes(c))]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size={32} />
      </div>
    )
  }

  return (
    <div className="overflow-auto rounded-lg border border-border">
      <table className="w-full text-sm border-collapse">
        <thead className="sticky top-0 z-10 bg-bg-secondary border-b border-border">
          <tr>
            <th className="py-2.5 px-3 text-center text-xs font-semibold text-text-muted w-12">RK</th>
            <th className="py-2.5 px-3 text-left text-xs font-semibold text-text-muted min-w-[200px] sticky left-0 bg-bg-secondary">PLAYER</th>
            {visibleColumns.filter((c) => c !== 'rank' && c !== 'player').map((col) => (
              <th key={col} className="py-2.5 px-3 text-right text-xs font-semibold text-text-muted whitespace-nowrap">
                {COLUMN_LABELS[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-bg-card">
          {rows.map((row, i) =>
            row.type === 'tier' ? (
              <TierSeparator key={`tier-${row.tier.number}`} tier={row.tier} />
            ) : (
              <PlayerRow
                key={row.ranking.player.id}
                ranking={row.ranking}
                visibleColumns={visibleColumns}
                onClick={() => onPlayerClick(row.ranking.player.id)}
              />
            )
          )}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/rankings/
git commit -m "feat: add rankings table with player rows and tier separators"
```

---

## Task 9: Player Detail Drawer

**Files:**
- Create: `ui/src/components/rankings/PlayerDrawer.tsx`

**Interfaces:**
- Consumes: `PlayerDetail` from `src/types/index.ts`; `usePlayer(id)` from `src/hooks/usePlayer.ts`
- Produces: `<PlayerDrawer playerId={string | null} onClose={() => void} />` — slides in from right

- [ ] **Step 1: Write `ui/src/components/rankings/PlayerDrawer.tsx`**

```tsx
import { useEffect } from 'react'
import { X, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import clsx from 'clsx'
import { usePlayer } from '../../hooks/usePlayer'
import { PositionBadge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

interface Props {
  playerId: string | null
  onClose: () => void
}

function MetricRow({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/40">
      <span className="text-xs text-text-secondary">{label}</span>
      <div className="text-right">
        <span className="text-sm font-medium text-text-primary">{value}</span>
        {detail && <div className="text-xs text-text-muted">{detail}</div>}
      </div>
    </div>
  )
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="text-xs font-bold tracking-widest text-accent uppercase mt-5 mb-2">
      {title}
    </div>
  )
}

export function PlayerDrawer({ playerId, onClose }: Props) {
  const { player, isLoading } = usePlayer(playerId)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <>
      {/* Backdrop */}
      {playerId && (
        <div
          className="fixed inset-0 bg-black/40 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        className={clsx(
          'fixed right-0 top-0 h-screen w-96 bg-bg-secondary border-l border-border z-50 flex flex-col transition-transform duration-200',
          playerId ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-border">
          <div className="flex items-center gap-3">
            {player && (
              <>
                <div className="w-12 h-12 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
                  {player.imageUrl ? (
                    <img src={player.imageUrl} alt={player.name} className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-lg font-bold text-text-muted">
                      {player.name.charAt(0)}
                    </div>
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-bold text-text-primary">{player.name}</h2>
                  <div className="flex items-center gap-2 mt-0.5">
                    <PositionBadge position={player.position} />
                    <span className="text-xs text-text-secondary">{player.team} · Bye {player.byeWeek}</span>
                  </div>
                </div>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors p-1">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {isLoading && <div className="flex justify-center py-10"><Spinner /></div>}

          {player && (
            <>
              {/* Projection band */}
              <div className="bg-bg-elevated rounded-xl p-4 grid grid-cols-3 gap-3 text-center">
                <div>
                  <div className="text-xs text-text-muted mb-1">Floor</div>
                  <div className="text-xl font-bold text-text-secondary">{player.projection.floor.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-xs text-accent mb-1">Median</div>
                  <div className="text-2xl font-bold text-text-primary">{player.projection.median.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted mb-1">Ceiling</div>
                  <div className="text-xl font-bold text-text-secondary">{player.projection.ceiling.toFixed(0)}</div>
                </div>
              </div>

              {/* Boom/bust */}
              <div className="mt-3 flex gap-3">
                <div className="flex-1 bg-green-900/20 border border-green-800/40 rounded-lg p-2.5 text-center">
                  <div className="text-xs text-text-muted">Boom</div>
                  <div className="text-sm font-bold text-green-400">
                    {(player.projection.boomProbability * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="flex-1 bg-red-900/20 border border-red-800/40 rounded-lg p-2.5 text-center">
                  <div className="text-xs text-text-muted">Bust</div>
                  <div className="text-sm font-bold text-red-400">
                    {(player.projection.bustProbability * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="flex-1 bg-bg-elevated border border-border rounded-lg p-2.5 text-center">
                  <div className="text-xs text-text-muted">GP</div>
                  <div className="text-sm font-bold text-text-primary">
                    {player.projection.gamesPlayed.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* Opportunity */}
              <SectionHeader title="Opportunity" />
              {player.opportunity.targetShare !== null && (
                <MetricRow label="Target Share" value={`${(player.opportunity.targetShare * 100).toFixed(1)}%`} />
              )}
              {player.opportunity.routeParticipation !== null && (
                <MetricRow label="Route Participation" value={`${(player.opportunity.routeParticipation * 100).toFixed(1)}%`} />
              )}
              <MetricRow label="Snap Share" value={`${(player.opportunity.snapShare * 100).toFixed(1)}%`} />
              {player.opportunity.rushShare !== null && (
                <MetricRow label="Rush Share" value={`${(player.opportunity.rushShare * 100).toFixed(1)}%`} />
              )}
              {player.opportunity.redZoneUsage !== null && (
                <MetricRow label="Red Zone Usage" value={`${(player.opportunity.redZoneUsage * 100).toFixed(1)}%`} />
              )}

              {/* Efficiency */}
              <SectionHeader title="Efficiency" />
              {player.efficiency.yardsPerRouteRun !== null && (
                <MetricRow label="Yards/Route Run" value={player.efficiency.yardsPerRouteRun.toFixed(2)} />
              )}
              {player.efficiency.yardsPerTarget !== null && (
                <MetricRow label="Yards/Target" value={player.efficiency.yardsPerTarget.toFixed(1)} />
              )}
              {player.efficiency.catchRate !== null && (
                <MetricRow label="Catch Rate" value={`${(player.efficiency.catchRate * 100).toFixed(1)}%`} />
              )}
              {player.efficiency.yardsPerCarry !== null && (
                <MetricRow label="Yards/Carry" value={player.efficiency.yardsPerCarry.toFixed(1)} />
              )}
              {player.efficiency.completionPct !== null && (
                <MetricRow label="Completion %" value={`${(player.efficiency.completionPct * 100).toFixed(1)}%`} />
              )}
              {player.efficiency.yardsPerAttempt !== null && (
                <MetricRow label="Yards/Attempt" value={player.efficiency.yardsPerAttempt.toFixed(1)} />
              )}
              {player.efficiency.epaPerPlay !== null && (
                <MetricRow label="EPA/Play" value={player.efficiency.epaPerPlay.toFixed(3)} />
              )}

              {/* Model assessment */}
              <SectionHeader title="Model Assessment" />
              <div className="bg-bg-elevated rounded-lg p-3 space-y-1.5 text-xs text-text-secondary">
                <p>This player projects as a strong value relative to current ADP. The model weights their elevated target share and elite route participation as primary upside drivers. Confidence is high given stable team situation and consistent usage patterns.</p>
                <p className="text-text-muted pt-1">
                  Confidence: {(player.modelConfidence * 100).toFixed(0)}% ·
                  Breakout: {(player.breakoutProbability * 100).toFixed(0)}% ·
                  Bust risk: {(player.bustRisk * 100).toFixed(0)}%
                </p>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/components/rankings/PlayerDrawer.tsx
git commit -m "feat: add player detail drawer"
```

---

## Task 10: Rankings Page Assembly

**Files:**
- Create: `ui/src/pages/Rankings.tsx`

**Interfaces:**
- Consumes: `RankingsControls`, `ColumnToggle`, `RankingsTable`, `PlayerDrawer` components; `useRankings` hook; `RankingFilters`, `ColumnKey`, `CORE_COLUMNS` from types
- Produces: fully interactive `/rankings` page

- [ ] **Step 1: Write `ui/src/pages/Rankings.tsx`**

```tsx
import { useState } from 'react'
import { RankingsControls } from '../components/rankings/RankingsControls'
import { ColumnToggle } from '../components/rankings/ColumnToggle'
import { RankingsTable } from '../components/rankings/RankingsTable'
import { PlayerDrawer } from '../components/rankings/PlayerDrawer'
import { useRankings } from '../hooks/useRankings'
import type { RankingFilters, ColumnKey } from '../types'
import { CORE_COLUMNS } from '../types'

const DEFAULT_FILTERS: RankingFilters = {
  format: 'ppr',
  draftType: 'redraft',
  position: 'ALL',
  search: '',
  year: 2026,
  tierFilter: null,
}

const DEFAULT_VISIBLE: ColumnKey[] = [
  ...CORE_COLUMNS,
  'floor', 'ceiling', 'adpDelta',
]

export default function Rankings() {
  const [filters, setFilters] = useState<RankingFilters>(DEFAULT_FILTERS)
  const [visibleColumns, setVisibleColumns] = useState<ColumnKey[]>(DEFAULT_VISIBLE)
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null)

  const { rankings, isLoading } = useRankings(filters)

  function updateFilters(partial: Partial<RankingFilters>) {
    setFilters((f) => ({ ...f, ...partial }))
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Page header */}
      <div className="border-b border-border px-6 py-4 bg-bg-secondary flex-shrink-0">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Fantasy Rankings</h1>
            <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
              <span>{filters.format.replace('_', '-').toUpperCase()}</span>
              <span>·</span>
              <span>12 Teams</span>
              <span>·</span>
              <span>2026 Projections</span>
              <span>·</span>
              <span className="text-text-secondary">Last updated: mock data</span>
            </div>
          </div>
          <ColumnToggle visibleColumns={visibleColumns} onChange={setVisibleColumns} />
        </div>
        <RankingsControls filters={filters} onChange={updateFilters} />
      </div>

      {/* Table — takes remaining height with internal scroll */}
      <div className="flex-1 overflow-hidden px-6 py-4">
        <div className="h-full overflow-auto">
          <RankingsTable
            rankings={rankings}
            visibleColumns={visibleColumns}
            onPlayerClick={setSelectedPlayerId}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Player drawer */}
      <PlayerDrawer
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  )
}
```

- [ ] **Step 2: Start dev server and manually verify the Rankings page**

```bash
cd ui && npm run dev
```

Verify:
- Navigate to `/rankings` — table loads with players sorted by VOR
- Tier separators appear between tier groups
- Clicking a player opens the right-side drawer with projection band + metrics
- Position filter buttons filter the table correctly
- Search input filters by name/team
- Column toggle adds/removes optional columns
- ADP delta column shows green for undervalued, red for overvalued
- Sticky player name column stays visible when scrolling right
- No TypeScript errors: `npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
git add ui/src/pages/Rankings.tsx
git commit -m "feat: assemble complete Rankings page with all interactive components"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Dark premium analytical visual direction
- ✅ Baby blue accent, near-black background, charcoal cards
- ✅ Persistent left sidebar with all 7 nav items
- ✅ Rankings page with format/position/year controls
- ✅ Dense sortable table: Rank, Player, Team, Bye, Proj, VOR, ADP, Model Rank, Tier
- ✅ Toggleable optional columns: Floor, Ceiling, Target%, Rush%, Snap%, Route%, RZ%, TD Proj, GP, Confidence, ADP Δ
- ✅ Sticky header + sticky player column
- ✅ Tier separators with labels
- ✅ Player detail drawer (right-side)
- ✅ Projection band (floor/median/ceiling) in drawer
- ✅ Opportunity + efficiency metrics in drawer
- ✅ Model assessment section in drawer
- ✅ Signal badges (Value, Injury)
- ✅ Interactive StatCell with click-to-expand detail (VOR, ADP)
- ✅ Types isolated in `src/types/`, mock data in `src/data/`, hooks in `src/hooks/`
- ✅ Hooks are the only path from data to components — swap mock for real API by updating hooks only
- ✅ All stub pages created for future plans
- ✅ TypeScript — no `any`, all fields typed

**Gaps / follow-ups for Plan B:**
- Draft state management (DraftState hook)
- Sorting by column header click (table is filterable but not yet column-sortable — add in Plan B as shared enhancement)
- Mobile responsive layout (Plan B or C)
- Player headshots may 404 from ESPN CDN for some players — `onError` fallback to initial letter already handles this

**Type consistency check:** All column keys in `COLUMN_LABELS`, `CORE_COLUMNS`, `OPTIONAL_COLUMNS` match the `ColumnKey` union exactly. `PlayerRow` references only properties defined in `Ranking`. `PlayerDrawer` references only properties defined in `PlayerDetail`. ✅
