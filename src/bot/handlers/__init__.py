"""Bot handlers package."""

from .start import router as start_router
from .search_module import router as search_router
from .payment_handlers import router as payment_router
from .referral import router as referral_router
from .menu import router as menu_router
from .image_extraction_handlers import router as image_extraction_router
from . import fallback

__all__ = ["start_router", "search_router", "payment_router", "referral_router", "menu_router", "image_extraction_router", "fallback"]