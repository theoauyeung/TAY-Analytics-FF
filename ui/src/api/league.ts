import type { LeagueSettings, ScoringFormat } from '../types'
import { DEFAULT_LEAGUE_SETTINGS } from '../types'
import { apiFetch } from './client'

interface BackendLeagueSettings {
  teams: number
  scoring: string
  roster_config: Record<string, number>
}

function fromBackend(s: BackendLeagueSettings): LeagueSettings {
  return {
    teams: s.teams,
    format: (s.scoring === 'half' ? 'half_ppr' : s.scoring) as ScoringFormat,
    rosterConfig: {
      QB: s.roster_config['QB'] ?? 1,
      RB: s.roster_config['RB'] ?? 2,
      WR: s.roster_config['WR'] ?? 2,
      TE: s.roster_config['TE'] ?? 1,
      FLEX: s.roster_config['FLEX'] ?? 1,
      BENCH: DEFAULT_LEAGUE_SETTINGS.rosterConfig.BENCH,
    },
  }
}

function toBackend(s: LeagueSettings): BackendLeagueSettings {
  return {
    teams: s.teams,
    scoring: s.format === 'half_ppr' ? 'half' : s.format,
    roster_config: {
      QB: s.rosterConfig.QB,
      RB: s.rosterConfig.RB,
      WR: s.rosterConfig.WR,
      TE: s.rosterConfig.TE,
      FLEX: s.rosterConfig.FLEX,
    },
  }
}

export async function fetchLeagueSettings(): Promise<LeagueSettings> {
  return apiFetch<BackendLeagueSettings>('/league/settings').then(fromBackend)
}

export async function saveLeagueSettings(settings: LeagueSettings): Promise<void> {
  await apiFetch('/league/settings', {
    method: 'POST',
    body: JSON.stringify(toBackend(settings)),
  })
}
