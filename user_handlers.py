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
    Приветственное сообщение и приглашение присоединиться.
    """
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or message.from_user.first_name
    cur = db.conn.execute("SELECT 1 FROM participants WHERE user_id=?", (user_id,))
    already_registered = cur.fetchone() is not None
    cur.close()
    if already_registered:
        await message.answer(
            "😊 Привет! 👋 Добро пожаловать в Random Coffee!\n"  # можно оставить коротко, т.к. ты уже участвуешь
            "Ты уже зарегистрирован и будешь получать партнёра согласно настройкам."
        )
    else:
        join_button = InlineKeyboardButton(text="☕ Участвовать", callback_data="join")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[join_button]])
        welcome_text = (
            "Привет! 👋 Добро пожаловать в Random Coffee!\n"
            "Это корпоративный формат, в котором сотрудники из разных команд встречаются случайным образом — чтобы просто пообщаться, познакомиться, поделиться опытом или обсудить что угодно.\n"
            "Мы формируем пары, и вы вместе идёте на кофе, обед или встречу после работы — выбор места по желанию.\n"
            "🎯 Цель — налаживать связи внутри компании, узнавать новое и напоминать друг другу: мы — не только роли и функции, мы — команда.\n\n"
            "📝 Как это работает:\n\n"
            "1. Все желающие регистрируются и выбирают частоту участия в жеребьевке (раз в неделю или раз в месяц)\n"
            "2. Назначается дата жеребьёвки\n"
            "3. В назначенную дату тебе приходит имя партнёра и как с ним можно связаться\n"
            "4. Вы договариваетесь о встрече на этой неделе\n"
            "5. Пьёте кофе, обсуждаете интересные темы.\n\n"
            "🤝 Надеемся, это будет полезно и приятно.\n"
            "Хорошей беседы и вкусного кофе ☕\n\n"
            "Нажми кнопку ниже, чтобы присоединиться:"
        )
        await message.answer(welcome_text, reply_markup=keyboard)


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
