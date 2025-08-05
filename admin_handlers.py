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
scheduler = AsyncIOScheduler()
scheduler.start()


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
    return builder.as_markup()


@admin_router.message(Command("admin"))
async def cmd_admin_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещен")
        return

    text = f"{hbold('🔧 Панель администратора')}\n\n" "Выберите действие из меню ниже:"
    await message.answer(text, reply_markup=get_admin_keyboard())


async def pair_users(bot: Bot, force_all=False) -> dict:
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
    users = db.get_all_users() if force_all else db.get_eligible_users()
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
        uname1_clean = uname1.strip("@") if uname1 else "username_not_available"
        uname2_clean = uname2.strip("@") if uname2 else "username_not_available"

        department2 = user2[5] if user2[5] else "не указан"
        partner_msg_1 = (
            f"☕ {hbold('Новый партнер для Random Coffee!')}\n\n"
            f"👤 {hbold('Имя:')} {name2}\n"
            f"💼 {hbold('Должность:')} {user2[4]}\n"
            f"🏢 {hbold('Отдел:')} {department2}\n"
            f"📱 {hbold('Контакты:')} @{uname2}"
            if uname2
            else " (нет username)" "\n\nДоговоритесь о времени встречи на этой неделе!"
        )

        department1 = user1[5] if user1[5] else "не указан"
        partner_msg_2 = (
            f"☕ {hbold('Новый партнер для Random Coffee!')}\n\n"
            f"👤 {hbold('Имя:')} {name1}\n"
            f"💼 {hbold('Должность:')} {user1[4]}\n"
            f"🏢 {hbold('Отдел:')} {department1}\n"
            f"📱 {hbold('Контакты:')} @{uname1}"
            if uname1
            else " (нет username)" "\n\nДоговоритесь о времени встречи на этой неделе!"
        )

        success = True
        try:
            await bot.send_message(uid1, partner_msg_1)
            await bot.send_message(uid2, partner_msg_2)
            # Запланировать напоминание через 3 дня
            run_date = datetime.datetime.now() + datetime.timedelta(days=3)
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
            "В этом раунде не нашлось для вас пары. "
            "Попробуем в следующий раз!"
        )

        try:
            await bot.send_message(uid, msg)
        except Exception as e:
            logging.error(f"Failed to notify user without pair {uid}: {e}")
            result["failed_to_notify"].append(uid)

    if paired_ids:
        db.update_last_participation(paired_ids)

    return result


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
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")]
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
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")]
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
    cur = db.conn.execute(
        "SELECT user_id, username, full_name, frequency, last_participation FROM participants ORDER BY full_name"
    )
    rows = cur.fetchall()
    cur.close()

    if not rows:
        await call.message.answer("ℹ️ Пока нет зарегистрированных участников.")
        return

    total = len(rows)
    active = sum(1 for row in rows if row[0] in eligible)

    text = (
        f"{hbold('👥 Участники Random Coffee')}\n\n"
        f"• Всего участников: {total}\n"
        f"• Активных (готовых к жеребьевке): {active}\n"
        f"• Неактивных: {total - active}\n\n"
        f"{hbold('Последние 10 участников:')}\n"
    )

    for row in rows[:10]:
        user_id, username, full_name, frequency, last_participation = row
        status = "✅" if user_id in eligible else "⏸"
        username_display = f"@{username}" if username else "нет username"
        last_part = (
            f", последний раз: {last_participation}" if last_participation else ""
        )
        text += f"{status} {full_name} ({username_display}){last_part}\n"

    if total > 10:
        text += f"\n...и ещё {total - 10} участников"

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

    await call.message.edit_text(text, reply_markup=keyboard)


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
