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
