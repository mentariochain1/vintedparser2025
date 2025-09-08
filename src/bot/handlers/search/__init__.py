"""Search handlers package: exposes the main search router and states."""

from aiogram import Router

# Re-export SearchStates from dedicated module
from .search_states import SearchStates

# Create main search router, will be included by the dispatcher
router = Router()

__all__ = ["router", "SearchStates"]
