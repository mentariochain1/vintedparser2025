"""Menu handlers for reply keyboard navigation."""

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.services.user_service import UserService
from src.bot.keyboards import ReplyKeyboards
from src.db.base import get_db_session
from src.bot.services.search_metrics import search_metrics
from src.bot.handlers.search import SearchStates

async def _get_user_safely(user_id: int, message: types.Message):
    """Get user with database error handling."""
    try:
        # Try SQLAlchemy first
        async with get_db_session() as session:
            return await user_service.get_user(session, user_id)
    except Exception as e:
        # Fall back to asyncpg
        try:
            from src.bot.services.user_service_asyncpg import user_service_asyncpg
            user_data = await user_service_asyncpg.get_user_asyncpg(user_id)
            if user_data:
                # Convert dict to object-like structure for compatibility
                class UserData:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                return UserData(user_data)
            return None
        except Exception as asyncpg_error:
            # Supabase REST fallback removed; proceed with limited mode

            await message.answer(
                "⚠️ Сервис временно недоступен. Попробуйте позже.",
                reply_markup=ReplyKeyboards.main_menu()
            )
            return None

router = Router()
user_service = UserService()

@router.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: types.Message) -> None:
    """Handle main menu button press."""
    await message.answer(
        "🏠 Главное меню\n\nЧем я могу помочь?",
        reply_markup=ReplyKeyboards.main_menu()
    )

@router.message(F.text == "📊 Статус")
async def status_handler(message: types.Message) -> None:
    """Handle status button press."""
    user_id = message.from_user.id
    
    user = await _get_user_safely(user_id, message)
    if not user:
        return
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    # Get attributes (works for both SQLAlchemy objects and dict-like objects)
    trial_expires = getattr(user, 'trial_expires', None)
    subscription_expires = getattr(user, 'subscription_expires', None)
    
    trial_active = trial_expires and trial_expires > now
    subscription_active = subscription_expires and subscription_expires > now
    
    # Build base status text by state
    if subscription_active:
        status_text = (
            f"💎 **Премиум активен**\n\n"
            f"Действует до {subscription_expires.strftime('%d.%m.%Y')}\n\n"
            f"Все функции доступны."
        )
    elif trial_active:
        status_text = (
            f"✨ **Пробный период**\n\n"
            f"Доступ до {trial_expires.strftime('%d.%m.%Y')}\n\n"
            f"Оформите Премиум, чтобы получить полный доступ."
        )
    else:
        ended = trial_expires.strftime('%d.%m.%Y') if trial_expires else 'неизвестно'
        status_text = (
            f"⏰ **Доступ истёк**\n\n"
            f"Пробный закончился {ended}\n\n"
            f"Оформите Премиум, чтобы вернуться к поиску."
        )

    # Append lightweight usage metric if available
    try:
        daily_count = search_metrics.get_user_daily_search_count(user_id)
        if daily_count:
            status_text += f"\n\nСегодня вы сделали {daily_count} поиск(а)."
    except Exception:
        pass
    
    await message.answer(
        status_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboards.main_menu()
    )

@router.message(F.text == "👥 Реферал")
async def referral_handler(message: types.Message) -> None:
    """Handle referral button press."""
    user_id = message.from_user.id
    
    user = await _get_user_safely(user_id, message)
    if not user:
        return
    
    # Get bot info to build referral link
    bot_info = await message.bot.get_me()
    
    # Get user ID (works for both SQLAlchemy objects and dict-like objects)
    user_db_id = getattr(user, 'id', user_id) if hasattr(user, 'id') else user_id
    referral_token = user_service.encode_referral_payload(user_db_id)
    referral_link = f"https://t.me/{bot_info.username}?start={referral_token}"
    
    # Get referrals count (works for both object types)
    referrals_count = getattr(user, 'referrals_count', 0)
    
    referral_text = (
        f"👥 **Твоя реферальная ссылка**\n\n"
        f"🔗 `{referral_link}`\n\n"
        f"🎁 **Преимущества:**\n"
        f"• Ты получаешь {user_service.referral_bonus_days} бонусных дней за каждого реферала\n"
        f"• Твои друзья получают {user_service.default_trial_days}-дневный пробный период\n\n"
        f"📊 **Твоя статистика:**\n"
        f"• Успешных рефералов: {referrals_count}\n"
        f"• Заработано бонусных дней: {referrals_count * user_service.referral_bonus_days}"
    )
    
    await message.answer(
        referral_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboards.main_menu()
        )

@router.message(F.text == "💎 Премиум")
async def premium_handler(message: types.Message) -> None:
    """Handle premium button press."""
    # Import here to avoid circular imports
    from src.bot.handlers.payment_handlers import get_subscription_keyboard
    from src.bot.handlers.payment.status_formatters import build_payment_status_message

    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""

    user = await _get_user_safely(user_id, message)
    if not user:
        return

    # Reuse the same UI and text as the /pay command
    status_text = build_payment_status_message(user, first_name)
    keyboard = get_subscription_keyboard()

    await message.answer(
        status_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@router.message(F.text == "🔍 Поиск")
async def search_button_handler(message: types.Message, state: FSMContext) -> None:
    """Handle search button press."""
    # Reset state and set waiting for query so next text is treated as search
    await state.clear()
    await state.set_state(SearchStates.waiting_for_query)

    await message.answer(
        "🔍 Готов к поиску.\n\n"
        "Просто напиши, что найти. Например: <code>кроссовки Nike</code> или <code>винтажная куртка</code>.",
        reply_markup=ReplyKeyboards.search_menu()
    )

@router.message(F.text == "🔍 Новый поиск")
async def new_search_handler(message: types.Message, state: FSMContext) -> None:
    """Handle new search button press."""
    # Reset state and set waiting for query so next text is treated as search
    await state.clear()
    await state.set_state(SearchStates.waiting_for_query)

    await message.answer(
        "🔍 Готов к поиску.\n\n"
        "Просто напиши, что найти. Например: <code>кроссовки Nike</code> или <code>винтажная куртка</code>.",
        reply_markup=ReplyKeyboards.search_menu()
    )