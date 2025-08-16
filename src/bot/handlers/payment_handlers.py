import logging
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.payment_service import PaymentService
from bot.services.user_service import UserService
from db.base import get_db_session
from .payment.status_formatters import (
    build_payment_status_message,
    get_user_status_info,
    build_detailed_status_text,
    build_subscription_status_text
)
from .payment.keyboards import (
    create_subscription_keyboard,
    create_confirmation_keyboard,
    create_status_keyboard,
    create_status_action_keyboard
)
from .payment.payment_utils import (
    handle_plan_selection,
    create_confirmation_message,
    handle_payment_creation,
    handle_payment_error,
    validate_payment_ownership,
    create_status_message
)

logger = logging.getLogger(__name__)
router = Router()
payment_service = PaymentService()
user_service = UserService()

async def validate_user_exists(session, user_id: int):
    user = await user_service.get_user(session, user_id)
    if not user:
        return None
    return user

async def send_account_not_found_message(message: types.Message):
    await message.answer("❌ Сначала используйте /start, чтобы создать аккаунт.")

async def send_payment_interface(message: types.Message, user, first_name: str):
    status_text = build_payment_status_message(user, first_name)
    keyboard = create_subscription_keyboard()
    await message.answer(status_text, reply_markup=keyboard, parse_mode="Markdown")

@router.message(Command("pay"))
async def payment_command(message: types.Message) -> None:
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"
    
    async with get_db_session() as session:
        user = await validate_user_exists(session, user_id)
        if not user:
            await send_account_not_found_message(message)
            return
        await send_payment_interface(message, user, first_name)

async def process_plan_confirmation(callback: types.CallbackQuery, data: str):
    days, description, pricing = handle_plan_selection(data)
    confirmation_text = create_confirmation_message(description, days, pricing)
    confirm_keyboard = create_confirmation_keyboard(days, pricing['final_price'])
    await callback.message.edit_text(confirmation_text, reply_markup=confirm_keyboard, parse_mode="Markdown")

async def handle_status_request(callback: types.CallbackQuery):
    await show_payment_status(callback)

async def handle_payment_cancellation(callback: types.CallbackQuery):
    keyboard = create_subscription_keyboard()
    await callback.message.edit_text("❌ Оплата отменена. Выберите план, чтобы продолжить:", reply_markup=keyboard)

async def handle_plan_selection_request(callback: types.CallbackQuery, data: str):
    try:
        await process_plan_confirmation(callback, data)
    except ValueError:
        await callback.message.edit_text("❌ Неверный вариант оплаты.")

@router.callback_query(F.data.startswith("pay_"))
async def handle_payment_callback(callback: types.CallbackQuery) -> None:
    await callback.answer()
    data = callback.data

    if data == "pay_status":
        await handle_status_request(callback)
    elif data == "pay_cancel":
        await handle_payment_cancellation(callback)
    else:
        await handle_plan_selection_request(callback, data)

async def extract_days_from_callback(callback_data: str) -> int:
    return int(callback_data.split("_")[-1])

async def process_payment_creation(session, user_id: int, days: int, callback: types.CallbackQuery):
    text, keyboard = await handle_payment_creation(session, user_id, days)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def handle_user_not_found_error(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Пользователь не найден. Сначала используйте /start.")

@router.callback_query(F.data.startswith("confirm_pay_"))
async def handle_payment_confirmation(callback: types.CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    days = extract_days_from_callback(callback.data)

    async with get_db_session() as session:
        try:
            await process_payment_creation(session, user_id, days, callback)
        except ValueError:
            await handle_user_not_found_error(callback)
        except Exception as e:
            await handle_payment_error(e, user_id, callback)

async def extract_payment_id(callback_data: str) -> str:
    return callback_data.split("_", 2)[-1]

async def validate_payment_access(payment_status, user_id: int, callback: types.CallbackQuery) -> bool:
    if not validate_payment_ownership(payment_status, user_id):
        await callback.answer("❌ Платёж не найден.", show_alert=True)
        return False
    return True

async def update_payment_status_display(payment_status, payment_id: str, callback: types.CallbackQuery):
    status, amount, currency = payment_status["status"], payment_status["amount"], payment_status["currency"]
    text = create_status_message(status, amount, currency, payment_id)
    keyboard = create_status_keyboard(status, payment_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def handle_payment_status_error(e: Exception, payment_id: str, callback: types.CallbackQuery):
    logger.error(f"Failed to check payment status {payment_id}: {e}")
    await callback.answer("❌ Не удалось проверить статус платежа.", show_alert=True)

@router.callback_query(F.data.startswith("check_payment_"))
async def handle_payment_status_check(callback: types.CallbackQuery) -> None:
    await callback.answer()
    payment_id = extract_payment_id(callback.data)
    user_id = callback.from_user.id

    try:
        payment_status = await payment_service.get_payment_status(payment_id)
        if not await validate_payment_access(payment_status, user_id, callback):
            return
        await update_payment_status_display(payment_status, payment_id, callback)
    except Exception as e:
        await handle_payment_status_error(e, payment_id, callback)

async def send_user_not_found_message(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Пользователь не найден. Сначала используйте /start.")

async def display_user_status(user, callback: types.CallbackQuery):
    status_info = get_user_status_info(user)
    status_text = build_detailed_status_text(user, status_info)
    keyboard = create_status_action_keyboard(status_info['subscription_active'])
    await callback.message.edit_text(status_text, reply_markup=keyboard, parse_mode="Markdown")

async def show_payment_status(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id

    async with get_db_session() as session:
        user = await validate_user_exists(session, user_id)
        if not user:
            await send_user_not_found_message(callback)
            return
        await display_user_status(user, callback)

async def create_subscription_interface_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay_monthly")]]
    )

async def send_subscription_status(user, message: types.Message):
    status_info = get_user_status_info(user)
    status_text = build_subscription_status_text(user, status_info)
    keyboard = create_subscription_interface_keyboard()
    await message.answer(status_text, reply_markup=keyboard, parse_mode="Markdown")

@router.message(Command("subscription", "sub"))
async def subscription_status_command(message: types.Message) -> None:
    user_id = message.from_user.id

    async with get_db_session() as session:
        user = await validate_user_exists(session, user_id)
        if not user:
            await send_account_not_found_message(message)
            return
        await send_subscription_status(user, message)

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    return create_subscription_keyboard()
