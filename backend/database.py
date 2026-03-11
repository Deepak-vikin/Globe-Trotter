import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "globe_trotter.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password   TEXT NOT NULL,
                city       TEXT NOT NULL,
                state      TEXT NOT NULL,
                country    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                dest_city      TEXT NOT NULL,
                dest_state     TEXT NOT NULL,
                dest_country   TEXT NOT NULL,
                start_date     TEXT NOT NULL,
                return_date    TEXT NOT NULL,
                transport_mode TEXT NOT NULL DEFAULT 'flight',
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Safe migration: add columns if upgrading from an older DB
        existing = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        for col in ("city", "state", "country"):
            if col not in existing:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        conn.commit()
    print(f"[DB] Initialised → {DB_PATH}")


def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed


def create_user(name: str, email: str, password: str,
                city: str, state: str, country: str) -> dict:
    if find_user_by_email(email):
        raise ValueError("Email already registered.")
    hashed = hash_password(password)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password, city, state, country) VALUES (?,?,?,?,?,?)",
            (name.strip(), email.strip().lower(), hashed,
             city.strip(), state.strip(), country.strip()),
        )
        conn.commit()
    return get_user_by_id(cursor.lastrowid)


def find_user_by_email(email: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, city, state, country, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email, city, state, country, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def create_trip(user_id: int, dest_city: str, dest_state: str,
                dest_country: str, start_date: str, return_date: str,
                transport_mode: str = "flight") -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO trips
               (user_id, dest_city, dest_state, dest_country, start_date, return_date, transport_mode)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, dest_city.strip(), dest_state.strip(),
             dest_country.strip(), start_date, return_date, transport_mode),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM trips WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row) if row else {}


def get_user_trips(user_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM trips WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def update_trip(user_id: int, trip_id: int, dest_city: str, dest_state: str,
                dest_country: str, start_date: str, return_date: str,
                transport_mode: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE trips
               SET dest_city=?, dest_state=?, dest_country=?, start_date=?, return_date=?, transport_mode=?
               WHERE id=? AND user_id=?""",
            (dest_city.strip(), dest_state.strip(), dest_country.strip(),
             start_date, return_date, transport_mode, trip_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def delete_trip(user_id: int, trip_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
