import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from .handlers import (
    start_router,
    search_router,
    payment_router,
    referral_router,
    menu_router
)

logger = logging.getLogger(__name__)

def create_bot() -> Bot:
    bot_config = DefaultBotProperties(parse_mode=ParseMode.HTML)
    return Bot(
        token=settings.bot_token,
        default=bot_config
    )

async def check_database_availability() -> bool:
    try:
        from db.base import get_db_session
        from sqlalchemy import text
        
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False

def create_dispatcher(use_fallback: bool = False) -> Dispatcher:
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    if use_fallback:
        from bot.handlers import fallback
        dispatcher.include_router(fallback.router)
        logger.info("Bot dispatcher configured with fallback handlers")
    else:
        routers = [
            start_router,
            menu_router,
            search_router,
            payment_router,
            referral_router
        ]
        for router in routers:
            dispatcher.include_router(router)
        logger.info("Bot dispatcher configured with full handlers")
    
    return dispatcher

async def setup_bot_webhook(bot: Bot) -> None:
    webhook_url = settings.webhook_url
    
    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query", "chat_member", "my_chat_member"]
        )
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as error:
        logger.error(f"Failed to set webhook: {error}")
        raise

async def remove_bot_webhook(bot: Bot) -> None:
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook removed")
    except Exception as error:
        logger.error(f"Failed to remove webhook: {error}")

async def close_bot(bot: Bot) -> None:
    try:
        await bot.session.close()
        logger.info("Bot session closed")
    except Exception as error:
        logger.error(f"Error closing bot session: {error}")
