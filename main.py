"""
Main entry point for the Random Coffee Telegram Bot.
Sets up the bot, scheduler, and starts polling.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, SCHEDULE_DAY, SCHEDULE_HOUR, SCHEDULE_MINUTE
import db  # initialize database connection
from admin_handlers import admin_router, pair_users
from user_handlers import user_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)


async def main():
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    # Register user and admin routers with the dispatcher
    dp.include_router(user_router)
    dp.include_router(admin_router)

    # Set up the scheduler for weekly pairings
    scheduler = AsyncIOScheduler(timezone="UTC")
    # Schedule the pairing job at the configured day/time every week
    try:
        scheduler.add_job(
            pair_users,
            "cron",
            args=[bot],
            day_of_week=SCHEDULE_DAY,
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
        )
    except Exception as e:
        logging.error(f"Failed to schedule pairing job: {e}")
    scheduler.start()
    logging.info(
        f"Scheduler started: weekly pairing every {SCHEDULE_DAY} at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}."
    )

    # Start polling for bot updates (runs until stopped)
    try:
        await dp.start_polling(bot)
    finally:
        # Shutdown scheduler and close DB connection on exit
        scheduler.shutdown()
        db.conn.close()


if __name__ == "__main__":
    asyncio.run(main())
