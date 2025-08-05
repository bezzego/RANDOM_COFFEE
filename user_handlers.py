from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic
import db

user_router = Router()


class RegistrationStates(StatesGroup):
    first_name = State()
    last_name = State()
    position = State()
    department = State()


def get_start_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Начать регистрацию", callback_data="start_registration"
                ),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help_info"),
            ]
        ]
    )


def get_cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")]
        ]
    )


@user_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    existing_user = db.get_user(user_id)

    if existing_user and existing_user[9]:  # is_active
        text = (
            f"С возвращением! Вы уже зарегистрированы в Random Coffee.\n"
            f"Используйте /profile для просмотра или изменения данных."
        )
        await message.answer(text)
        return

    text = (
        "Привет! 👋 Добро пожаловать в Random Coffee!\n"
        "Это корпоративный формат, в котором сотрудники из разных команд встречаются случайным образом — "
        "чтобы просто пообщаться, познакомиться, поделиться опытом или обсудить что угодно.\n\n"
        "🎯 Цель — налаживать связи внутри компании и узнавать новое.\n\n"
        "📝 Как это работает:\n"
        "1. Регистрируетесь, указав свои данные\n"
        "2. Каждую неделю получаете нового собеседника\n"
        "3. Встречаетесь за чашкой кофе\n\n"
        "Начнем?"
    )
    await message.answer(text, reply_markup=get_start_kb())


@user_router.callback_query(F.data == "start_registration")
async def on_start_registration(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    existing_user = db.get_user(user_id)
    await state.clear()
    text = (
        "📝 Давайте начнем регистрацию. Это займет меньше минуты!\n\n"
        f"{hbold('Пожалуйста, введите ваше имя:')}"
    )
    await call.message.answer(text, reply_markup=get_cancel_kb())
    await state.set_state(RegistrationStates.first_name)
    await call.answer()


@user_router.message(RegistrationStates.first_name)
async def process_first_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(
            "❌ Имя слишком короткое. Пожалуйста, введите ваше настоящее имя."
        )
        return

    await state.update_data(first_name=name)
    await message.answer(
        f"👌 Отлично, {name}! Теперь {hbold('введите вашу фамилию:')}",
        reply_markup=get_cancel_kb(),
    )
    await state.set_state(RegistrationStates.last_name)


@user_router.message(RegistrationStates.last_name)
async def process_last_name(message: Message, state: FSMContext):
    last_name = message.text.strip()
    if len(last_name) < 2:
        await message.answer(
            "❌ Фамилия слишком короткая. Пожалуйста, введите вашу настоящую фамилию."
        )
        return

    await state.update_data(last_name=last_name)
    await message.answer(
        f"💼 {hbold('Укажите вашу должность:')}\n\n"
        "Примеры:\n"
        "• Менеджер проектов\n"
        "• Разработчик Python\n"
        "• Дизайнер интерфейсов",
        reply_markup=get_cancel_kb(),
    )
    await state.set_state(RegistrationStates.position)


@user_router.message(RegistrationStates.position)
async def process_position(message: Message, state: FSMContext):
    position = message.text.strip()
    if len(position) < 3:
        await message.answer(
            "❌ Должность слишком короткая. Пожалуйста, укажите корректно."
        )
        return

    await state.update_data(position=position)
    await message.answer(
        f"🏢 {hbold('Укажите ваш отдел или направление:')}\n\n"
        "Примеры:\n"
        "• Разработка\n"
        "• Маркетинг\n"
        "• Финансы\n"
        "• HR",
        reply_markup=get_cancel_kb(),
    )
    await state.set_state(RegistrationStates.department)


@user_router.message(RegistrationStates.department)
async def process_department(message: Message, state: FSMContext):
    department = message.text.strip()
    if len(department) < 3:
        await message.answer(
            "❌ Название отдела слишком короткое. Пожалуйста, укажите корректно."
        )
        return

    data = await state.get_data()
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    position = data.get("position", "")

    text = (
        f"{hbold('Проверьте ваши данные:')}\n\n"
        f"👤 {hbold('Имя:')} {first_name} {last_name}\n"
        f"💼 {hbold('Должность:')} {position}\n"
        f"🏢 {hbold('Отдел:')} {department}\n\n"
        "Всё верно?"
    )

    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, сохранить", callback_data="confirm_registration"
                ),
                InlineKeyboardButton(
                    text="❌ Нет, начать заново", callback_data="start_registration"
                ),
            ]
        ]
    )

    await state.update_data(department=department)
    await message.answer(text, reply_markup=confirm_kb)


@user_router.callback_query(F.data == "confirm_registration")
async def on_confirm_registration(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id
    username = call.from_user.username or ""

    new_user = db.ensure_user(
        user_id=user_id,
        username=username,
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        position=data.get("position", ""),
        department=data.get("department", ""),
    )

    if new_user:
        text = (
            f"🎉 {hbold('Регистрация завершена!')}\n\n"
            "Теперь вы участник Random Coffee!\n\n"
            "Каждую неделю вы будете получать нового собеседника. "
            "Первое знакомство запланировано на ближайший понедельник."
        )
    else:
        text = (
            f"🔄 {hbold('Данные обновлены!')}\n\n"
            "Ваша информация в системе Random Coffee была успешно обновлена."
        )

    await call.message.edit_text(text)
    await call.answer()
    await state.clear()


@user_router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id)

    if not user_data:
        await message.answer(
            "❌ Вы еще не зарегистрированы в системе!\n"
            "Используйте /start для регистрации."
        )
        return

    profile_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Обновить данные", callback_data="start_registration"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отписаться", callback_data="confirm_unsubscribe"
                )
            ],
        ]
    )

    text = (
        f"{hbold('👤 Ваш профиль:')}\n\n"
        f"Имя: {user_data[2]} {user_data[3]}\n"
        f"Должность: {user_data[4]}\n"
        f"Отдел: {user_data[5]}\n"
        f"Статус: {'Активный ✅' if user_data[9] else 'Неактивный ❌'}\n\n"
        "Используйте кнопки ниже для управления профилем:"
    )

    await message.answer(text, reply_markup=profile_kb)


@user_router.callback_query(F.data == "confirm_unsubscribe")
async def on_confirm_unsubscribe(call: CallbackQuery):
    user_id = call.from_user.id
    db.deactivate_user(user_id)  # Предполагается, что такой метод существует

    text = (
        f"{hbold('👋 Вы отписались от Random Coffee')}\n\n"
        "Жаль, что вы уходите! Если захотите вернуться, "
        "используйте команду /start"
    )

    await call.message.edit_text(text)
    await call.answer()


@user_router.callback_query(F.data == "cancel_unsubscribe")
async def on_cancel_unsubscribe(call: CallbackQuery):
    await call.message.delete()
    await cmd_profile(call.message)
    await call.answer()


@user_router.callback_query(F.data == "cancel_action")
async def on_cancel_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "❌ Действие отменено. Используйте /start когда будете готовы.",
        reply_markup=get_start_kb(),
    )
    await call.answer()


@user_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        f"{hbold('Доступные команды:')}\n\n"
        "/start - Начать работу с ботом\n"
        "/profile - Просмотреть/изменить профиль\n"
        "/help - Показать эту справку\n\n"
        f"{hbold('О сервисе:')}\n"
        "Random Coffee - это возможность познакомиться "
        "с коллегами в неформальной обстановке.\n\n"
        "По всем вопросам обращайтесь к администратору."
    )
