"""
User handlers: handles user commands and interactions (start, join, etc.).
"""

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import db

user_router = Router()


@user_router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Handle the /start command for a new or returning user.
    """
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or message.from_user.first_name
    # Check if the user is already in the participants database
    cur = db.conn.execute("SELECT 1 FROM participants WHERE user_id=?", (user_id,))
    already_registered = cur.fetchone() is not None
    cur.close()
    if already_registered:
        # User is already participating
        await message.answer(
            f"😊 Привет, {message.from_user.first_name}! Ты уже участвуешь в Random Coffee.\n"
            f"Ты будешь получать партнёра каждую неделю."
        )
    else:
        # New user: prompt to join with an inline button
        join_button = InlineKeyboardButton(text="☕ Участвовать", callback_data="join")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[join_button]])
        await message.answer(
            "👋 Добро пожаловать! Этот бот подбирает собеседников для еженедельной встречи за случайным кофе.\n"
            "Нажми кнопку ниже, чтобы присоединиться:",
            reply_markup=keyboard,
        )


@user_router.callback_query(lambda call: call.data == "join")
async def on_join_button(call: CallbackQuery):
    """
    Handle the user clicking the 'Participate' button to join the weekly pairing pool.
    """
    user_id = call.from_user.id
    username = call.from_user.username or ""
    full_name = call.from_user.full_name or call.from_user.first_name
    # Add the user to the database (or update if they exist)
    new_user = db.ensure_user(user_id, username, full_name)
    if new_user:
        # Successfully added a new participant
        await call.answer("Ты добавлен в список участников!", show_alert=False)
        # Remove the keyboard to prevent duplicate joins
        if call.message:
            await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer(
            "✅ Ты участвуешь в Random Coffee! Ожидай партнёра каждую неделю ☕."
        )
    else:
        # User was already registered
        await call.answer("Ты уже участвуешь.", show_alert=True)
        if call.message:
            await call.message.edit_reply_markup(reply_markup=None)
