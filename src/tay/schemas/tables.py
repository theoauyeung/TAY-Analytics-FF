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

PLAYER_FEATURES = """
CREATE TABLE IF NOT EXISTS player_features (
    gsis_id                 VARCHAR NOT NULL,
    season                  INTEGER NOT NULL,
    position                VARCHAR,
    age                     DOUBLE,
    experience              INTEGER,

    -- Prior season raw stats (season N-1)
    prev_games              INTEGER,
    prev_targets            INTEGER,
    prev_receptions         INTEGER,
    prev_rec_yards          DOUBLE,
    prev_rec_tds            INTEGER,
    prev_air_yards          DOUBLE,
    prev_yac                DOUBLE,
    prev_carries            INTEGER,
    prev_rush_yards         DOUBLE,
    prev_rush_tds           INTEGER,
    prev_attempts           INTEGER,
    prev_completions        INTEGER,
    prev_pass_yards         DOUBLE,
    prev_pass_tds           INTEGER,
    prev_interceptions      INTEGER,
    prev_fantasy_ppr        DOUBLE,

    -- Per-game efficiency (season N-1, only when games > 0)
    targets_per_game        DOUBLE,
    catches_per_game        DOUBLE,
    rec_yards_per_game      DOUBLE,
    rec_tds_per_game        DOUBLE,
    carries_per_game        DOUBLE,
    rush_yards_per_game     DOUBLE,

    -- Rate stats (season N-1)
    catch_rate              DOUBLE,   -- receptions / targets
    yards_per_target        DOUBLE,   -- rec_yards / targets
    yards_per_carry         DOUBLE,   -- rush_yards / carries
    air_yards_per_target    DOUBLE,   -- air_yards / targets
    yac_per_reception       DOUBLE,   -- yac / receptions
    pass_completion_pct     DOUBLE,   -- completions / attempts
    pass_yards_per_attempt  DOUBLE,   -- pass_yards / attempts
    td_rate_receiving       DOUBLE,   -- rec_tds / targets
    td_rate_rushing         DOUBLE,   -- rush_tds / carries

    -- Advanced (season N-1)
    prev_epa_per_play       DOUBLE,
    prev_cpoe               DOUBLE,

    -- 2-year rolling averages (seasons N-2 and N-1)
    roll2_fantasy_ppr       DOUBLE,
    roll2_targets           DOUBLE,
    roll2_carries           DOUBLE,

    -- Season N-2 raw stats
    lag2_fantasy_ppr        DOUBLE,
    lag2_targets            INTEGER,
    lag2_carries            INTEGER,
    lag2_pass_yards         DOUBLE,

    -- Season N-3 raw stats
    lag3_fantasy_ppr        DOUBLE,
    lag3_targets            INTEGER,
    lag3_carries            INTEGER,
    lag3_pass_yards         DOUBLE,

    -- EWMA (0.6 × N-1  +  0.3 × N-2  +  0.1 × N-3)
    ewma_fantasy_ppr        DOUBLE,
    ewma_targets            DOUBLE,
    ewma_carries            DOUBLE,
    ewma_pass_yards         DOUBLE,

    -- Team context (season N-1 team environment)
    team                    VARCHAR,
    team_pass_rate          DOUBLE,
    team_pass_epa           DOUBLE,
    team_total_plays        INTEGER,

    -- Vacated opportunity coming into season N
    -- (opportunity from players who left this team after season N-1)
    incoming_vacated_targets   DOUBLE,
    incoming_vacated_carries   DOUBLE,

    -- Roster depth (from weekly rosters, season N-1 week 1)
    depth_chart_pos         INTEGER,

    -- Rookie / draft context (NULL for veterans)
    is_rookie               INTEGER,   -- 1 if first NFL season
    draft_round             INTEGER,
    draft_pick              INTEGER,
    draft_pick_value        DOUBLE,    -- 1/(overall_pick^0.5), 0 for undrafted
    combine_forty           DOUBLE,
    combine_vertical        DOUBLE,

    -- Target variable (what we're predicting — season N)
    next_season_fantasy_ppr DOUBLE,
    next_season_games       INTEGER,

    created_at              TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season)
)
"""

TEAM_FEATURES = """
CREATE TABLE IF NOT EXISTS team_features (
    team                    VARCHAR NOT NULL,
    season                  INTEGER NOT NULL,

    -- Season N-1 environment
    pass_rate               DOUBLE,
    rush_rate               DOUBLE,
    team_epa                DOUBLE,
    pass_epa                DOUBLE,
    rush_epa                DOUBLE,
    total_plays             INTEGER,
    pass_attempts           INTEGER,
    total_tds               INTEGER,

    -- Vacated opportunity (after season N-1, before season N)
    vacated_qb_attempts     DOUBLE,
    vacated_rb_carries      DOUBLE,
    vacated_wr_targets      DOUBLE,
    vacated_te_targets      DOUBLE,

    created_at              TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (team, season)
)
"""

ALL_TABLES = [
    PLAYERS, PLAY_BY_PLAY, PLAYER_SEASON_STATS, TEAM_SEASON_STATS,
    ROSTERS, DRAFT_PICKS, COMBINE_DATA, ADP, PROJECTIONS, DRAFT_SESSIONS,
    PLAYER_FEATURES, TEAM_FEATURES,
]
