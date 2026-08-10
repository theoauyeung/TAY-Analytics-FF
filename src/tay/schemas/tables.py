"""SQL CREATE TABLE statements — single source of truth for the DuckDB schema."""

PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    gsis_id         VARCHAR PRIMARY KEY,
    name            VARCHAR NOT NULL,
    position        VARCHAR,
    team            VARCHAR,
    birth_date      DATE,
    draft_year      INTEGER,
    draft_round     INTEGER,
    draft_pick      INTEGER,
    college         VARCHAR,
    height          INTEGER,
    weight          INTEGER,
    -- Cross-source IDs
    sleeper_id      VARCHAR,
    espn_id         VARCHAR,
    pfr_id          VARCHAR,
    yahoo_id        VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp
)
"""

PLAY_BY_PLAY = """
CREATE TABLE IF NOT EXISTS play_by_play (
    play_id         VARCHAR,
    game_id         VARCHAR,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     VARCHAR,
    posteam         VARCHAR,
    defteam         VARCHAR,
    play_type       VARCHAR,
    yards_gained    DOUBLE,
    passer_id       VARCHAR,
    rusher_id       VARCHAR,
    receiver_id     VARCHAR,
    air_yards       DOUBLE,
    yards_after_catch DOUBLE,
    pass_attempt    INTEGER,
    rush_attempt    INTEGER,
    complete_pass   INTEGER,
    touchdown       INTEGER,
    interception    INTEGER,
    fumble          INTEGER,
    epa             DOUBLE,
    cpoe            DOUBLE,
    wpa             DOUBLE,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (game_id, play_id)
)
"""

PLAYER_SEASON_STATS = """
CREATE TABLE IF NOT EXISTS player_season_stats (
    gsis_id             VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    team                VARCHAR,
    games               INTEGER,
    -- Passing
    attempts            INTEGER DEFAULT 0,
    completions         INTEGER DEFAULT 0,
    pass_yards          DOUBLE DEFAULT 0,
    pass_tds            INTEGER DEFAULT 0,
    interceptions       INTEGER DEFAULT 0,
    -- Rushing
    carries             INTEGER DEFAULT 0,
    rush_yards          DOUBLE DEFAULT 0,
    rush_tds            INTEGER DEFAULT 0,
    -- Receiving
    targets             INTEGER DEFAULT 0,
    receptions          INTEGER DEFAULT 0,
    rec_yards           DOUBLE DEFAULT 0,
    rec_tds             INTEGER DEFAULT 0,
    -- Advanced
    air_yards           DOUBLE DEFAULT 0,
    yards_after_catch   DOUBLE DEFAULT 0,
    epa_per_play        DOUBLE,
    cpoe                DOUBLE,
    -- Fantasy points
    fantasy_points_ppr  DOUBLE DEFAULT 0,
    fantasy_points_hppr DOUBLE DEFAULT 0,
    fantasy_points_std  DOUBLE DEFAULT 0,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season)
)
"""

TEAM_SEASON_STATS = """
CREATE TABLE IF NOT EXISTS team_season_stats (
    team                VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    games               INTEGER,
    -- Volume
    total_plays         INTEGER DEFAULT 0,
    pass_attempts       INTEGER DEFAULT 0,
    rush_attempts       INTEGER DEFAULT 0,
    pass_rate           DOUBLE,
    -- Scoring
    total_tds           INTEGER DEFAULT 0,
    pass_tds            INTEGER DEFAULT 0,
    rush_tds            INTEGER DEFAULT 0,
    points_scored       DOUBLE DEFAULT 0,
    -- Efficiency
    team_epa            DOUBLE,
    pass_epa            DOUBLE,
    rush_epa            DOUBLE,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (team, season)
)
"""

ROSTERS = """
CREATE TABLE IF NOT EXISTS rosters (
    gsis_id         VARCHAR NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    team            VARCHAR,
    position        VARCHAR,
    depth_chart_pos INTEGER,
    status          VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season, week)
)
"""

DRAFT_PICKS = """
CREATE TABLE IF NOT EXISTS draft_picks (
    gsis_id         VARCHAR,
    season          INTEGER NOT NULL,
    round           INTEGER,
    pick            INTEGER,
    overall_pick    INTEGER,
    team            VARCHAR,
    position        VARCHAR,
    college         VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (season, overall_pick)
)
"""

COMBINE_DATA = """
CREATE TABLE IF NOT EXISTS combine_data (
    gsis_id         VARCHAR,
    pfr_id          VARCHAR,
    name            VARCHAR,
    season          INTEGER NOT NULL,
    position        VARCHAR,
    forty_yard      DOUBLE,
    vertical        DOUBLE,
    broad_jump      DOUBLE,
    cone            DOUBLE,
    shuttle         DOUBLE,
    bench_reps      INTEGER,
    height          INTEGER,
    weight          INTEGER,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (season, pfr_id)
)
"""

ADP = """
CREATE TABLE IF NOT EXISTS adp (
    gsis_id         VARCHAR,
    season          INTEGER NOT NULL,
    platform        VARCHAR NOT NULL,
    format          VARCHAR NOT NULL,
    adp             DOUBLE,
    rank            INTEGER,
    fetched_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (season, platform, format, gsis_id)
)
"""

PROJECTIONS = """
CREATE TABLE IF NOT EXISTS projections (
    gsis_id             VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    model_version       VARCHAR,
    mean_projection     DOUBLE,
    median_projection   DOUBLE,
    floor               DOUBLE,
    ceiling             DOUBLE,
    std_dev             DOUBLE,
    p10                 DOUBLE,
    p25                 DOUBLE,
    p50                 DOUBLE,
    p75                 DOUBLE,
    p90                 DOUBLE,
    boom_probability    DOUBLE,
    bust_probability    DOUBLE,
    vor                 DOUBLE,
    vor_rank            INTEGER,
    adp_delta           DOUBLE,
    tier                INTEGER,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season, model_version)
)
"""

DRAFT_SESSIONS = """
CREATE TABLE IF NOT EXISTS draft_sessions (
    session_id      VARCHAR PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    league_settings JSON,
    picks           JSON,
    completed       BOOLEAN DEFAULT FALSE
)
"""

ALL_TABLES = [
    PLAYERS, PLAY_BY_PLAY, PLAYER_SEASON_STATS, TEAM_SEASON_STATS,
    ROSTERS, DRAFT_PICKS, COMBINE_DATA, ADP, PROJECTIONS, DRAFT_SESSIONS,
]
