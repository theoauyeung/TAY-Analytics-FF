"""Shared TestClient and in-memory DuckDB fixture for API tests."""
from __future__ import annotations
import duckdb
from starlette.testclient import TestClient

from tay.api.app import create_app
from tay.api.deps import get_db


def make_test_db() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE players (
            gsis_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            position VARCHAR,
            team VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            model_version VARCHAR,
            mean_projection DOUBLE,
            vor DOUBLE,
            vor_rank INTEGER,
            tier INTEGER,
            adp_delta DOUBLE,
            sim_mean DOUBLE,
            sim_p10 DOUBLE,
            sim_p90 DOUBLE,
            sim_boom_prob DOUBLE,
            sim_bust_prob DOUBLE,
            avail_mean DOUBLE,
            avail_std DOUBLE,
            std_dev DOUBLE,
            p10 DOUBLE,
            p90 DOUBLE,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    conn.execute("""
        CREATE TABLE adp (
            gsis_id VARCHAR,
            season INTEGER NOT NULL,
            platform VARCHAR NOT NULL,
            format VARCHAR NOT NULL,
            adp DOUBLE,
            rank INTEGER,
            PRIMARY KEY (season, platform, format, gsis_id)
        )
    """)
    conn.execute("""
        CREATE TABLE draft_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP DEFAULT current_timestamp,
            league_settings JSON,
            picks JSON,
            completed BOOLEAN DEFAULT FALSE
        )
    """)
    # Insert test players
    conn.executemany("INSERT INTO players VALUES (?, ?, ?, ?)", [
        ('P1', 'Bijan Robinson', 'RB', 'ATL'),
        ('P2', 'Josh Allen', 'QB', 'BUF'),
        ('P3', 'Puka Nacua', 'WR', 'LAR'),
        ('P4', 'Trey McBride', 'TE', 'ARI'),
    ])
    # Insert test projections
    conn.executemany("""
        INSERT INTO projections
        (gsis_id, season, model_version, mean_projection, vor, vor_rank, tier, adp_delta,
         sim_mean, sim_p10, sim_p90, sim_boom_prob, sim_bust_prob, avail_mean, avail_std,
         std_dev, p10, p90)
        VALUES (?, 2026, 'neural-v1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('P1', 267.0, 154.0, 1, 1, 5.0, 262.0, 210.0, 315.0, 0.25, 0.08, 15.4, 3.0, 30.0, 210.0, 315.0),
        ('P2', 386.0, 120.0, 2, 1, 8.0, 381.0, 300.0, 460.0, 0.35, 0.07, 15.3, 2.8, 38.0, 300.0, 460.0),
        ('P3', 290.0, 140.0, 3, 2, 3.0, 285.0, 215.0, 355.0, 0.28, 0.09, 14.2, 3.2, 29.0, 215.0, 355.0),
        ('P4', 197.0,  80.0, 4, 2, 7.0, 193.0, 149.0, 239.0, 0.18, 0.12, 15.2, 2.9, 20.0, 149.0, 239.0),
    ])
    # Insert ADP
    conn.executemany("INSERT INTO adp VALUES (?, 2026, 'espn', 'ppr', ?, ?)", [
        ('P1', 1.0, 1),
        ('P2', 5.0, 5),
        ('P3', 3.0, 3),
        ('P4', 12.0, 12),
    ])
    return conn


_test_db = make_test_db()

_app = create_app()
_app.dependency_overrides[get_db] = lambda: _test_db

client = TestClient(_app, raise_server_exceptions=True)
