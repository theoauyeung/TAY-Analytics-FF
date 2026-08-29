"""DuckDB connection manager."""
from pathlib import Path
import duckdb
from tay.schemas.tables import ALL_TABLES

DB_PATH = Path(__file__).parent.parent.parent / "data" / "ff.duckdb"


def get_conn(db_path: str | Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection. Creates the file if absent."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables if they do not exist."""
    for ddl in ALL_TABLES:
        conn.execute(ddl)
    # Idempotent migrations for existing databases
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS consensus_projection DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS blended_projection DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_target_share DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_carry_share DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_rec_share DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_pass_att_per_game DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_targets DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_receptions DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_rec_yards DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_rec_tds DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_rush_attempts DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_rush_yards DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_rush_tds DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_pass_attempts DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_completions DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_pass_yards DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_pass_tds DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS proj_interceptions DOUBLE")
    conn.commit()
