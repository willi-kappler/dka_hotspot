"""SQLite schema for users, cases, onsets, and audit events."""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "data" / "app.db"

DB_TIMEOUT_SECONDS = 15.0


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _create_users(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'scientist', 'admin')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _create_clinics(conn: sqlite3.Connection) -> None:
    """Create the participating-clinic lookup."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clinics (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kreis_ags TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.executemany(
        "INSERT OR IGNORE INTO clinics (code, name, kreis_ags) VALUES (?, ?, ?)",
        [
            ("TUE", "Universitätsklinikum Tübingen, Diabetesambulanz", "08416"),
            ("RT", "Kreiskliniken Reutlingen, Klinikum am Steinenberg", "08415"),
        ],
    )


def _create_cases(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pseudonym TEXT,
            clinic TEXT NOT NULL REFERENCES clinics (code),

            age_at_onset REAL NOT NULL CHECK (age_at_onset >= 0 AND age_at_onset < 20),
            sex TEXT NOT NULL CHECK (sex IN ('Male', 'Female')),
            migration_background TEXT NOT NULL DEFAULT 'Unknown'
                CHECK (migration_background IN ('Yes', 'No', 'Unknown')),

            plz5 TEXT CHECK (plz5 IS NULL OR length(plz5) = 5),
            kreis_ags TEXT CHECK (kreis_ags IS NULL OR length(kreis_ags) = 5),

            month_of_onset INTEGER NOT NULL CHECK (month_of_onset BETWEEN 1 AND 12),
            year_of_onset INTEGER NOT NULL,

            new_onset INTEGER CHECK (new_onset IN (0, 1)),

            referral_pathway TEXT,

            ph REAL,
            bicarbonate REAL,
            hba1c REAL,
            glucose INTEGER,
            duration_of_symptoms INTEGER,

            dka_reported INTEGER CHECK (dka_reported IS NULL OR dka_reported IN (0, 1)),
            dka_severity_reported TEXT,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_cases_kreis ON cases (kreis_ags)",
        "CREATE INDEX IF NOT EXISTS idx_cases_plz5 ON cases (plz5)",
        "CREATE INDEX IF NOT EXISTS idx_cases_year ON cases (year_of_onset)",
        "CREATE INDEX IF NOT EXISTS idx_cases_clinic ON cases (clinic)",
    ):
        conn.execute(statement)


def _create_onsets(conn: sqlite3.Connection) -> None:
    """Create aggregate manifestation counts."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS onsets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic TEXT NOT NULL REFERENCES clinics (code),
            year INTEGER NOT NULL,
            kreis_ags TEXT NOT NULL CHECK (length(kreis_ags) = 5),
            manifestations INTEGER NOT NULL CHECK (manifestations >= 0),
            dka_cases INTEGER CHECK (dka_cases IS NULL OR dka_cases >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (clinic, year, kreis_ags),
            CHECK (dka_cases IS NULL OR dka_cases <= manifestations)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_onsets_year ON onsets (year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_onsets_kreis ON onsets (kreis_ags)")


def _create_audit_log(conn: sqlite3.Connection) -> None:
    """Create the audit log."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log (at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action)")


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        _create_users(conn)
        _create_clinics(conn)
        _create_cases(conn)
        _create_onsets(conn)
        _create_audit_log(conn)
