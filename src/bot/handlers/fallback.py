"""Fallback handlers when database is unavailable."""

from aiogram import Router, types, F
from aiogram.filters import CommandStart

from bot.keyboards import ReplyKeyboards

router = Router()

@router.message(CommandStart())
async def fallback_start_handler(message: types.Message) -> None:
    """Handle /start command when database is unavailable."""
    first_name = message.from_user.first_name or "друг"
    
    welcome_text = (
        f"🎉 Добро пожаловать в Vinted Parser Bot, {first_name}!\n\n"
        f"⚠️ Сервис временно работает в ограниченном режиме.\n"
        f"База данных недоступна, но вы можете:\n\n"
        f"🔍 Попробовать поиск (без сохранения истории)\n"
        f"💎 Узнать о премиум функциях\n"
        f"📞 Связаться с поддержкой\n\n"
        f"Мы работаем над восстановлением полного функционала!"
    )
    
    await message.answer(welcome_text, reply_markup=ReplyKeyboards.main_menu())

@router.message(F.text == "📊 Статус")
async def fallback_status_handler(message: types.Message) -> None:
    """Handle status button when database is unavailable."""
    await message.answer(
        "⚠️ **Статус сервиса**\n\n"
        "🔧 База данных временно недоступна\n"
        "⏳ Работаем над восстановлением\n"
        "📞 Обратитесь в поддержку для помощи",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboards.main_menu()
    )

@router.message(F.text == "👥 Реферал")
async def fallback_referral_handler(message: types.Message) -> None:
    """Handle referral button when database is unavailable."""
    await message.answer(
        "⚠️ **Реферальная система**\n\n"
        "🔧 Функция временно недоступна\n"
        "💾 База данных восстанавливается\n"
        "🔄 Попробуйте позже",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboards.main_menu()
    )

@router.message(F.text == "💎 Премиум")
async def fallback_premium_handler(message: types.Message) -> None:
    """Handle premium button when database is unavailable."""
    await message.answer(
        "💎 **Премиум подписка**\n\n"
        "⚠️ Система подписок временно недоступна\n"
        "🔧 База данных восстанавливается\n\n"
        "📞 Свяжитесь с поддержкой для оформления премиума",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboards.main_menu()
    )

@router.message(F.text == "🔍 Поиск")
async def fallback_search_handler(message: types.Message) -> None:
    """Handle search button when database is unavailable."""
    await message.answer(
        "🔍 Готов к поиску.\n\n"
        "Просто напиши, что найти. Например: <code>кроссовки Nike</code> или <code>винтажная куртка</code>.\n\n"
        "ℹ️ Сервис работает в упрощённом режиме — поиск доступен, но история не сохраняется."
    )

# Add callback handlers for fallback mode
@router.callback_query(F.data.startswith("item_count:"))
async def fallback_item_count_callback(callback: types.CallbackQuery) -> None:
    """Handle item count selection in fallback mode."""
    await callback.answer("⚠️ Поиск временно недоступен из-за проблем с базой данных", show_alert=True)

# Removed test callback used in fallback mode

@router.message(F.text == "🏠 Главное меню")
async def fallback_main_menu_handler(message: types.Message) -> None:
    """Handle main menu button when database is unavailable."""
    await message.answer(
        "🏠 **Главное меню**\n\n"
        "⚠️ Сервис работает в ограниченном режиме\n"
        "🔧 База данных восстанавливается",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboards.main_menu()
    )

@router.message()
async def fallback_any_message_handler(message: types.Message) -> None:
    """Handle any other message when database is unavailable."""
    await message.answer(
        "⚠️ Сервис работает в ограниченном режиме\n\n"
        "🔧 База данных недоступна, мы уже чиним\n"
        "🔍 Поиск товаров доступен без ограничений\n"
        "📞 Нужна помощь? Напишите в поддержку",
        reply_markup=ReplyKeyboards.main_menu()
    )