"""
Config module: loads environment variables and defines configuration constants.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot token from environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment")

# List of admin user IDs (as integers) from environment
ADMIN_IDS = []
admin_ids_str = os.getenv("ADMIN_IDS")
if admin_ids_str:
    try:
        ADMIN_IDS = [int(x) for x in admin_ids_str.split(",")]
    except ValueError:
        raise RuntimeError("ADMIN_IDS environment variable is malformed")

# Default to provided IDs (from specification) if none set in .env
if not ADMIN_IDS:
    ADMIN_IDS = [764643451, 8128706897]

# Database file path (default 'coffee_bot.db' in current directory)
DB_PATH = os.getenv("DB_PATH", "coffee_bot.db")

# Schedule configuration for weekly pairing (default: every Monday at 10:00)
# Day of week can be "mon", "tue", ..., "sun" (or numeric 0=Monday)
SCHEDULE_DAY = os.getenv("SCHEDULE_DAY", "mon")
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "10"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "00"))
