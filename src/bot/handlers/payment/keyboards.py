from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.bot.services.payment_service import PaymentService

payment_service = PaymentService()

def create_confirmation_keyboard(days: int, final_price: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💳 Оплатить {final_price:.0f} ₽",
                    callback_data=f"confirm_pay_{days}",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="pay_cancel")],
        ]
    )

def create_payment_keyboard(payment_data: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить сейчас",
                    url=payment_data["confirmation_url"],
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Проверить статус",
                    callback_data=f"check_payment_{payment_data['payment_id']}",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="pay_cancel")],
        ]
    )

def create_status_keyboard(status: str, payment_id: str) -> InlineKeyboardMarkup:
    if status in ["pending", "waiting_for_capture"]:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить статус",
                        callback_data=f"check_payment_{payment_id}",
                    )
                ],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="pay_cancel")],
            ]
        )
    else:
        return create_subscription_keyboard()

def create_status_action_keyboard(has_active_subscription: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay_monthly")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="pay_cancel")],
        ]
    )

def create_subscription_keyboard() -> InlineKeyboardMarkup:
    monthly = payment_service.calculate_subscription_price(30)
    quarterly = payment_service.calculate_subscription_price(90)
    yearly = payment_service.calculate_subscription_price(365)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Выбрать на месяц · {monthly['final_price']:.0f} ₽",
                    callback_data="pay_monthly",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Выбрать на 3 месяца · {quarterly['final_price']:.0f} ₽ (−10%)",
                    callback_data="pay_quarterly",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Выбрать на год · {yearly['final_price']:.0f} ₽ (−20%)",
                    callback_data="pay_yearly",
                )
            ],
            [InlineKeyboardButton(text="📊 Мой статус", callback_data="pay_status")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="pay_cancel")],
        ]
    )

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    return create_subscription_keyboard()
