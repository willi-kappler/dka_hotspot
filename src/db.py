import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "data" / "app.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def create_users_table(conn: sqlite3.Connection) -> None:
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


def migrate_users_table(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    if not table or "'admin'" in table["sql"]:
        return

    conn.execute("ALTER TABLE users RENAME TO users_old")
    create_users_table(conn)
    conn.execute("""
        INSERT INTO users (id, username, password_hash, role, is_active, created_at)
        SELECT id, username, password_hash, role, is_active, created_at
        FROM users_old
    """)
    conn.execute("DROP TABLE users_old")


# TODO before real (non-synthetic) data: snapshot app.db on startup
# (e.g. VACUUM INTO data/backups/app-YYYY-MM-DD.db, keep last 7) —
# edit/delete have no undo, so a backup is the only recovery path.
def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        create_users_table(conn)
        migrate_users_table(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                age_at_onset INTEGER NOT NULL,
                sex TEXT NOT NULL CHECK (sex IN ('Male', 'Female')),
                zipcode TEXT NOT NULL,
                state TEXT NOT NULL,
                month_of_onset INTEGER NOT NULL,
                year_of_onset INTEGER NOT NULL,
                a1c REAL,
                glucose INTEGER NOT NULL,
                bikarb REAL NOT NULL,
                ph REAL NOT NULL,
                duration_of_symptoms INTEGER,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_sex ON patients (sex)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_year ON patients (year_of_onset)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_zipcode_state ON patients (zipcode, state)")
