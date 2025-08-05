"""
Database module: handles SQLite database connections and operations.
Enhanced for better integration with the updated bot functionality.
"""

import sqlite3
import datetime
from typing import List, Tuple, Optional
from config import DB_PATH

# Connect to the SQLite database with WAL mode for better concurrency
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON;")
conn.execute("PRAGMA journal_mode = WAL;")  # Better for concurrent access

# Table schema with additional useful fields
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS participants (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        full_name TEXT NOT NULL,
        position TEXT NOT NULL,
        department TEXT NOT NULL,
        frequency INTEGER DEFAULT 1 CHECK(frequency >= 1),
        last_participation TEXT,
        registration_date TEXT DEFAULT CURRENT_DATE,
        is_active BOOLEAN DEFAULT TRUE
    )
    """
)


def ensure_schema():
    """Ensure all required columns exist with proper constraints."""
    cur = conn.execute("PRAGMA table_info(participants)")
    existing_columns = {row[1] for row in cur.fetchall()}

    # Add is_active if missing (has constant default so allowed in ALTER TABLE)
    if "is_active" not in existing_columns:
        conn.execute(
            "ALTER TABLE participants ADD COLUMN is_active BOOLEAN DEFAULT TRUE"
        )

    # Add registration_date if missing, then backfill existing rows manually
    if "registration_date" not in existing_columns:
        conn.execute("ALTER TABLE participants ADD COLUMN registration_date TEXT")
        today = datetime.date.today().isoformat()
        conn.execute(
            "UPDATE participants SET registration_date = ? WHERE registration_date IS NULL",
            (today,),
        )

    conn.commit()


ensure_schema()

# Create index for faster queries on active users (after ensuring schema)
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_active_users ON participants(is_active, frequency, last_participation)"
)
conn.commit()


def ensure_user(
    user_id: int,
    username: str,
    first_name: str,
    last_name: str,
    full_name: str,
    position: str,
    department: str,
    frequency: int = 1,
) -> bool:
    """
    Add or update user in the database.
    Returns True if new user was created, False if existing user was updated.
    """

    # Use parameterized queries and transaction
    with conn:
        conn.execute(
            "INSERT INTO participants (user_id, username, first_name, last_name, full_name, "
            "position, department, frequency, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, TRUE) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "username=excluded.username, first_name=excluded.first_name, "
            "last_name=excluded.last_name, full_name=excluded.full_name, "
            "position=excluded.position, department=excluded.department, "
            "frequency=excluded.frequency, is_active=TRUE",
            (
                user_id,
                username,
                first_name,
                last_name,
                full_name,
                position,
                department,
                frequency,
            ),
        )
        return True


def get_user(user_id: int) -> Optional[Tuple]:
    """Get complete user information by user_id."""
    cur = conn.execute(
        "SELECT user_id, username, first_name, last_name, full_name, "
        "position, department, frequency, last_participation, is_active "
        "FROM participants WHERE user_id = ?",
        (user_id,),
    )
    return cur.fetchone()


def get_eligible_users() -> List[Tuple]:
    """
    Get users eligible for pairing based on their frequency and last participation.
    Returns: List of (user_id, username, full_name, position, department)
    """
    today = datetime.date.today().isoformat()
    cur = conn.execute(
        "SELECT user_id, username, full_name, position, department "
        "FROM participants "
        "WHERE is_active = TRUE AND ("
        "  last_participation IS NULL OR "
        "  date(last_participation, '+' || frequency || ' weeks') <= date(?)"
        ")",
        (today,),
    )
    return cur.fetchall()


def get_all_users(include_inactive: bool = False) -> List[Tuple]:
    """Get all users with basic info."""
    query = (
        "SELECT user_id, username, full_name, position, department, is_active "
        "FROM participants"
    )
    if not include_inactive:
        query += " WHERE is_active = TRUE"
    cur = conn.execute(query)
    return cur.fetchall()


def update_last_participation(user_ids: List[int]):
    """Update last participation date for given users."""
    today = datetime.date.today().isoformat()
    with conn:
        conn.executemany(
            "UPDATE participants SET last_participation = ? WHERE user_id = ?",
            [(today, uid) for uid in user_ids],
        )


def deactivate_user(user_id: int) -> bool:
    """Mark user as inactive (unsubscribed)."""
    with conn:
        cur = conn.execute(
            "UPDATE participants SET is_active = FALSE WHERE user_id = ?", (user_id,)
        )
        return cur.rowcount > 0


def get_user(user_id: int) -> Optional[Tuple]:
    """Get complete user information by user_id."""
    cur = conn.execute(
        "SELECT user_id, username, first_name, last_name, full_name, "
        "position, department, frequency, last_participation, is_active "
        "FROM participants WHERE user_id = ?",
        (user_id,),
    )
    return cur.fetchone()


def get_user_stats() -> dict:
    """Get statistics about users."""
    stats = {}
    cur = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active, "
        "SUM(CASE WHEN last_participation IS NULL THEN 1 ELSE 0 END) as never_participated "
        "FROM participants"
    )
    row = cur.fetchone()
    stats.update(zip(("total", "active", "never_participated"), row))

    cur = conn.execute(
        "SELECT frequency, COUNT(*) FROM participants "
        "WHERE is_active = TRUE GROUP BY frequency"
    )
    stats["frequency_distribution"] = dict(cur.fetchall())

    return stats


def close_connection():
    """Properly close database connection."""
    conn.close()
