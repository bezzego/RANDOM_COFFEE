import logging
import random
import datetime
from user_handlers import send_reminder_after_pairing
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hbold, hitalic, hcode

import db
from config import ADMIN_IDS

admin_router = Router()
awaiting_actions = {}  # user_id: action_type

# Scheduler for reminders
from zoneinfo import ZoneInfo

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Moscow"))
scheduler.start()

# --- helpers for long outputs ---


def chunk_list(lst, size):
    """Yield successive chunks from list with max length `size`."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def split_text_by_limit(lines, header="", limit=4000):
    """Split a list of text lines into chunks respecting Telegram 4096 char limit."""
    chunks = []
    current = header
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = header + line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)
    return chunks


def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 Провести жеребьевку", callback_data="admin_pair_force"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📢 Сделать рассылку", callback_data="admin_broadcast"
        ),
        InlineKeyboardButton(
            text="📝 Тестовая рассылка", callback_data="admin_test_broadcast"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Список участников", callback_data="admin_list"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить пользователя", callback_data="admin_delete_user"
        )
    )
    return builder.as_markup()


@admin_router.message(Command("admin"))
async def cmd_admin_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещен")
        return

    text = f"{hbold('🔧 Панель администратора')}\n\n" "Выберите действие из меню ниже:"
    await message.answer(text, reply_markup=get_admin_keyboard())


async def pair_users(bot: Bot, force_all: bool = False, include_active_also: bool = False) -> dict:
    """
    Формирует пары пользователей
    Возвращает словарь с результатами:
    {
        "pairs_count": int,
        "users_paired": int,
        "users_without_pair": int,
        "failed_to_notify": list
    }
    """
    # When forcing pairing from admin panel, explicitly request only active users
    users = db.get_all_users(include_inactive=False) if force_all else db.get_eligible_users()
    result = {
        "pairs_count": 0,
        "users_paired": 0,
        "users_without_pair": 0,
        "failed_to_notify": [],
    }

    if len(users) < 2:
        return result

    random.shuffle(users)
    paired_ids = []

    # Формируем пары
    for i in range(0, len(users) - (len(users) % 2), 2):
        # Получаем все поля для первого пользователя
        user1 = users[i]
        uid1 = user1[0]
        uname1 = user1[1]
        name1 = user1[2] if len(user1) > 2 else "Неизвестно"

        # Получаем все поля для второго пользователя
        user2 = users[i + 1]
        uid2 = user2[0]
        uname2 = user2[1]
        name2 = user2[2] if len(user2) > 2 else "Неизвестно"

        # Обработка username для корректной передачи в напоминание (без @, не пустой)
        uname1_clean = uname1.lstrip("@") if uname1 else ""
        uname2_clean = uname2.lstrip("@") if uname2 else ""

        position2 = user2[3] if len(user2) > 3 and user2[3] else "не указан"
        department2 = user2[4] if len(user2) > 4 and user2[4] else "не указан"
        if uname2:
            contact2 = f"📱 {hbold('Контакты:')} @{uname2}\n"
        else:
            contact2 = "📱 (нет username)\n"
        partner_msg_1 = (
            f"☕ {hbold('Новый партнер для Random Coffee!')}\n\n"
            f"👤 {hbold('Имя:')} {name2}\n"
            f"💼 {hbold('Должность:')} {position2}\n"
            f"🏢 {hbold('Отдел:')} {department2}\n"
            f"{contact2}\n"
            "Теперь ты можешь написать своему партнеру и договориться о встрече на этой неделе."
        )

        position1 = user1[3] if len(user1) > 3 and user1[3] else "не указан"
        department1 = user1[4] if len(user1) > 4 and user1[4] else "не указан"
        if uname1:
            contact1 = f"📱 {hbold('Контакты:')} @{uname1}\n"
        else:
            contact1 = "📱 (нет username)\n"
        partner_msg_2 = (
            f"☕ {hbold('Новый партнер для Random Coffee!')}\n\n"
            f"👤 {hbold('Имя:')} {name1}\n"
            f"💼 {hbold('Должность:')} {position1}\n"
            f"🏢 {hbold('Отдел:')} {department1}\n"
            f"{contact1}\n"
            "Теперь ты можешь написать своему партнеру и договориться о встрече на этой неделе."
        )

        success = True
        try:
            await bot.send_message(uid1, partner_msg_1)
            await bot.send_message(uid2, partner_msg_2)
            # Запланировать напоминание через 3 дня
            run_date = datetime.datetime.now(
                ZoneInfo("Europe/Moscow")
            ) + datetime.timedelta(days=3)
            scheduler.add_job(
                send_reminder_after_pairing,
                trigger="date",
                run_date=run_date,
                args=[uid1, name2, uname2_clean, bot],
            )
            scheduler.add_job(
                send_reminder_after_pairing,
                trigger="date",
                run_date=run_date,
                args=[uid2, name1, uname1_clean, bot],
            )
        except Exception as e:
            logging.error(f"Failed to notify pair {uid1} and {uid2}: {e}")
            result["failed_to_notify"].extend([uid1, uid2])
            success = False

        if success:
            paired_ids.extend([uid1, uid2])
            result["pairs_count"] += 1
            result["users_paired"] += 2

    # Обработка пользователя без пары
    if len(users) % 2 == 1:
        user = users[-1]
        uid = user[0]
        uname = user[1]
        name = user[2] if len(user) > 2 else "Неизвестно"

        result["users_without_pair"] += 1

        msg = (
            f"☕ {hbold('Random Coffee')}\n\n"
            "В этом раунде не нашлось для вас пары, потому что количество участников оказалось нечетным.\n"
            "В следующий раз обязательно найдём вам собеседника!"
        )

        try:
            await bot.send_message(uid, msg)
        except Exception as e:
            logging.error(f"Failed to notify user without pair {uid}: {e}")
            result["failed_to_notify"].append(uid)

    if paired_ids:
        db.update_last_participation(paired_ids)

    return result


async def pair_users_monday(bot: Bot):
    """
    Wrapper to be scheduled weekly from main.py.
    Calls pair_users and logs a short summary.
    """
    logging.info("Weekly pairing job started.")
    try:
        result = await pair_users(bot, force_all=False)
        logging.info(
            f"Weekly pairing finished: pairs={result.get('pairs_count',0)}, "
            f"paired={result.get('users_paired',0)}, without_pair={result.get('users_without_pair',0)}"
        )
    except Exception as e:
        logging.exception(f"pair_users_monday failed: {e}")


@admin_router.callback_query(F.data == "admin_pair_force")
async def on_admin_pair_force(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    await call.answer("⏳ Формируем пары...")

    result = await pair_users(call.bot, force_all=True)

    if result["pairs_count"] > 0:
        text = (
            f"{hbold('✅ Жеребьевка завершена!')}\n\n"
            f"• Создано пар: {result['pairs_count']}\n"
            f"• Участников с парой: {result['users_paired']}\n"
            f"• Участников без пары: {result['users_without_pair']}\n"
        )

        if result["failed_to_notify"]:
            text += f"\n{hitalic('Не удалось уведомить:')} {len(result['failed_to_notify'])} участников"
    else:
        text = "⚠️ Не удалось сформировать пары. Недостаточно участников."

    await call.message.edit_text(text)
    await call.message.answer(
        "🔧 Панель администратора", reply_markup=get_admin_keyboard()
    )


@admin_router.callback_query(F.data == "admin_broadcast")
async def on_admin_broadcast(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    awaiting_actions[call.from_user.id] = "broadcast"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить", callback_data="admin_back_to_menu"
                )
            ]
        ]
    )

    await call.message.edit_text(
        f"{hbold('📢 Рассылка всем участникам')}\n\n"
        "Отправьте сообщение, которое нужно разослать всем пользователям.\n"
        "Можно использовать текст, фото или другие медиа.\n\n"
        f"{hitalic('Для отмены нажмите кнопку ниже или отправьте /cancel')}",
        reply_markup=keyboard,
    )
    await call.answer()


@admin_router.callback_query(F.data == "admin_test_broadcast")
async def on_admin_test_broadcast(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    awaiting_actions[call.from_user.id] = "test_broadcast"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить", callback_data="admin_back_to_menu"
                )
            ]
        ]
    )

    await call.message.edit_text(
        f"{hbold('📢 Тестовая рассылка')}\n\n"
        "Отправьте сообщение для тестовой рассылки (получите только вы).\n"
        "Проверьте как будет выглядеть сообщение перед основной рассылкой.\n\n"
        f"{hitalic('Для отмены нажмите кнопку ниже или отправьте /cancel')}",
        reply_markup=keyboard,
    )
    await call.answer()


@admin_router.callback_query(F.data == "admin_list")
async def on_admin_list(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    await call.answer("⏳ Загружаем список участников...")

    eligible = {u[0] for u in db.get_eligible_users()}
    active = {u[0] for u in db.get_all_active_users()}
    cur = db.conn.execute(
        "SELECT user_id, username, full_name, frequency, last_participation FROM participants ORDER BY full_name"
    )
    rows = cur.fetchall()
    cur.close()

    if not rows:
        await call.message.answer("ℹ️ Пока нет зарегистрированных участников.")
        return

    total = len(rows)
    active_count = sum(1 for row in rows if row[0] in active)
    eligible_count = sum(1 for row in rows if row[0] in eligible)

    header = (
        f"{hbold('👥 Участники Random Coffee')}\n\n"
        f"• Всего участников: {total}\n"
        f"• Активных: {active_count}\n"
        f"• Готовых к жеребьевке: {eligible_count}\n"
        f"• Неактивных: {total - active_count}\n\n"
    )

    # Сформируем строки списка для ВСЕХ пользователей
    lines = []
    for row in rows:
        user_id, username, full_name, frequency, last_participation = row
        if user_id in eligible:
            status = "✅"
        elif user_id in active:
            status = "☑️"  # активен, но не eligible по дате/частоте
        else:
            status = "⏸"
        username_display = f"@{username}" if username else "нет username"
        last_part = (
            f", последний раз: {last_participation}" if last_participation else ""
        )
        freq_part = f", раз в {frequency} недель" if frequency is not None else ""
        lines.append(f"{status} {full_name} ({username_display}){freq_part}{last_part}")

    # Разобьём вывод на несколько сообщений, чтобы показать всех
    chunks = split_text_by_limit(lines, header=header, limit=4000)

    # Перепишем исходное сообщение шапкой и первой порцией (если поместится)
    if chunks:
        await call.message.edit_text(chunks[0])
        # Остальные части отправим отдельными сообщениями
        for part in chunks[1:]:
            await call.message.answer(part)

    # Кнопки действий отдельным сообщением
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Экспорт в CSV", callback_data="admin_export_csv"
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_menu")],
        ]
    )
    await call.message.answer("Выберите действие:", reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_stats")
async def on_admin_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    await call.answer("⏳ Собираем статистику...")

    # Общая статистика
    total_users = db.conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
    active_users = len(db.get_eligible_users())

    # Статистика по участию
    participation_stats = db.conn.execute(
        "SELECT last_participation, COUNT(*) FROM participants "
        "WHERE last_participation IS NOT NULL "
        "GROUP BY last_participation ORDER BY last_participation DESC LIMIT 5"
    ).fetchall()

    text = (
        f"{hbold('📊 Статистика Random Coffee')}\n\n"
        f"• Всего участников: {total_users}\n"
        f"• Активных: {active_users}\n"
        f"• Неактивных: {total_users - active_users}\n\n"
        f"{hbold('Последние участия:')}\n"
    )

    for date, count in participation_stats:
        text += f"• {date}: {count} участников\n"

    # Статистика по частоте
    freq_stats = db.conn.execute(
        "SELECT frequency, COUNT(*) FROM participants GROUP BY frequency ORDER BY frequency"
    ).fetchall()

    text += f"\n{hbold('Частота участия:')}\n"
    for freq, count in freq_stats:
        text += f"• Раз в {freq} недель: {count} участников\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_menu")],
        ]
    )

    await call.message.edit_text(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_export_csv")
async def on_admin_export_csv(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    await call.answer("⏳ Подготавливаем данные...")

    cur = db.conn.execute(
        "SELECT user_id, username, full_name, position, department, frequency, last_participation "
        "FROM participants ORDER BY full_name"
    )
    rows = cur.fetchall()
    cur.close()

    if not rows:
        await call.answer("ℹ️ Нет данных для экспорта", show_alert=True)
        return

    # Формируем CSV
    csv_content = (
        "ID;Username;Full Name;Position;Department;Frequency;Last Participation\n"
    )
    for row in rows:
        csv_content += ";".join(str(x) if x is not None else "" for x in row) + "\n"

    # В реальном боте здесь нужно сохранить файл и отправить его
    # Для примера покажем первые 5 строк
    preview = "\n".join(csv_content.split("\n")[:6])

    await call.message.answer(
        f"{hbold('📁 Экспорт данных (первые 5 строк):')}\n"
        f"{hcode(preview)}\n\n"
        "В реальной версии бота здесь будет прикрепленный CSV-файл."
    )
    await call.answer()


@admin_router.callback_query(F.data == "admin_back_to_menu")
async def on_admin_back_to_menu(call: CallbackQuery):
    await call.message.edit_text(
        f"{hbold('🔧 Панель администратора')}\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
    )
    await call.answer()


@admin_router.callback_query(F.data == "cancel_action")
async def on_cancel_action(call: CallbackQuery):
    if call.from_user.id in awaiting_actions:
        del awaiting_actions[call.from_user.id]
    await call.message.edit_text(
        "❌ Действие отменено.", reply_markup=get_admin_keyboard()
    )
    await call.answer()


@admin_router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.from_user.id in awaiting_actions:
        action = awaiting_actions.pop(message.from_user.id)
        await message.answer(
            f"❌ {hbold('Отменено:')} {action.replace('_', ' ')}",
            reply_markup=get_admin_keyboard(),
        )
    else:
        await message.answer("Нет активных действий для отмены.")


@admin_router.message()
async def on_admin_message(message: Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return

    action = awaiting_actions.get(message.from_user.id)

    if not action:
        return

    if action == "test_broadcast":
        # Тестовая рассылка - отправляем только админу
        try:
            await message.copy_to(message.from_user.id)
            await message.answer(
                "✅ Тестовое сообщение отправлено вам. "
                "Если всё в порядке, можете сделать основную рассылку.",
                reply_markup=get_admin_keyboard(),
            )
        except Exception as e:
            logging.error(f"Failed to send test broadcast: {e}")
            await message.answer(
                "❌ Не удалось отправить тестовое сообщение.",
                reply_markup=get_admin_keyboard(),
            )
        finally:
            awaiting_actions.pop(message.from_user.id, None)

    elif action == "broadcast":
        # Основная рассылка
        users = db.get_all_users()
        total = len(users)
        success = 0
        failed = []

        await message.answer(f"⏳ Начинаем рассылку для {total} пользователей...")

        for user in users:
            user_id = user[0]  # Берем только ID пользователя
            try:
                await message.copy_to(user_id)
                success += 1
            except Exception as e:
                logging.error(f"Failed to send broadcast to {user_id}: {e}")
                failed.append(user_id)
                continue

        text = (
            f"{hbold('📢 Результаты рассылки:')}\n\n"
            f"• Всего получателей: {total}\n"
            f"• Успешно отправлено: {success}\n"
            f"• Не удалось отправить: {len(failed)}\n"
        )

        if failed:
            text += f"\n{hitalic('Не удалось отправить:')} первые 10 ID: {', '.join(map(str, failed[:10]))}"

        await message.answer(text, reply_markup=get_admin_keyboard())
        awaiting_actions.pop(message.from_user.id, None)


# --- Новый обработчик: Удаление пользователя ---


@admin_router.callback_query(F.data.startswith("admin_delete_user"))
async def on_admin_delete_user(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    users = db.get_all_users()
    if not users:
        await call.message.answer("ℹ️ Нет зарегистрированных пользователей.")
        return

    # Сообщение-инструкция
    await call.message.edit_text(
        f"{hbold('🗑 Удаление пользователя')}\n\n"
        "Ниже показаны ВСЕ пользователи. Нажмите на имя, чтобы удалить.\n"
        "(Список разбит на несколько сообщений, если пользователей много.)"
    )

    # Телеграм ограничивает размер клавиатуры, поэтому отправляем несколько сообщений по 45 кнопок
    for idx, chunk in enumerate(chunk_list(users, 45)):
        keyboard_rows = [
            [
                InlineKeyboardButton(
                    text=(f"{u[2]} (@{u[1]})" if u[1] else u[2]),
                    callback_data=f"admin_delete_confirm:{u[0]}",
                )
            ]
            for u in chunk
        ]
        keyboard_rows.append(
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_menu")]
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await call.message.answer(
            f"Список для удаления — часть {idx+1}", reply_markup=keyboard
        )

    await call.answer()


@admin_router.callback_query(F.data.startswith("admin_delete_confirm:"))
async def on_admin_delete_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = int(call.data.split(":")[1])
    db.delete_user(user_id)

    try:
        await call.bot.send_message(
            chat_id=user_id,
            text="❌ Вы были удалены из Random Coffee администратором.\n"
            "Если хотите вернуться — используйте /start.",
        )
    except Exception as e:
        logging.error(f"Failed to notify deleted user {user_id}: {e}")

    await call.message.edit_text(
        f"✅ Пользователь {user_id} удален.", reply_markup=get_admin_keyboard()
    )
    await call.answer()


@admin_router.callback_query(F.data == "noop")
async def on_noop(call: CallbackQuery):
    await call.answer()
