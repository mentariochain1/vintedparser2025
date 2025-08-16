"""Bot handlers package."""

from bot.handlers.start import router as start_router
from bot.handlers.search import router as search_router
from bot.handlers.payment_handlers import router as payment_router
from bot.handlers.referral import router as referral_router
from bot.handlers.menu import router as menu_router
from bot.handlers import fallback

__all__ = ["start_router", "search_router", "payment_router", "referral_router", "menu_router", "fallback"]