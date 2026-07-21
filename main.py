import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

import config
import database
from trading import get_tv_signal

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

WELCOME_IMAGE_URL = "https://images.unsplash.com/photo-1614162692292-7ac56d7f7f1e"

class RegisterState(StatesGroup):
    waiting_for_pocket_id = State()

def get_pairs_keyboard():
    buttons = []
    pairs = list(config.PAIR_MAP.keys())
    for i in range(0, len(pairs), 2):
        row = [KeyboardButton(text=pairs[i])]
        if i + 1 < len(pairs):
            row.append(KeyboardButton(text=pairs[i+1]))
        buttons.append(row)
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- Хэндлеры старта и регистрации ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    is_approved = await database.is_user_approved(user_id)

    if is_approved:
        await message.answer_photo(
            photo=WELCOME_IMAGE_URL,
            caption=(
                "🏎️ **ДОБРО ПОЖАЛОВАТЬ В SQUAD 911!**\n\n"
                "📊 Твой аккаунт верифицирован.\n"
                "Выбери валютную пару ниже, чтобы получить сигнал:"
            ),
            reply_markup=get_pairs_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer_photo(
            photo=WELCOME_IMAGE_URL,
            caption=(
                "🤖 **SQUAD 911 | AI Signal Bot**\n\n"
                "Для получения доступа к аналитической панели введите ваш **ID аккаунта Pocket Option** (8 цифр).\n\n"
                "📌 *Чтобы заявка была принята, необходимо пополнить баланс от $15.*"
            ),
            parse_mode="Markdown"
        )
        await state.set_state(RegisterState.waiting_for_pocket_id)

# --- Ввод ID (Срабатывает только если юзер НЕ верифицирован) ---

@dp.message(RegisterState.waiting_for_pocket_id)
async def process_pocket_id(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Защита: если пользователь уже верифицирован в базе, сбрасываем состояние и передаем обработку дальше
    if await database.is_user_approved(user_id):
        await state.clear()
        if message.text in config.PAIR_MAP.keys():
            await send_signal(message, state)
            return

    pocket_id = message.text.strip()

    if not pocket_id.isdigit() or len(pocket_id) < 5:
        await message.answer("❌ Неверный формат ID. Введите корректный цифровой ID Pocket Option:")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
    await database.add_or_update_user(user_id, username, pocket_id)
    await state.clear()

    await message.answer(
        "⏳ **Заявка отправлена на проверку!**\n\n"
        "Менеджер проверяет ваш ID. Обычно это занимает от 2 до 15 минут. Вы получите уведомление, как только доступ будет открыт.",
        parse_mode="Markdown"
    )

    admin_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])

    await bot.send_message(
        chat_id=config.ADMIN_ID,
        text=f"📥 **Новая заявка на доступ!**\n\n"
             f"👤 Пользователь: {username} (ID: `{user_id}`)\n"
             f"🆔 Pocket Option ID: `{pocket_id}`",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )

# --- Обработка решений админа ---

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await database.set_approve_status(target_id, True)

    # Точечно очищаем FSM-состояние одобренного пользователя
    user_key = StorageKey(bot_id=bot.id, chat_id=target_id, user_id=target_id)
    await dp.fsm.storage.set_state(key=user_key, state=None)

    await callback.message.edit_text(f"{callback.message.text}\n\n✅ **ОДОБРЕНО**", parse_mode="Markdown")

    try:
        await bot.send_photo(
            chat_id=target_id,
            photo=WELCOME_IMAGE_URL,
            caption=(
                "🏎️ **ДОБРО ПОЖАЛОВАТЬ В SQUAD 911!**\n\n"
                "Ваш аккаунт успешно верифицирован!\n"
                "Выберите валютную пару ниже, чтобы получить сигнал:"
            ),
            reply_markup=get_pairs_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await database.set_approve_status(target_id, False)

    user_key = StorageKey(bot_id=bot.id, chat_id=target_id, user_id=target_id)
    await dp.fsm.storage.set_state(key=user_key, state=None)

    await callback.message.edit_text(f"{callback.message.text}\n\n❌ **ОТКЛОНЕНО**", parse_mode="Markdown")

    try:
        await bot.send_message(
            chat_id=target_id,
            text="❌ Ваш ID не найден в системе. Проверьте правильность регистрации и отправьте /start снова."
        )
    except Exception:
        pass

# --- Выдача сигнала и опрос ---

@dp.message(F.text.in_(config.PAIR_MAP.keys()))
async def send_signal(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await database.is_user_approved(user_id):
        await message.answer("🔒 У вас нет доступа. Введите /start для верификации.")
        return

    await state.clear()

    pair_name = message.text
    symbol = config.PAIR_MAP[pair_name]

    msg = await message.answer(f"🔍 Сканирование рынка TradingView для пары **{pair_name}**...", parse_mode="Markdown")
    await asyncio.sleep(1.2)

    data = get_tv_signal(symbol)

    signal_text = (
        f"📊 **СИГНАЛ SQUAD 911 AI**\n"
        f"───────────────────\n"
        f"🔀 **Валютная пара:** {pair_name}\n"
        f"📈 **Направление:** {data['direction']}\n"
        f"⏱ **Время экспирации:** 1–3 минуты\n"
        f"🎯 **Уверенность алгоритма:** {data['confidence']}%\n"
        f"───────────────────\n"
        f"⏳ *Сигнал действителен 60 секунд. Соблюдайте RM!*"
    )

    await msg.edit_text(signal_text, parse_mode="Markdown")

    # Пауза перед опросом фидбека (60 сек)
    await asyncio.sleep(60)

    feedback_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Плюс (+)", callback_data="trade_win"),
            InlineKeyboardButton(text="🔴 Минус (-)", callback_data="trade_loss")
        ]
    ])

    await message.answer(
        f"⏱ **Время экспирации по {pair_name} прошло!**\n\n"
        f"Как закрылась ваша сделка?",
        reply_markup=feedback_keyboard,
        parse_mode="Markdown"
    )

# --- Фидбек по сделке ---

@dp.callback_query(F.data == "trade_win")
async def process_win(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔥 **Отличный результат!** Сигнал отработал успешно.\n\n"
        "Выбирай следующую пару и продолжай в том же духе! 🚀",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "trade_loss")
async def process_loss(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📉 **Не переживай!** Рыночные шумы иногда случаются.\n\n"
        "Соблюдай мани-менеджмент, перекрой сделку по следующему сигналу! 🧠",
        parse_mode="Markdown"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
