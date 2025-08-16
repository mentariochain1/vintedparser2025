"""Tests for search handler functionality."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from aiogram import types
from aiogram .fsm .context import FSMContext
from aiogram_tests import MockedBot
from aiogram_tests .handler import MessageHandler ,CallbackQueryHandler
from aiogram_tests .types .dataset import MESSAGE ,CALLBACK_QUERY

from src .bot .handlers .search import (
search_command ,
process_search_query ,
show_item_detail ,
show_item_photos ,
start_new_search ,
SearchStates ,
_generate_search_id ,
_format_item_detail
)
from src .bot .services .user_service import UserService
from src .db .models import User ,Item ,Photo

class TestSearchCommand :
    """Test search command handler."""

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
    def mock_state (self ):
        """Mock FSM state."""
        state =AsyncMock (spec =FSMContext )
        return state

    @pytest .mark .asyncio
    async def test_search_command_with_premium_user (
    self ,
    mock_user_service ,
    mock_db_session ,
    mock_state
    ):
        """Test search command with premium user."""

        mock_user_service .is_premium_active .return_value =True

        message =MESSAGE .as_object ()
        message .from_user .id =12345

        await search_command (message ,mock_state )

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )
        mock_state .set_state .assert_called_once_with (SearchStates .waiting_for_query )
        message .answer .assert_called_once ()

        call_args =message .answer .call_args [0 ][0 ]
        assert "What would you like to search for"in call_args

    @pytest .mark .asyncio
    async def test_search_command_without_premium (
    self ,
    mock_user_service ,
    mock_db_session ,
    mock_state
    ):
        """Test search command without premium access."""

        mock_user_service .is_premium_active .return_value =False

        mock_user =MagicMock ()
        mock_user .trial_expires =datetime .utcnow ()-timedelta (days =1 )
        mock_user .subscription_expires =None
        mock_user .referrals_count =0
        mock_user_service .get_user .return_value =mock_user
        mock_user_service .referral_bonus_days =3

        message =MESSAGE .as_object ()
        message .from_user .id =12345

        await search_command (message ,mock_state )

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )
        mock_state .set_state .assert_not_called ()
        message .answer .assert_called_once ()

        call_args =message .answer .call_args
        assert "trial expired"in call_args [0 ][0 ]
        assert call_args [1 ]['reply_markup']is not None

class TestSearchQuery :
    """Test search query processing."""

    @pytest .fixture
    def mock_search_task_manager (self ):
        """Mock search task manager."""
        with patch ('src.bot.handlers.search.search_task_manager')as mock :
            mock .queue_search_task .return_value ="search123"
            mock .is_search_complete .return_value =False
            yield mock

    @pytest .fixture
    def mock_state (self ):
        """Mock FSM state."""
        state =AsyncMock (spec =FSMContext )
        return state

    @pytest .mark .asyncio
    async def test_process_valid_search_query (
    self ,
    mock_search_task_manager ,
    mock_state
    ):
        """Test processing valid search query."""
        message =MESSAGE .as_object ()
        message .text ="Nike sneakers"
        message .from_user .id =12345
        message .chat .id =67890

        mock_search_msg =MagicMock ()
        mock_search_msg .message_id =999
        message .answer .return_value =mock_search_msg

        with patch ('asyncio.sleep'),patch ('asyncio.create_task'):
            await process_search_query (message ,mock_state )

        mock_state .clear .assert_called_once ()
        message .answer .assert_called_once ()
        mock_search_task_manager .queue_search_task .assert_called_once ()

        call_kwargs =mock_search_task_manager .queue_search_task .call_args [1 ]
        assert call_kwargs ['query']=="Nike sneakers"
        assert call_kwargs ['user_id']==12345
        assert call_kwargs ['max_pages']==5

    @pytest .mark .asyncio
    async def test_process_empty_search_query (self ,mock_state ):
        """Test processing empty search query."""
        message =MESSAGE .as_object ()
        message .text =""

        await process_search_query (message ,mock_state )

        mock_state .clear .assert_not_called ()
        message .answer .assert_called_once ()

        call_args =message .answer .call_args [0 ][0 ]
        assert "valid search query"in call_args

    @pytest .mark .asyncio
    async def test_process_too_long_search_query (self ,mock_state ):
        """Test processing too long search query."""
        message =MESSAGE .as_object ()
        message .text ="a"*101

        await process_search_query (message ,mock_state )

        mock_state .clear .assert_not_called ()
        message .answer .assert_called_once ()

        call_args =message .answer .call_args [0 ][0 ]
        assert "too long"in call_args

class TestItemDetail :
    """Test item detail display."""

    @pytest .fixture
    def mock_db_session (self ):
        """Mock database session."""
        with patch ('src.bot.handlers.search.get_db_session')as mock :
            session =AsyncMock ()
            mock .return_value .__aenter__ .return_value =session
            yield session

    @pytest .fixture
    def mock_item_crud (self ):
        """Mock ItemCRUD."""
        with patch ('src.bot.handlers.search.ItemCRUD')as mock :
            yield mock

    @pytest .fixture
    def mock_photo_crud (self ):
        """Mock PhotoCRUD."""
        with patch ('src.bot.handlers.search.PhotoCRUD')as mock :
            yield mock

    @pytest .mark .asyncio
    async def test_show_item_detail_with_photos (
    self ,
    mock_db_session ,
    mock_item_crud ,
    mock_photo_crud
    ):
        """Test showing item detail with photos."""

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

        callback =CALLBACK_QUERY .as_object ()
        callback .data ="item_detail:123"
        callback .message .edit_media =AsyncMock ()

        await show_item_detail (callback )

        mock_item_crud .get_by_id .assert_called_once_with (mock_db_session ,123 )
        mock_photo_crud .get_by_item_id .assert_called_once_with (mock_db_session ,123 )
        callback .message .edit_media .assert_called_once ()
        callback .answer .assert_called_once ()

    @pytest .mark .asyncio
    async def test_show_item_detail_not_found (
    self ,
    mock_db_session ,
    mock_item_crud ,
    mock_photo_crud
    ):
        """Test showing item detail when item not found."""

        mock_item_crud .get_by_id .return_value =None

        callback =CALLBACK_QUERY .as_object ()
        callback .data ="item_detail:999"

        await show_item_detail (callback )

        callback .answer .assert_called_once_with ("❌ Item not found",show_alert =True )

class TestItemPhotos :
    """Test item photo navigation."""

    @pytest .fixture
    def mock_db_session (self ):
        """Mock database session."""
        with patch ('src.bot.handlers.search.get_db_session')as mock :
            session =AsyncMock ()
            mock .return_value .__aenter__ .return_value =session
            yield session

    @pytest .fixture
    def mock_item_crud (self ):
        """Mock ItemCRUD."""
        with patch ('src.bot.handlers.search.ItemCRUD')as mock :
            yield mock

    @pytest .fixture
    def mock_photo_crud (self ):
        """Mock PhotoCRUD."""
        with patch ('src.bot.handlers.search.PhotoCRUD')as mock :
            yield mock

    @pytest .mark .asyncio
    async def test_show_item_photos_navigation (
    self ,
    mock_db_session ,
    mock_item_crud ,
    mock_photo_crud
    ):
        """Test photo navigation."""

        mock_item =MagicMock ()
        mock_item .id =123
        mock_item .title ="Test Item"
        mock_item .price =25.99
        mock_item .currency ="EUR"
        mock_item .brand ="Nike"

        mock_item_crud .get_by_id .return_value =mock_item

        mock_photos =[]
        for i in range (3 ):
            photo =MagicMock ()
            photo .url =f"https://example.com/photo{i }.jpg"
            photo .order_no =i
            mock_photos .append (photo )

        mock_photo_crud .get_by_item_id .return_value =mock_photos

        callback =CALLBACK_QUERY .as_object ()
        callback .data ="item_photos:123:1"
        callback .message .edit_media =AsyncMock ()

        await show_item_photos (callback )

        mock_item_crud .get_by_id .assert_called_once_with (mock_db_session ,123 )
        mock_photo_crud .get_by_item_id .assert_called_once_with (mock_db_session ,123 )
        callback .message .edit_media .assert_called_once ()
        callback .answer .assert_called_once ()

class TestNewSearch :
    """Test new search functionality."""

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
    def mock_state (self ):
        """Mock FSM state."""
        state =AsyncMock (spec =FSMContext )
        return state

    @pytest .mark .asyncio
    async def test_start_new_search_with_premium (
    self ,
    mock_user_service ,
    mock_db_session ,
    mock_state
    ):
        """Test starting new search with premium access."""

        mock_user_service .is_premium_active .return_value =True

        callback =CALLBACK_QUERY .as_object ()
        callback .from_user .id =12345
        callback .data ="new_search"

        await start_new_search (callback ,mock_state )

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )
        mock_state .set_state .assert_called_once_with (SearchStates .waiting_for_query )
        callback .message .edit_text .assert_called_once ()
        callback .answer .assert_called_once ()

    @pytest .mark .asyncio
    async def test_start_new_search_without_premium (
    self ,
    mock_user_service ,
    mock_db_session ,
    mock_state
    ):
        """Test starting new search without premium access."""

        mock_user_service .is_premium_active .return_value =False

        callback =CALLBACK_QUERY .as_object ()
        callback .from_user .id =12345
        callback .data ="new_search"

        await start_new_search (callback ,mock_state )

        mock_user_service .is_premium_active .assert_called_once_with (mock_db_session ,12345 )
        mock_state .set_state .assert_not_called ()
        callback .message .edit_text .assert_called_once ()
        callback .answer .assert_called_once ()

        call_args =callback .message .edit_text .call_args [0 ][0 ]
        assert "trial has expired"in call_args

class TestUtilityFunctions :
    """Test utility functions."""

    def test_generate_search_id (self ):
        """Test search ID generation."""
        search_id1 =_generate_search_id (123 ,"test query")
        search_id2 =_generate_search_id (123 ,"test query")
        search_id3 =_generate_search_id (456 ,"test query")

        assert isinstance (search_id1 ,str )
        assert isinstance (search_id2 ,str )
        assert isinstance (search_id3 ,str )

        assert len (search_id1 )==12
        assert len (search_id2 )==12
        assert len (search_id3 )==12

        import time
        time .sleep (0.001 )
        search_id4 =_generate_search_id (123 ,"test query")
        assert search_id1 !=search_id4

        assert search_id1 !=search_id3

    def test_format_item_detail (self ):
        """Test item detail formatting."""
        item ={
        'title':'Test Item',
        'price':25.99 ,
        'currency':'EUR',
        'brand':'Nike',
        'size':'M',
        'condition':'Good',
        'description':'Test description',
        'photos':[{'url':'photo1.jpg'},{'url':'photo2.jpg'}]
        }

        result =_format_item_detail (item )

        assert 'Test Item'in result
        assert '25.99 EUR'in result
        assert 'Nike'in result
        assert 'Size: M'in result
        assert 'Condition: Good'in result
        assert 'Test description'in result
        assert '2 photos available'in result

    def test_format_item_detail_minimal (self ):
        """Test item detail formatting with minimal data."""
        item ={
        'title':'Minimal Item',
        'price':10.0 ,
        'currency':'EUR',
        'photos':[]
        }

        result =_format_item_detail (item )

        assert 'Minimal Item'in result
        assert '10.00 EUR'in result

        assert 'Brand:'not in result
        assert 'Size:'not in result
        assert 'Condition:'not in result
        assert 'photos available'not in result

    def test_format_item_detail_long_description (self ):
        """Test item detail formatting with long description."""
        long_desc ="a"*250
        item ={
        'title':'Item with Long Description',
        'price':15.50 ,
        'currency':'EUR',
        'description':long_desc ,
        'photos':[]
        }

        result =_format_item_detail (item )

        assert long_desc not in result
        assert "aaa..."in result 