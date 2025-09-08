"""Telegram Bot initialization and configuration with security hardening."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage

from ..config import settings
from .handlers import (
    start_router,
    search_router,
    payment_router,
    referral_router,
    menu_router,
    image_extraction_router
)

logger = logging.getLogger(__name__)

# Constants
WEBHOOK_TIMEOUT: int = 30
BOT_REQUEST_TIMEOUT: int = 60
MAX_RETRIES: int = 3


def create_bot() -> Bot:
    """Create and configure Telegram bot with secure settings."""
    if not settings.bot_token:
        raise ValueError("Bot token is required")

    # Secure bot configuration - using only supported parameters
    bot_config = DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    )

    bot = Bot(
        token=settings.bot_token,
        default=bot_config
    )

    logger.info("Telegram bot instance created")
    return bot


def create_dispatcher(use_fallback: bool = False, redis_client: Optional[object] = None) -> Dispatcher:
    """Create and configure bot dispatcher with appropriate storage."""

    # Use Redis storage in production for persistence, Memory storage in development
    if settings.is_production and redis_client:
        try:
            storage = RedisStorage(
                redis=redis_client,
                key_builder=lambda *args, **kwargs: f"bot_fsm:{':'.join(str(arg) for arg in args)}"
            )
            logger.info("Using Redis storage for bot state persistence")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis storage, falling back to memory: {e}")
            storage = MemoryStorage()
    else:
        storage = MemoryStorage()
        if settings.is_production:
            logger.warning("Using MemoryStorage in production - state will not persist across restarts")

    dispatcher = Dispatcher(storage=storage)

    # Configure dispatcher with security settings
    dispatcher.update.middleware(lambda handler, event, data: handler(event, data))

    # Include routers based on configuration
    if use_fallback:
        try:
            from .handlers import fallback
            dispatcher.include_router(fallback.router)
            logger.info("Bot dispatcher configured with fallback handlers")
        except ImportError as e:
            logger.error(f"Failed to load fallback handlers: {e}")
            raise
    else:
        routers = [
            start_router,
            menu_router,
            search_router,
            payment_router,
            referral_router,
            image_extraction_router
        ]

        for router in routers:
            try:
                dispatcher.include_router(router)
                logger.debug(f"Included router: {router.name or 'unnamed'}")
            except Exception as e:
                logger.error(f"Failed to include router {router}: {e}")
                raise

        logger.info("Bot dispatcher configured with full handlers")

    return dispatcher


async def setup_bot_webhook(bot: Bot, max_retries: int = MAX_RETRIES) -> None:
    """Setup Telegram webhook with retry logic and security validation."""

    if not settings.webhook_url:
        raise ValueError("Webhook URL is required")

    # Validate webhook URL format
    if settings.is_production and not settings.webhook_url.startswith("https://"):
        raise ValueError("Production webhook URL must use HTTPS")

    webhook_url = settings.webhook_url
    secret_token = settings.webhook_secret

    # Security: Validate secret token
    if not secret_token or len(secret_token) < 32:
        raise ValueError("Webhook secret token must be at least 32 characters long")

    # Define allowed update types for security
    allowed_updates = [
        "message",
        "callback_query",
        "inline_query",
        "chat_member",
        "my_chat_member"
    ]

    for attempt in range(max_retries):
        try:
            logger.info(f"Setting up webhook (attempt {attempt + 1}/{max_retries})")

            await bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token,
                drop_pending_updates=True,
                allowed_updates=allowed_updates,
                request_timeout=WEBHOOK_TIMEOUT
            )

            # Verify webhook was set correctly
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url == webhook_url:
                logger.info(f"Webhook successfully configured: {webhook_url}")
                return
            else:
                logger.warning(f"Webhook verification failed. Expected: {webhook_url}, Got: {webhook_info.url}")
                if attempt == max_retries - 1:
                    raise RuntimeError("Webhook verification failed")

        except Exception as error:
            logger.warning(f"Webhook setup attempt {attempt + 1} failed: {error}")

            if attempt < max_retries - 1:
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to setup webhook after {max_retries} attempts")
                raise


async def remove_bot_webhook(bot: Bot) -> None:
    """Remove Telegram webhook safely."""
    try:
        await bot.delete_webhook(
            drop_pending_updates=True,
            request_timeout=WEBHOOK_TIMEOUT
        )
        logger.info("Webhook successfully removed")
    except Exception as error:
        logger.error(f"Failed to remove webhook: {error}")
        # Don't raise here as this is cleanup code


async def close_bot(bot: Bot) -> None:
    """Close bot session and cleanup resources."""
    try:
        if bot.session:
            await bot.session.close()
        logger.info("Bot session closed successfully")
    except Exception as error:
        logger.error(f"Error closing bot session: {error}")


async def validate_bot_token(bot: Bot) -> bool:
    """Validate bot token by making a test API call."""
    try:
        bot_info = await bot.get_me()
        logger.info(f"Bot token validated. Bot username: @{bot_info.username}")
        return True
    except Exception as e:
        logger.error(f"Bot token validation failed: {e}")
        return False
