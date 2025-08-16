"""Integration tests for search functionality."""

import pytest
from unittest .mock import AsyncMock ,MagicMock ,patch
from datetime import datetime ,timedelta

from aiogram import Bot ,Dispatcher
from aiogram .fsm .storage .memory import MemoryStorage
from aiogram .types import User ,Chat ,Message ,CallbackQuery

from src .bot .handlers .search import router as search_router
from src .bot .services .user_service import UserService

class TestSearchIntegration :
    """Integration tests for search functionality."""

    @pytest .fixture
    def bot (self ):
        """Create mock bot."""
        return MagicMock (spec =Bot )

    @pytest .fixture
    def dp (self ):
        """Create dispatcher with search router."""
        storage =MemoryStorage ()
        dp =Dispatcher (storage =storage )
        dp .include_router (search_router )
        return dp

    @pytest .fixture
    def mock_user_service (self ):
        """Mock user service."""
        with patch ('src.bot.handlers.search.user_service')as mock :
            yield mock

    @pytest .fixture
    def mock_db_session (self ):
        """Mock database session."""
        with patch ('src.bot.handlers.search.get_db_session')as mock :
            session =AsyncMock ()
            mock .return_value .__aenter__ .return_value =session
            yield session

    @pytest .fixture
    def mock_search_task_manager (self ):
        """Mock search task manager."""
        with patch ('src.bot.handlers.search.search_task_manager')as mock :
            mock .queue_search_task .return_value ="search123"
            mock .is_search_complete .return_value =False
            yield mock

    def create_message (self ,text :str ,user_id :int =12345 )->Message :
        """Create a mock message."""
        user =User (id =user_id ,is_bot =False ,first_name ="Test",username ="testuser")
        chat =Chat (id =67890 ,type ="private")

        message =MagicMock (spec =Message )
        message .text =text
        message .from_user =user
        message .chat =chat
        message .message_id =999
        message .answer =AsyncMock ()

        return message

    def create_callback_query (self ,data :str ,user_id :int =12345 )->CallbackQuery :
        """Create a mock callback query."""
        user =User (id =user_id ,is_bot =False ,first_name ="Test",username ="testuser")

        callback =MagicMock (spec =CallbackQuery )
        callback .data =data
        callback .from_user =user
        callback .answer =AsyncMock ()
        callback .message =MagicMock ()
        callback .message .edit_text =AsyncMock ()
        callback .message .edit_media =AsyncMock ()

        return callback

    @pytest .mark .asyncio
    async def test_search_command_flow_with_premium (
    self ,
    bot ,
    dp ,
    mock_user_service ,
    mock_db_session
    ):
        """Test complete search command flow with premium user."""

        mock_user_service .is_premium_active .return_value =True

        message =self .create_message ("/search")

        await dp .feed_update (bot ,self ._create_update_with_message (message ))

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "What would you like to search for"in call_args

    @pytest .mark .asyncio
    async def test_search_command_flow_without_premium (
    self ,
    bot ,
    dp ,
    mock_user_service ,
    mock_db_session
    ):
        """Test search command flow without premium access."""

        mock_user_service .is_premium_active .return_value =False

        mock_user =MagicMock ()
        mock_user .trial_expires =datetime .utcnow ()-timedelta (days =1 )
        mock_user .subscription_expires =None
        mock_user .referrals_count =0
        mock_user_service .get_user .return_value =mock_user
        mock_user_service .referral_bonus_days =3

        message =self .create_message ("/search")

        await dp .feed_update (bot ,self ._create_update_with_message (message ))

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args
        assert "trial expired"in call_args [0 ][0 ]
        assert call_args [1 ]['reply_markup']is not None

    @pytest .mark .asyncio
    async def test_search_query_processing (
    self ,
    bot ,
    dp ,
    mock_search_task_manager
    ):
        """Test search query processing."""

        message =self .create_message ("Nike sneakers")

        mock_search_msg =MagicMock ()
        mock_search_msg .message_id =999
        message .answer .return_value =mock_search_msg

        with patch ('asyncio.sleep'),patch ('asyncio.create_task'):

            from src .bot .handlers .search import process_search_query
            from aiogram .fsm .context import FSMContext

            state =AsyncMock (spec =FSMContext )
            await process_search_query (message ,state )

        state .clear .assert_called_once ()

        mock_search_task_manager .queue_search_task .assert_called_once ()
        call_kwargs =mock_search_task_manager .queue_search_task .call_args [1 ]
        assert call_kwargs ['query']=="Nike sneakers"
        assert call_kwargs ['user_id']==12345

    @pytest .mark .asyncio
    async def test_item_detail_callback (
    self ,
    bot ,
    dp ,
    mock_db_session
    ):
        """Test item detail callback handling."""

        with patch ('src.bot.handlers.search.ItemCRUD')as mock_item_crud ,patch ('src.bot.handlers.search.PhotoCRUD')as mock_photo_crud :

            mock_item =MagicMock ()
            mock_item .id =123
            mock_item .title ="Test Item"
            mock_item .price =25.99
            mock_item .currency ="EUR"
            mock_item .brand ="Nike"
            mock_item .size ="M"
            mock_item .condition ="Good"
            mock_item .description ="Test description"
            mock_item .url ="https://vinted.at/items/123"

            mock_item_crud .get_by_id .return_value =mock_item

            mock_photo =MagicMock ()
            mock_photo .url ="https://example.com/photo1.jpg"
            mock_photo .order_no =0
            mock_photo_crud .get_by_item_id .return_value =[mock_photo ]

            callback =self .create_callback_query ("item_detail:123")

            await dp .feed_update (bot ,self ._create_update_with_callback (callback ))

            mock_item_crud .get_by_id .assert_called_once_with (mock_db_session ,123 )
            mock_photo_crud .get_by_item_id .assert_called_once_with (mock_db_session ,123 )

            callback .message .edit_media .assert_called_once ()
            callback .answer .assert_called_once ()

    @pytest .mark .asyncio
    async def test_new_search_callback_with_premium (
    self ,
    bot ,
    dp ,
    mock_user_service ,
    mock_db_session
    ):
        """Test new search callback with premium access."""

        mock_user_service .is_premium_active .return_value =True

        callback =self .create_callback_query ("new_search")

        await dp .feed_update (bot ,self ._create_update_with_callback (callback ))

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )

        callback .message .edit_text .assert_called_once ()
        call_args =callback .message .edit_text .call_args [0 ][0 ]
        assert "What would you like to search for"in call_args

        callback .answer .assert_called_once ()

    def _create_update_with_message (self ,message :Message ):
        """Create update with message."""
        from aiogram .types import Update

        return Update (
        update_id =1 ,
        message =message
        )

    def _create_update_with_callback (self ,callback :CallbackQuery ):
        """Create update with callback query."""
        from aiogram .types import Update

        return Update (
        update_id =1 ,
        callback_query =callback
        )