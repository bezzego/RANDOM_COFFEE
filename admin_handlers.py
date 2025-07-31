import logging
import random
import datetime
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import db
from config import ADMIN_IDS

admin_router = Router()
awaiting_broadcast_admins = set()


@admin_router.message(Command("admin"))
async def cmd_admin_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📌 Провести жеребьевку",
                    callback_data="admin_pair_force",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка всем", callback_data="admin_broadcast"
                )
            ],
            [InlineKeyboardButton(text="👥 Участники", callback_data="admin_list")],
        ]
    )
    await message.answer(
        "🔧 <b>Панель администратора</b>:\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def pair_users(bot: Bot) -> int:
    users = db.get_eligible_users()
    if len(users) < 2:
        return 0
    random.shuffle(users)
    pairs_count = 0
    paired_ids = []
    for i in range(0, len(users) - (len(users) % 2), 2):
        uid1, uname1, name1 = users[i]
        uid2, uname2, name2 = users[i + 1]
        partner_msg_1 = f"☕ Твой партнёр по случайному кофе: {name2}"
        partner_msg_2 = f"☕ Твой партнёр по случайному кофе: {name1}"
        partner_msg_1 += f" (@{uname2})" if uname2 else " (нет username)"
        partner_msg_2 += f" (@{uname1})" if uname1 else " (нет username)"
        try:
            await bot.send_message(uid1, partner_msg_1)
            await bot.send_message(uid2, partner_msg_2)
        except Exception as e:
            logging.error(
                f"Не удалось отправить сообщение парам {uid1} или {uid2}: {e}"
            )
        paired_ids.extend([uid1, uid2])
        pairs_count += 1
    if len(users) % 2 == 1:
        uid, uname, name = users[-1]
        try:
            await bot.send_message(
                uid,
                "☕ К сожалению, в этом раунде не нашлось пары. В следующий раз ты точно будешь участвовать!",
            )
        except Exception as e:
            logging.error(
                f"Не удалось отправить сообщение без партнёра пользователю {uid}: {e}"
            )
    db.update_last_participation(paired_ids)
    return pairs_count


async def pair_all_users(bot: Bot) -> int:
    users = db.get_all_users()
    if len(users) < 2:
        return 0
    random.shuffle(users)
    pairs_count = 0
    paired_ids = []
    for i in range(0, len(users) - (len(users) % 2), 2):
        uid1, uname1, name1 = users[i]
        uid2, uname2, name2 = users[i + 1]
        partner_msg_1 = f"☕ Твой партнёр по случайному кофе: {name2}"
        partner_msg_2 = f"☕ Твой партнёр по случайному кофе: {name1}"
        partner_msg_1 += f" (@{uname2})" if uname2 else " (нет username)"
        partner_msg_2 += f" (@{uname1})" if uname1 else " (нет username)"
        try:
            await bot.send_message(uid1, partner_msg_1)
            await bot.send_message(uid2, partner_msg_2)
        except Exception as e:
            logging.error(
                f"Не удалось отправить сообщение парам {uid1} или {uid2}: {e}"
            )
        paired_ids.extend([uid1, uid2])
        pairs_count += 1
    if len(users) % 2 == 1:
        uid, uname, name = users[-1]
        try:
            await bot.send_message(
                uid,
                "☕ К сожалению, в этом раунде не нашлось пары. В следующий раз ты точно будешь участвовать!",
            )
        except Exception as e:
            logging.error(
                f"Не удалось отправить сообщение без партнёра пользователю {uid}: {e}"
            )
    db.update_last_participation(paired_ids)
    return pairs_count


@admin_router.callback_query(lambda call: call.data == "admin_pair")
async def on_admin_pair_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return
    pairs_made = await pair_users(call.bot)
    if pairs_made > 0:
        await call.answer("✅ Пары сформированы!", show_alert=False)
        await call.message.answer(
            f"👥 Случайные пары составлены для {pairs_made*2} участников ({pairs_made} пар)."
        )
    else:
        await call.answer(
            "⚠️ Недостаточно участников для формирования пар.", show_alert=True
        )
        await call.message.answer(
            "⚠️ Пока недостаточно участников для формирования пар."
        )


@admin_router.callback_query(lambda call: call.data == "admin_pair_force")
async def on_admin_pair_force_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return
    pairs_made = await pair_all_users(call.bot)
    if pairs_made > 0:
        await call.answer("✅ Принудительные пары сформированы!", show_alert=False)
        await call.message.answer(
            f"✅ Принудительные пары сформированы для {pairs_made*2} участников ({pairs_made} пар)."
        )
    else:
        await call.answer(
            "⚠️ Недостаточно пользователей для формирования пар.", show_alert=True
        )
        await call.message.answer("⚠️ Недостаточно пользователей для формирования пар.")


@admin_router.callback_query(lambda call: call.data == "admin_broadcast")
async def on_admin_broadcast_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.answer()
    awaiting_broadcast_admins.add(call.from_user.id)
    await call.message.answer(
        "✉️ Отправь мне текст для рассылки всем пользователям.\n\nИли отправь /cancel, чтобы отменить."
    )


@admin_router.callback_query(lambda call: call.data == "admin_list")
async def on_admin_list_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return
    # Получаем всех пользователей и eligibility
    eligible = {u[0] for u in db.get_eligible_users()}
    cur = db.conn.execute(
        "SELECT user_id, username, full_name, frequency, last_participation FROM participants ORDER BY user_id"
    )
    rows = cur.fetchall()
    cur.close()
    if not rows:
        await call.message.answer("Пока нет зарегистрированных участников.")
        return
    lines = []
    today = datetime.date.today()
    for user_id, username, full_name, frequency, last_participation in rows:
        status = "✅ Готов" if user_id in eligible else "⏳ Ждёт"
        if last_participation:
            try:
                last = datetime.date.fromisoformat(last_participation)
                since = (today - last).days
                lp = f"последнее участие {last.isoformat()} ({since} дн. назад)"
            except Exception:
                lp = f"последнее участие {last_participation}"
        else:
            lp = "ещё не участвовал"
        uname_display = f"@{username}" if username else "(нет username)"
        lines.append(f"• {full_name} {uname_display} — {status}, {lp}")
    chunk = "\n".join(lines[:50])
    footer = "" if len(lines) <= 50 else f"\n...и ещё {len(lines)-50} участника(ов)"
    await call.message.answer(f"👥 Участники:\n{chunk}{footer}")


@admin_router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if message.from_user.id in awaiting_broadcast_admins:
        awaiting_broadcast_admins.remove(message.from_user.id)
        await message.reply("Рассылка отменена.")
    else:
        await message.reply("Нет активной рассылки для отмены.")


@admin_router.message()
async def on_admin_message(message: Message):
    if message.from_user.id in awaiting_broadcast_admins:
        broadcast_text = message.text
        awaiting_broadcast_admins.remove(message.from_user.id)
        users = db.get_all_users()
        success_count = 0
        for user_id, username, full_name in users:
            try:
                await message.bot.send_message(user_id, broadcast_text)
                success_count += 1
            except Exception as e:
                logging.error(
                    f"Не удалось разослать сообщение пользователю {user_id}: {e}"
                )
                continue
        await message.answer(f"✅ Рассылка отправлена {success_count} пользователям.")
