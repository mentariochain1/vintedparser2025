"""Integration tests for start handler with router."""

import pytest
from aiogram import Dispatcher

from src .bot .handlers .start import router

class TestStartHandlerIntegration :
    """Integration tests for start handler."""

    @pytest .mark .asyncio
    async def test_router_exists (self ):
        """Test that router exists and can be imported."""
        assert router is not None
        assert hasattr (router ,'message')

    @pytest .mark .asyncio
    async def test_router_integration (self ):
        """Test that router can be integrated with dispatcher."""
        dp =Dispatcher ()
        dp .include_router (router )

        assert router in dp .sub_routers 