import { API_BASE as API } from './client'

export interface UndervaluedPlayer {
  name: string
  position: string
  team: string
  efficiency_factor: number
  adp_bucket: string
  avg_pts_above: number
  sample_size: number
  adp: number
}

export interface BucketStat {
  bucket: string
  position: string
  avg_factor: number
  sample_size: number
}

export interface DraftValueData {
  undervalued: UndervaluedPlayer[]
  bucket_stats: BucketStat[]
}

export async function fetchDraftValue(season = 2026): Promise<DraftValueData> {
  const res = await fetch(`${API}/analytics/draft-value?season=${season}`)
  if (!res.ok) throw new Error('Failed to fetch draft value data')
  return res.json()
}
