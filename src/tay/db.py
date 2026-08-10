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
    conn.commit()
