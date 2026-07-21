import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

import config
import database
from trading import get_tv_signal

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

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

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    is_approved = await database.is_user_approved(user_id)

    if is_approved:
        await message.answer(
            "🏎️ **Добро пожаловать в SQUAD 911!**\n\n"
            "Твой аккаунт верифицирован. Выбери валютную пару для получения сигнала:",
            reply_markup=get_pairs_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "🤖 **SQUAD 911 | AI Signal Bot**\n\n"
            "Для получения доступа к аналитической панели введите ваш **ID аккаунта Pocket Option** (8 цифр):",
            parse_mode="Markdown"
        )
        await state.set_state(RegisterState.waiting_for_pocket_id)

@dp.message(RegisterState.waiting_for_pocket_id)
async def process_pocket_id(message: types.Message, state: FSMContext):
    pocket_id = message.text.strip()

    if not pocket_id.isdigit() or len(pocket_id) < 5:
        await message.answer("❌ Неверный формат ID. Введите корректный цифровой ID Pocket Option:")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
    await database.add_or_update_user(message.from_user.id, username, pocket_id)
    await state.clear()

    await message.answer(
        "⏳ **Заявка отправлена на проверку!**\n\n"
        "Менеджер проверяет ваш ID. Обычно это занимает от 2 до 15 минут. Вы получите уведомление, как только доступ будет открыт.",
        parse_mode="Markdown"
    )

    admin_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{message.from_user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{message.from_user.id}")
        ]
    ])

    await bot.send_message(
        chat_id=config.ADMIN_ID,
        text=f"📥 **Новая заявка на доступ!**\n\n"
             f"👤 Пользователь: {username} (ID: `{message.from_user.id}`)\n"
             f"🆔 Pocket Option ID: `{pocket_id}`",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await database.set_approve_status(target_id, True)

    await callback.message.edit_text(f"{callback.message.text}\n\n✅ **ОДОБРЕНО**", parse_mode="Markdown")

    try:
        await bot.send_message(
            chat_id=target_id,
            text="🏎️ **Ваш аккаунт успешно верифицирован!**\n\nДоступ к SQUAD 911 AI разблокирован. Выберите валютную пару ниже:",
            reply_markup=get_pairs_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    await database.set_approve_status(target_id, False)

    await callback.message.edit_text(f"{callback.message.text}\n\n❌ **ОТКЛОНЕНО**", parse_mode="Markdown")

    try:
        await bot.send_message(
            chat_id=target_id,
            text="❌ Ваш ID не найден в системе. Проверьте правильность регистрации и отправьте /start снова."
        )
    except Exception:
        pass

@dp.message(F.text.in_(config.PAIR_MAP.keys()))
async def send_signal(message: types.Message):
    user_id = message.from_user.id
    if not await database.is_user_approved(user_id):
        await message.answer("🔒 У вас нет доступа. Введите /start для верификации.")
        return

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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
