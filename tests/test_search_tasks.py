"""Tests for search task management."""

import pytest
import asyncio
from unittest .mock import AsyncMock ,MagicMock ,patch
from datetime import datetime

from src .tasks .search_tasks import SearchTaskManager

class TestSearchTaskManager :
    """Test search task manager functionality."""

    @pytest .fixture
    def task_manager (self ):
        """Create a fresh task manager for each test."""
        return SearchTaskManager ()

    @pytest .fixture
    def mock_vinted_service (self ):
        """Mock Vinted service."""
        with patch ('src.tasks.search_tasks.VintedService')as mock_class :
            mock_service =AsyncMock ()
            mock_class .return_value =mock_service
            yield mock_service

    @pytest .fixture
    def mock_db_session (self ):
        """Mock database session."""
        with patch ('src.tasks.search_tasks.get_db_session')as mock :
            session =AsyncMock ()
            mock .return_value .__aenter__ .return_value =session
            yield session

    @pytest .fixture
    def mock_item_crud (self ):
        """Mock ItemCRUD."""
        with patch ('src.tasks.search_tasks.ItemCRUD')as mock :
            yield mock

    @pytest .fixture
    def mock_photo_crud (self ):
        """Mock PhotoCRUD."""
        with patch ('src.tasks.search_tasks.PhotoCRUD')as mock :
            yield mock

    @pytest .mark .asyncio
    async def test_queue_search_task (self ,task_manager ,mock_vinted_service ):
        """Test queuing a search task."""

        mock_vinted_service .search_and_get_details .return_value =[]

        search_id =await task_manager .queue_search_task (
        search_id ="test123",
        query ="Nike shoes",
        user_id =12345 ,
        max_pages =3
        )

        assert search_id =="test123"
        assert "test123"in task_manager ._active_searches

        await asyncio .sleep (0.1 )

        task =task_manager ._active_searches .get ("test123")
        assert task is not None

    @pytest .mark .asyncio
    async def test_queue_search_task_cancels_existing (self ,task_manager ,mock_vinted_service ):
        """Test that queuing a new task cancels existing one with same ID."""

        mock_vinted_service .search_and_get_details .return_value =[]

        await task_manager .queue_search_task (
        search_id ="test123",
        query ="First query",
        user_id =12345
        )

        first_task =task_manager ._active_searches ["test123"]

        await task_manager .queue_search_task (
        search_id ="test123",
        query ="Second query",
        user_id =12345
        )

        assert first_task .cancelled ()

        second_task =task_manager ._active_searches ["test123"]
        assert second_task !=first_task

    @pytest .mark .asyncio
    async def test_execute_search_task_success (
    self ,
    task_manager ,
    mock_vinted_service ,
    mock_db_session ,
    mock_item_crud ,
    mock_photo_crud
    ):
        """Test successful search task execution."""

        mock_items =[
        {
        'id':123 ,
        'title':'Test Item',
        'price':25.99 ,
        'currency':'EUR',
        'brand':'Nike',
        'url':'https://vinted.at/items/123',
        'photos':[
        {'url':'photo1.jpg','order_no':0 },
        {'url':'photo2.jpg','order_no':1 }
        ]
        }
        ]
        mock_vinted_service .search_and_get_details .return_value =mock_items

        mock_item_crud .get_by_id .return_value =None
        mock_item =MagicMock ()
        mock_item .id =123
        mock_item_crud .create .return_value =mock_item

        await task_manager ._execute_search_task (
        search_id ="test123",
        query ="Nike shoes",
        user_id =12345 ,
        max_pages =3
        )

        mock_vinted_service .search_and_get_details .assert_called_once_with (
        query ="Nike shoes",
        max_pages =3 ,
        per_page =100
        )

        mock_item_crud .create .assert_called_once ()
        create_args =mock_item_crud .create .call_args [1 ]
        assert create_args ['id']==123
        assert create_args ['title']=='Test Item'
        assert create_args ['price']==25.99

        assert mock_photo_crud .create .call_count ==2

        mock_db_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_execute_search_task_update_existing (
    self ,
    task_manager ,
    mock_vinted_service ,
    mock_db_session ,
    mock_item_crud ,
    mock_photo_crud
    ):
        """Test search task execution with existing item update."""

        mock_items =[
        {
        'id':123 ,
        'title':'Updated Item',
        'price':30.99 ,
        'currency':'EUR',
        'photos':[]
        }
        ]
        mock_vinted_service .search_and_get_details .return_value =mock_items

        mock_existing_item =MagicMock ()
        mock_existing_item .id =123
        mock_item_crud .get_by_id .return_value =mock_existing_item

        await task_manager ._execute_search_task (
        search_id ="test123",
        query ="Nike shoes",
        user_id =12345
        )

        mock_item_crud .update .assert_called_once ()
        mock_item_crud .create .assert_not_called ()

        mock_photo_crud .delete_by_item_id .assert_called_once_with (mock_db_session ,123 )

    @pytest .mark .asyncio
    async def test_execute_search_task_no_results (
    self ,
    task_manager ,
    mock_vinted_service
    ):
        """Test search task execution with no results."""

        mock_vinted_service .search_and_get_details .return_value =[]

        await task_manager ._execute_search_task (
        search_id ="test123",
        query ="nonexistent item",
        user_id =12345
        )

    @pytest .mark .asyncio
    async def test_execute_search_task_error_handling (
    self ,
    task_manager ,
    mock_vinted_service
    ):
        """Test search task error handling."""

        mock_vinted_service .search_and_get_details .side_effect =Exception ("API Error")

        await task_manager ._execute_search_task (
        search_id ="test123",
        query ="Nike shoes",
        user_id =12345
        )

        assert "test123"not in task_manager ._active_searches

    @pytest .mark .asyncio
    async def test_get_search_results (
    self ,
    task_manager ,
    mock_db_session ,
    mock_item_crud ,
    mock_photo_crud
    ):
        """Test getting search results."""

        mock_item =MagicMock ()
        mock_item .id =123
        mock_item .title ="Test Item"
        mock_item .price =25.99
        mock_item .currency ="EUR"
        mock_item .brand ="Nike"
        mock_item .size ="M"
        mock_item .condition ="Good"
        mock_item .description ="Test description"
        mock_item .seller_id =456
        mock_item .url ="https://vinted.at/items/123"
        mock_item .preview_img ="preview.jpg"
        mock_item .ships_to_at =True

        mock_item_crud .get_recent .return_value =[mock_item ]

        mock_photo =MagicMock ()
        mock_photo .url ="photo1.jpg"
        mock_photo .order_no =0
        mock_photo_crud .get_by_item_id .return_value =[mock_photo ]

        results =await task_manager .get_search_results ("test123",limit =5 )

        assert len (results )==1
        result =results [0 ]
        assert result ['id']==123
        assert result ['title']=="Test Item"
        assert result ['price']==25.99
        assert result ['currency']=="EUR"
        assert result ['brand']=="Nike"
        assert len (result ['photos'])==1
        assert result ['photos'][0 ]['url']=="photo1.jpg"

        mock_item_crud .get_recent .assert_called_once_with (mock_db_session ,limit =5 ,offset =0 )
        mock_photo_crud .get_by_item_id .assert_called_once_with (mock_db_session ,123 )

    @pytest .mark .asyncio
    async def test_is_search_complete (self ,task_manager ,mock_vinted_service ):
        """Test checking if search is complete."""

        assert await task_manager .is_search_complete ("nonexistent")

        mock_vinted_service .search_and_get_details .return_value =[]
        await task_manager .queue_search_task (
        search_id ="test123",
        query ="Nike shoes",
        user_id =12345
        )

        await asyncio .sleep (0.01 )

        await asyncio .sleep (0.1 )

        is_complete =await task_manager .is_search_complete ("test123")

        assert isinstance (is_complete ,bool )

    @pytest .mark .asyncio
    async def test_cancel_search (self ,task_manager ,mock_vinted_service ):
        """Test cancelling a search task."""

        async def slow_search (*args ,**kwargs ):
            await asyncio .sleep (1 )
            return []

        mock_vinted_service .search_and_get_details .side_effect =slow_search

        await task_manager .queue_search_task (
        search_id ="test123",
        query ="Nike shoes",
        user_id =12345
        )

        await asyncio .sleep (0.01 )

        cancelled =await task_manager .cancel_search ("test123")
        assert cancelled is True

        assert "test123"not in task_manager ._active_searches

        cancelled =await task_manager .cancel_search ("nonexistent")
        assert cancelled is False

    def test_get_active_searches (self ,task_manager ):
        """Test getting active search IDs."""

        active =task_manager .get_active_searches ()
        assert active ==[]

        task1 =MagicMock ()
        task1 .done .return_value =False
        task2 =MagicMock ()
        task2 .done .return_value =True
        task3 =MagicMock ()
        task3 .done .return_value =False

        task_manager ._active_searches ={
        "search1":task1 ,
        "search2":task2 ,
        "search3":task3
        }

        active =task_manager .get_active_searches ()
        assert set (active )=={"search1","search3"}