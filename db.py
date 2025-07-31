"""
Database module: handles SQLite database connections and operations.
"""

import sqlite3
import datetime
from contextlib import closing
from config import DB_PATH

# Connect to the SQLite database (create file if not exists)
# Using check_same_thread=False to allow usage across different threads (scheduler)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
# Enable foreign key support (not used here, but good practice for future extensions)
conn.execute("PRAGMA foreign_keys = ON;")

# Create the participants table if it doesn't exist
conn.execute(
    """
CREATE TABLE IF NOT EXISTS participants (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    frequency INTEGER DEFAULT 1,
    last_participation TEXT
);
"""
)
conn.commit()


def ensure_user(
    user_id: int, username: str, full_name: str, frequency: int = 1
) -> bool:
    """
    Add a new user to the participants database or update an existing user's info.
    Returns True if a new user was added, or False if the user already existed (info was updated).
    """
    cur = conn.execute("SELECT user_id FROM participants WHERE user_id=?", (user_id,))
    result = cur.fetchone()
    cur.close()
    if result:
        # User exists: update username and full_name (keep existing frequency and last_participation)
        conn.execute(
            "UPDATE participants SET username=?, full_name=? WHERE user_id=?",
            (username, full_name, user_id),
        )
        conn.commit()
        return False
    else:
        # New user: insert record with default frequency and no last_participation yet
        conn.execute(
            "INSERT INTO participants (user_id, username, full_name, frequency) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, frequency),
        )
        conn.commit()
        return True


def get_eligible_users() -> list:
    """
    Retrieve a list of participants eligible for pairing.
    Respects each user's participation frequency and last_participation date to ensure
    users only participate once per their frequency interval (default is weekly).
    """
    cur = conn.execute(
        "SELECT user_id, username, full_name, frequency, last_participation FROM participants"
    )
    rows = cur.fetchall()
    cur.close()
    eligible = []
    today = datetime.date.today()
    for user_id, username, full_name, frequency, last_participation in rows:
        if last_participation:
            try:
                last_date = datetime.date.fromisoformat(last_participation)
            except ValueError:
                # If stored date format is unexpected, include the user (fail-safe)
                last_date = None
            if last_date:
                # Calculate days since last participation
                delta_days = (today - last_date).days
                # Skip this user if not enough days have passed according to their frequency
                if delta_days < 7 * frequency:
                    continue
        # Include user if never participated or if enough time has passed
        eligible.append((user_id, username, full_name))
    return eligible


def get_all_users() -> list:
    """
    Retrieve all users from the participants database (user_id, username, full_name).
    """
    cur = conn.execute("SELECT user_id, username, full_name FROM participants")
    rows = cur.fetchall()
    cur.close()
    return rows


def update_last_participation(user_ids: list):
    """
    Update the last_participation date for the given list of user IDs to today.
    """
    today_str = datetime.date.today().isoformat()
    for uid in user_ids:
        conn.execute(
            "UPDATE participants SET last_participation=? WHERE user_id=?",
            (today_str, uid),
        )
    conn.commit()
