import type { PlayerDetail } from '../types'

const EMPTY_STATS = {
  projection: { mean: 0, median: 0, floor: 0, ceiling: 0, p10: 0, p25: 0, p75: 0, p90: 0, stdDev: 0, gamesPlayed: 17 },
  projectedStats: { targets: null, receptions: null, recYards: null, recTds: null, rushAttempts: null, rushYards: null, rushTds: null, passAttempts: null, completions: null, passYards: null, passTds: null, interceptions: null },
  opportunity: { targetShare: null, routeParticipation: null, snapShare: 0, rushShare: null, redZoneUsage: null, targets: null, carries: null },
  efficiency: { yardsPerRouteRun: null, epaPerPlay: null, successRate: null, explosivePlayRate: null, yardsPerCarry: null, yardsPerTarget: null, catchRate: null, completionPct: null, yardsPerAttempt: null },
}

const NFL_TEAMS = [
  ['ARI', 'Arizona Cardinals'], ['ATL', 'Atlanta Falcons'], ['BAL', 'Baltimore Ravens'],
  ['BUF', 'Buffalo Bills'], ['CAR', 'Carolina Panthers'], ['CHI', 'Chicago Bears'],
  ['CIN', 'Cincinnati Bengals'], ['CLE', 'Cleveland Browns'], ['DAL', 'Dallas Cowboys'],
  ['DEN', 'Denver Broncos'], ['DET', 'Detroit Lions'], ['GB', 'Green Bay Packers'],
  ['HOU', 'Houston Texans'], ['IND', 'Indianapolis Colts'], ['JAX', 'Jacksonville Jaguars'],
  ['KC', 'Kansas City Chiefs'], ['LV', 'Las Vegas Raiders'], ['LAC', 'Los Angeles Chargers'],
  ['LAR', 'Los Angeles Rams'], ['MIA', 'Miami Dolphins'], ['MIN', 'Minnesota Vikings'],
  ['NE', 'New England Patriots'], ['NO', 'New Orleans Saints'], ['NYG', 'New York Giants'],
  ['NYJ', 'New York Jets'], ['PHI', 'Philadelphia Eagles'], ['PIT', 'Pittsburgh Steelers'],
  ['SF', 'San Francisco 49ers'], ['SEA', 'Seattle Seahawks'], ['TB', 'Tampa Bay Buccaneers'],
  ['TEN', 'Tennessee Titans'], ['WAS', 'Washington Commanders'],
]

const KICKERS: Array<[string, string]> = [
  ['Justin Tucker', 'BAL'], ['Evan McPherson', 'CIN'], ['Tyler Bass', 'BUF'],
  ['Harrison Butker', 'KC'], ['Jake Elliott', 'PHI'], ['Younghoe Koo', 'ATL'],
  ['Jason Myers', 'SEA'], ['Matt Gay', 'IND'], ['Nick Folk', 'TEN'],
  ['Greg Zuerlein', 'NYJ'], ['Wil Lutz', 'DEN'], ['Cairo Santos', 'CHI'],
  ['Brandon Aubrey', 'DAL'], ['Chris Boswell', 'PIT'], ['Daniel Carlson', 'LV'],
  ['Dustin Hopkins', 'LAC'], ['Cade York', 'CLE'], ['Blake Grupe', 'NO'],
  ['Chad Ryland', 'NE'], ['Riley Patterson', 'JAX'], ['Graham Gano', 'NYG'],
  ['Austin Seibert', 'WAS'], ['Eddy Pineiro', 'CAR'], ['Matt Prater', 'ARI'],
  ['Jake Moody', 'SF'], ['Brayden Narveson', 'GB'], ['Ka\'imi Fairbairn', 'HOU'],
  ['Ryan Succop', 'TB'], ['Lucas Havrisik', 'LAR'], ['Tyler Goodson', 'MIA'],
  ['James Turner', 'MIN'], ['Rodrigo Blankenship', 'LAC'],
]

function makeId(prefix: string, name: string): string {
  return `static-${prefix}-${name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`
}

export const STATIC_DST_PLAYERS: PlayerDetail[] = NFL_TEAMS.map(([abbr, fullName]) => ({
  id: makeId('dst', abbr),
  name: `${fullName} D/ST`,
  position: 'DST',
  team: abbr,
  byeWeek: 0,
  age: 0,
  experience: 0,
  imageUrl: null,
  injuryStatus: null,
  injuryNote: null,
  rookieYear: false,
  collegeTeam: null,
  depthChartPosition: 1,
  ...EMPTY_STATS,
}))

export const STATIC_K_PLAYERS: PlayerDetail[] = KICKERS.map(([name, team]) => ({
  id: makeId('k', name),
  name,
  position: 'K',
  team,
  byeWeek: 0,
  age: 0,
  experience: 0,
  imageUrl: null,
  injuryStatus: null,
  injuryNote: null,
  rookieYear: false,
  collegeTeam: null,
  depthChartPosition: 1,
  ...EMPTY_STATS,
}))

export const STATIC_UNRANKED_PLAYERS: PlayerDetail[] = [
  ...STATIC_DST_PLAYERS,
  ...STATIC_K_PLAYERS,
]
