"""
database.py — Globe Trotter SQLite Database Layer
Handles: DB initialisation, user creation, and user lookup.

SQLite file: backend/globe_trotter.db  (auto-created on first run)
"""

import sqlite3
import hashlib
import os

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "globe_trotter.db")


# ──────────────────────────────────────────────
# Connection helper
# ──────────────────────────────────────────────
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows accessible like dicts
    conn.execute("PRAGMA journal_mode=WAL") # better concurrency
    return conn


# ──────────────────────────────────────────────
# Schema initialisation  (with safe migration)
# ──────────────────────────────────────────────
def init_db() -> None:
    with get_connection() as conn:
        # Create table with all columns (new installs)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                email      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password   TEXT    NOT NULL,
                city       TEXT    NOT NULL DEFAULT '',
                state      TEXT    NOT NULL DEFAULT '',
                country    TEXT    NOT NULL DEFAULT '',
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Safe migration: add columns if upgrading from an older DB
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        for col, definition in (
            ("city",    "TEXT NOT NULL DEFAULT ''"),
            ("state",   "TEXT NOT NULL DEFAULT ''"),
            ("country", "TEXT NOT NULL DEFAULT ''"),
        ):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
                print(f"[DB] Migration: added column '{col}'")

        conn.commit()
    print(f"[DB] Initialised → {DB_PATH}")


# ──────────────────────────────────────────────
# Password hashing (SHA-256)
# ──────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Return a SHA-256 hex digest of the plain-text password."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plain password matches the stored hash."""
    return hash_password(plain) == hashed


# ──────────────────────────────────────────────
# User operations
# ──────────────────────────────────────────────
def create_user(
    name: str,
    email: str,
    password: str,
    city: str = "",
    state: str = "",
    country: str = "",
) -> dict:
    if find_user_by_email(email):
        raise ValueError("Email already registered.")

    hashed = hash_password(password)
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO users (name, email, password, city, state, country)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                name.strip(),
                email.strip().lower(),
                hashed,
                city.strip(),
                state.strip(),
                country.strip(),
            ),
        )
        conn.commit()
        user_id = cursor.lastrowid

    return get_user_by_id(user_id)


def find_user_by_email(email: str) -> dict | None:
    """
    Return user dict for the given email, or None if not found.
    Comparison is case-insensitive (COLLATE NOCASE on column).
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Return user dict by primary key, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, city, state, country, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    """Return all users (passwords excluded) — useful for admin/debug."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email, city, state, country, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]
