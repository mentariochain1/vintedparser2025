import logging
from aiogram import types
from src.bot.services.payment_service import PaymentService
from src.bot.services.user_service import UserService
from src.config import settings
from .keyboards import create_payment_keyboard, create_subscription_keyboard
from src.validation import PaymentInput, validate_input
from decimal import Decimal
from src.exceptions import ValidationError
from src.error_handlers import error_handler

logger = logging.getLogger(__name__)
payment_service = PaymentService()
user_service = UserService()

def handle_plan_selection(callback_data: str) -> tuple[int, str, dict]:
    if callback_data == "pay_monthly":
        days = 30
        description = "Премиум на месяц"
    elif callback_data == "pay_quarterly":
        days = 90
        description = "Премиум на 3 месяца"
    elif callback_data == "pay_yearly":
        days = 365
        description = "Премиум на год"
    else:
        raise ValueError(f"Invalid payment plan: {callback_data}")
    
    pricing = payment_service.calculate_subscription_price(days)
    return days, description, pricing

def create_confirmation_message(description: str, days: int, pricing: dict) -> str:
    discount_text = ""
    if pricing["discount"] > 0:
        discount_text = f"\n🎉 **Скидка**: {pricing['discount']*100:.0f}%"
    
    return (
        f"💳 **Подтверждение оплаты**\n\n"
        f"📦 **План**: {description}\n"
        f"⏱️ **Длительность**: {days} дн.\n"
        f"💰 **Стоимость**: {pricing['final_price']:.0f} ₽"
        f"{discount_text}\n\n"
        "Нажмите кнопку ниже, чтобы продолжить."
    )

def validate_user_exists(user) -> None:
    if not user:
        raise ValueError("User not found")

def validate_payment_input(user_id: int, amount: float, days: int) -> dict:
    payment_input_data = {
        "user_id": user_id,
        "amount": Decimal(str(amount)),
        "currency": "RUB",
        "description": f"Premium subscription ({days} days)",
    }
    return validate_input(payment_input_data, PaymentInput)

def create_payment_with_service(session, user_id: int, amount: float, days: int) -> dict:
    validated_payment = validate_payment_input(user_id, amount, days)
    
    return payment_service.create_payment(
        session=session,
        user_id=validated_payment.user_id,
        amount=float(validated_payment.amount),
        currency=validated_payment.currency,
        description=validated_payment.description,
        return_url=f"{settings.webhook_domain}/payment/success",
    )

def create_payment_message(payment_data: dict, amount: float, days: int) -> str:
    return (
        f"💳 **Платёж создан**\n\n"
        f"💰 **Сумма**: {amount:.0f} ₽\n"
        f"⏱️ **Длительность**: {days} дн.\n"
        f"🆔 **ID платежа**: `{payment_data['payment_id']}`\n\n"
        f"Нажмите **Оплатить сейчас**, чтобы завершить оплату.\n"
        f"Статус можно проверить в любое время."
    )

async def handle_payment_creation(session, user_id: int, days: int) -> tuple[str, types.InlineKeyboardMarkup]:
    user = await user_service.get_user(session, user_id)
    if not user:
        raise ValueError("User not found")
    
    pricing = payment_service.calculate_subscription_price(days)
    amount = pricing["final_price"]
    payment_data = await create_payment_with_service(session, user.id, amount, days)
    
    text = create_payment_message(payment_data, amount, days)
    keyboard = create_payment_keyboard(payment_data)
    return text, keyboard

async def handle_payment_error(e: Exception, user_id: int, callback: types.CallbackQuery) -> None:
    from src.exceptions import ValidationError
    from src.error_handlers import error_handler
    
    if isinstance(e, ValidationError):
        error_handler.log_error(e, {"user_id": user_id, "handler": "payment_creation"})
        message = error_handler.get_user_friendly_message(e)
        await callback.message.edit_text(message)
    else:
        logger.error(f"Failed to create payment for user {user_id}: {e}")
        keyboard = create_subscription_keyboard()
        await callback.message.edit_text(
            "❌ Не удалось создать платёж. Попробуйте позже или выберите другой план:",
            reply_markup=keyboard
        )

def validate_payment_ownership(payment_status: dict, user_id: int) -> bool:
    if not payment_status:
        return False
    
    metadata = payment_status.get("metadata", {})
    return str(user_id) == metadata.get("user_id")

def get_status_emoji_and_text(status: str) -> tuple[str, str]:
    status_mapping = {
        "succeeded": ("✅", "Оплата прошла"),
        "pending": ("⏳", "Оплата в обработке"),
        "canceled": ("❌", "Платёж отменён"),
    }
    
    if status in status_mapping:
        return status_mapping[status]
    else:
        return ("❓", f"Статус: {status.title()}")

def create_status_message(status: str, amount: float, currency: str, payment_id: str) -> str:
    status_emoji, status_text = get_status_emoji_and_text(status)
    
    base_text = (
        f"{status_emoji} **{status_text}**\n\n"
        f"💰 **Сумма**: {amount} {currency}\n"
        f"🆔 **ID платежа**: `{payment_id}`\n\n"
    )
    
    if status == "succeeded":
        additional_text = (
            f"🎉 Подписка активирована!\n"
            f"Используйте /start, чтобы увидеть обновлённый статус."
        )
    elif status == "pending":
        additional_text = (
            f"⏳ Платёж обрабатывается.\n"
            f"Мы уведомим, когда всё будет готово."
        )
    elif status == "canceled":
        additional_text = (
            f"❌ Этот платёж был отменён.\n"
            f"Используйте /pay, чтобы создать новый платёж."
        )
    else:
        additional_text = f"ℹ️ Статус платежа: {status}"
    
    return base_text + additional_text
