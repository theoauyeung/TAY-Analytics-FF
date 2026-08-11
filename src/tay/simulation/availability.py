"""Compute player availability (games played) distribution from historical data."""
from __future__ import annotations
import duckdb

POSITION_PRIORS: dict[str, tuple[float, float]] = {
    'QB': (14.0, 3.5),
    'RB': (13.0, 4.0),
    'WR': (13.5, 3.5),
    'TE': (13.0, 4.0),
}


def _season_games(season: int) -> int:
    """Return the number of games in a given NFL season (16 pre-2021, 17 from 2021+)."""
    return 16 if season <= 2020 else 17


def compute_availability(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
) -> dict[str, tuple[float, float]]:
    """Return {gsis_id: (avail_mean, avail_std)} for all players in projections.

    avail_mean and avail_std are in 17-game-season units.
    Uses Bayesian shrinkage: blends up to 3 prior seasons with position prior.
    """
    players = conn.execute("""
        SELECT pr.gsis_id, p.position
        FROM projections pr
        JOIN players p ON pr.gsis_id = p.gsis_id
        WHERE pr.season = ? AND pr.model_version = ?
    """, [season, model_version]).fetchall()

    result: dict[str, tuple[float, float]] = {}

    for gsis_id, position in players:
        prior_mean, prior_std = POSITION_PRIORS.get(position, (13.0, 4.0))

        # Fetch up to 3 most recent prior seasons of games played
        rows = conn.execute("""
            SELECT season, games FROM player_season_stats
            WHERE gsis_id = ? AND season < ? AND games IS NOT NULL AND games > 0
            ORDER BY season DESC
            LIMIT 3
        """, [gsis_id, season]).fetchall()

        # Normalize to 17-game scale (rows ordered most-recent first)
        games_17 = [g * (17 / _season_games(s)) for s, g in rows]
        n = len(games_17)

        # Recency-weighted mean: most recent season carries 0.6 weight so a
        # player who was healthy last year isn't dragged down by old injuries.
        _recency = [0.6, 0.3, 0.1]
        if n > 0:
            w = _recency[:n]
            w_sum = sum(w)
            player_mean = sum(wi * gi for wi, gi in zip(w, games_17)) / w_sum
        else:
            player_mean = 0.0
        if n >= 2:
            variance = sum((x - player_mean) ** 2 for x in games_17) / n
            player_std = variance ** 0.5
        else:
            player_std = prior_std  # not enough data: use prior

        weight = n / (n + 2)
        blended_mean = weight * player_mean + (1 - weight) * prior_mean
        blended_std = weight * player_std + (1 - weight) * prior_std

        result[gsis_id] = (blended_mean, blended_std)

    return result
