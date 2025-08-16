"""Tests for Vinted crawling task handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.tasks.crawl_handlers import (
    crawl_vinted_search,
    crawl_item_details,
    refresh_item_details,
    _batch_store_items_and_photos,
    register_crawl_handlers
)
from src.tasks.queue import TaskQueue


@pytest.fixture
def mock_vinted_service():
    """Mock VintedService for testing."""
    with patch('src.tasks.crawl_handlers.VintedService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    with patch('src.tasks.crawl_handlers.get_db_session') as mock_session_context:
        mock_session = AsyncMock()
        mock_session_context.return_value.__aenter__.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_deduplicator():
    """Mock crawl deduplicator for testing."""
    with patch('src.tasks.crawl_handlers.crawl_deduplicator') as mock_dedup:
        mock_dedup.mark_search_completed = AsyncMock()
        mock_dedup.mark_item_details_completed = AsyncMock()
        yield mock_dedup


@pytest.fixture
def sample_search_results():
    """Sample search results from Vinted."""
    return [
        {
            "id": 12345,
            "title": "Vintage Nike Sneakers",
            "price": 45.99,
            "currency": "EUR",
            "brand": "Nike",
            "size": "42",
            "condition": "Good",
            "url": "https://www.vinted.at/items/12345",
            "preview_img": "https://example.com/preview1.jpg",
            "seller_id": 67890,
            "ships_to_at": True
        },
        {
            "id": 12346,
            "title": "Adidas T-Shirt",
            "price": 15.50,
            "currency": "EUR",
            "brand": "Adidas",
            "size": "M",
            "condition": "Very Good",
            "url": "https://www.vinted.at/items/12346",
            "preview_img": "https://example.com/preview2.jpg",
            "seller_id": 67891,
            "ships_to_at": True
        }
    ]


@pytest.fixture
def sample_detailed_items():
    """Sample detailed items with photos."""
    return [
        {
            "id": 12345,
            "title": "Vintage Nike Sneakers",
            "price": 45.99,
            "currency": "EUR",
            "brand": "Nike",
            "size": "42",
            "condition": "Good",
            "description": "Great vintage sneakers in good condition",
            "seller_id": 67890,
            "url": "https://www.vinted.at/items/12345",
            "preview_img": "https://example.com/photo1.jpg",
            "ships_to_at": True,
            "photos": [
                {"url": "https://example.com/photo1.jpg", "order_no": 0},
                {"url": "https://example.com/photo2.jpg", "order_no": 1}
            ]
        },
        {
            "id": 12346,
            "title": "Adidas T-Shirt",
            "price": 15.50,
            "currency": "EUR",
            "brand": "Adidas",
            "size": "M",
            "condition": "Very Good",
            "description": "Comfortable Adidas t-shirt",
            "seller_id": 67891,
            "url": "https://www.vinted.at/items/12346",
            "preview_img": "https://example.com/photo3.jpg",
            "ships_to_at": True,
            "photos": [
                {"url": "https://example.com/photo3.jpg", "order_no": 0}
            ]
        }
    ]


class TestCrawlVintedSearch:
    """Tests for crawl_vinted_search function."""

    @pytest.mark.asyncio
    async def test_successful_search_crawl(
        self, 
        mock_vinted_service, 
        mock_db_session,
        mock_deduplicator,
        sample_search_results,
        sample_detailed_items
    ):
        """Test successful search crawl with items found."""
        # Setup mocks
        mock_vinted_service.search_items.return_value = sample_search_results
        mock_vinted_service.get_item_details.return_value = sample_detailed_items
        
        with patch('src.tasks.crawl_handlers._batch_store_items_and_photos') as mock_batch_store:
            mock_batch_store.return_value = (2, 3)  # 2 items, 3 photos stored
            
            # Execute
            result = await crawl_vinted_search("nike sneakers", max_pages=2, per_page=50)
            
            # Verify
            assert result["query"] == "nike sneakers"
            assert result["items_found"] == 2
            assert result["items_stored"] == 2
            assert result["photos_stored"] == 3
            assert result["duration_seconds"] > 0
            assert len(result["errors"]) == 0
            
            # Verify service calls
            mock_vinted_service.search_items.assert_called_once_with(
                query="nike sneakers",
                max_pages=2,
                per_page=50
            )
            mock_vinted_service.get_item_details.assert_called_once_with([12345, 12346])
            
            # Verify batch storage
            mock_batch_store.assert_called_once_with(sample_detailed_items)
            
            # Verify deduplication
            mock_deduplicator.mark_search_completed.assert_called_once_with("nike sneakers")

    @pytest.mark.asyncio
    async def test_search_crawl_no_results(
        self, 
        mock_vinted_service, 
        mock_deduplicator
    ):
        """Test search crawl when no items are found."""
        # Setup mocks
        mock_vinted_service.search_items.return_value = []
        
        # Execute
        result = await crawl_vinted_search("nonexistent item")
        
        # Verify
        assert result["query"] == "nonexistent item"
        assert result["items_found"] == 0
        assert result["items_stored"] == 0
        assert result["photos_stored"] == 0
        assert result["duration_seconds"] > 0
        
        # Verify service calls
        mock_vinted_service.search_items.assert_called_once()
        mock_vinted_service.get_item_details.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_crawl_with_filters(
        self, 
        mock_vinted_service,
        mock_deduplicator,
        sample_search_results,
        sample_detailed_items
    ):
        """Test search crawl with additional filters."""
        # Setup mocks
        mock_vinted_service.search_items.return_value = sample_search_results
        mock_vinted_service.get_item_details.return_value = sample_detailed_items
        
        with patch('src.tasks.crawl_handlers._batch_store_items_and_photos') as mock_batch_store:
            mock_batch_store.return_value = (2, 3)
            
            # Execute with filters
            result = await crawl_vinted_search(
                "nike",
                max_pages=1,
                per_page=20,
                brand_ids=[1, 2],
                size_ids=[10]
            )
            
            # Verify service call includes filters
            mock_vinted_service.search_items.assert_called_once_with(
                query="nike",
                max_pages=1,
                per_page=20,
                brand_ids=[1, 2],
                size_ids=[10]
            )
            
            # Verify deduplication includes filters
            mock_deduplicator.mark_search_completed.assert_called_once_with(
                "nike",
                brand_ids=[1, 2],
                size_ids=[10]
            )

    @pytest.mark.asyncio
    async def test_search_crawl_service_error(self, mock_vinted_service):
        """Test search crawl when Vinted service raises an error."""
        # Setup mock to raise error
        mock_vinted_service.search_items.side_effect = Exception("Vinted API error")
        
        # Execute and expect exception
        with pytest.raises(Exception, match="Vinted API error"):
            await crawl_vinted_search("test query")


class TestCrawlItemDetails:
    """Tests for crawl_item_details function."""

    @pytest.mark.asyncio
    async def test_successful_item_details_crawl(
        self, 
        mock_vinted_service,
        mock_deduplicator,
        sample_detailed_items
    ):
        """Test successful item details crawl."""
        # Setup mocks
        item_ids = [12345, 12346]
        mock_vinted_service.get_item_details.return_value = sample_detailed_items
        
        with patch('src.tasks.crawl_handlers._batch_store_items_and_photos') as mock_batch_store:
            mock_batch_store.return_value = (2, 3)
            
            # Execute
            result = await crawl_item_details(item_ids)
            
            # Verify
            assert result["item_ids"] == item_ids
            assert result["items_requested"] == 2
            assert result["items_fetched"] == 2
            assert result["items_stored"] == 2
            assert result["photos_stored"] == 3
            assert result["duration_seconds"] > 0
            assert len(result["errors"]) == 0
            
            # Verify service calls
            mock_vinted_service.get_item_details.assert_called_once_with(item_ids)
            mock_batch_store.assert_called_once_with(sample_detailed_items)
            mock_deduplicator.mark_item_details_completed.assert_called_once_with(item_ids)

    @pytest.mark.asyncio
    async def test_item_details_crawl_empty_list(self, mock_vinted_service):
        """Test item details crawl with empty item list."""
        # Execute
        result = await crawl_item_details([])
        
        # Verify
        assert result["items_requested"] == 0
        assert result["items_fetched"] == 0
        assert result["items_stored"] == 0
        assert result["photos_stored"] == 0
        
        # Verify no service calls
        mock_vinted_service.get_item_details.assert_not_called()

    @pytest.mark.asyncio
    async def test_item_details_crawl_no_results(
        self, 
        mock_vinted_service,
        mock_deduplicator
    ):
        """Test item details crawl when no items are returned."""
        # Setup mocks
        item_ids = [99999, 99998]
        mock_vinted_service.get_item_details.return_value = []
        
        # Execute
        result = await crawl_item_details(item_ids)
        
        # Verify
        assert result["items_requested"] == 2
        assert result["items_fetched"] == 0
        assert result["items_stored"] == 0
        assert result["photos_stored"] == 0
        
        # Verify service calls
        mock_vinted_service.get_item_details.assert_called_once_with(item_ids)


class TestRefreshItemDetails:
    """Tests for refresh_item_details function."""

    @pytest.mark.asyncio
    async def test_successful_item_refresh(
        self, 
        mock_vinted_service,
        sample_detailed_items
    ):
        """Test successful item refresh."""
        # Setup mocks
        item_id = 12345
        mock_vinted_service.get_item_details.return_value = [sample_detailed_items[0]]
        
        with patch('src.tasks.crawl_handlers._batch_store_items_and_photos') as mock_batch_store:
            mock_batch_store.return_value = (1, 2)
            
            # Execute
            result = await refresh_item_details(item_id)
            
            # Verify
            assert result["item_id"] == item_id
            assert result["success"] is True
            assert result["photos_updated"] == 2
            assert result["error"] is None
            assert result["duration_seconds"] > 0
            
            # Verify service calls
            mock_vinted_service.get_item_details.assert_called_once_with([item_id])
            mock_batch_store.assert_called_once_with([sample_detailed_items[0]])

    @pytest.mark.asyncio
    async def test_item_refresh_not_found(self, mock_vinted_service):
        """Test item refresh when item is not found."""
        # Setup mocks
        item_id = 99999
        mock_vinted_service.get_item_details.return_value = []
        
        # Execute
        result = await refresh_item_details(item_id)
        
        # Verify
        assert result["item_id"] == item_id
        assert result["success"] is False
        assert result["photos_updated"] == 0
        assert "not found" in result["error"]


class TestBatchStoreItemsAndPhotos:
    """Tests for _batch_store_items_and_photos function."""

    @pytest.mark.asyncio
    async def test_batch_store_new_items(self, mock_db_session, sample_detailed_items):
        """Test batch storage of new items."""
        # Setup mocks
        with patch('src.tasks.crawl_handlers.ItemCRUD') as mock_item_crud, \
             patch('src.tasks.crawl_handlers.PhotoCRUD') as mock_photo_crud:
            
            mock_item_crud.get_by_id = AsyncMock(return_value=None)  # No existing items
            mock_item_crud.create = AsyncMock()
            mock_photo_crud.delete_by_item_id = AsyncMock()
            mock_photo_crud.create = AsyncMock()
            
            # Execute
            items_stored, photos_stored = await _batch_store_items_and_photos(sample_detailed_items)
            
            # Verify
            assert items_stored == 2
            assert photos_stored == 3  # 2 photos for first item, 1 for second
            
            # Verify database calls
            assert mock_item_crud.get_by_id.call_count == 2
            assert mock_item_crud.create.call_count == 2
            assert mock_item_crud.update.call_count == 0
            assert mock_photo_crud.delete_by_item_id.call_count == 2
            assert mock_photo_crud.create.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_store_existing_items(self, mock_db_session, sample_detailed_items):
        """Test batch storage of existing items (updates)."""
        # Setup mocks
        with patch('src.tasks.crawl_handlers.ItemCRUD') as mock_item_crud, \
             patch('src.tasks.crawl_handlers.PhotoCRUD') as mock_photo_crud:
            
            mock_item_crud.get_by_id = AsyncMock(return_value=AsyncMock())  # Existing items
            mock_item_crud.update = AsyncMock()
            mock_photo_crud.delete_by_item_id = AsyncMock()
            mock_photo_crud.create = AsyncMock()
            
            # Execute
            items_stored, photos_stored = await _batch_store_items_and_photos(sample_detailed_items)
            
            # Verify
            assert items_stored == 2
            assert photos_stored == 3
            
            # Verify database calls
            assert mock_item_crud.get_by_id.call_count == 2
            assert mock_item_crud.create.call_count == 0
            assert mock_item_crud.update.call_count == 2
            assert mock_photo_crud.delete_by_item_id.call_count == 2
            assert mock_photo_crud.create.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_store_empty_list(self, mock_db_session):
        """Test batch storage with empty item list."""
        # Execute
        items_stored, photos_stored = await _batch_store_items_and_photos([])
        
        # Verify
        assert items_stored == 0
        assert photos_stored == 0

    @pytest.mark.asyncio
    async def test_batch_store_items_without_photos(self, mock_db_session):
        """Test batch storage of items without photos."""
        items_without_photos = [
            {
                "id": 12345,
                "title": "Test Item",
                "price": 10.0,
                "currency": "EUR",
                "url": "https://example.com/item/12345",
                "ships_to_at": True
            }
        ]
        
        with patch('src.tasks.crawl_handlers.ItemCRUD') as mock_item_crud, \
             patch('src.tasks.crawl_handlers.PhotoCRUD') as mock_photo_crud:
            
            mock_item_crud.get_by_id = AsyncMock(return_value=None)
            mock_item_crud.create = AsyncMock()
            
            # Execute
            items_stored, photos_stored = await _batch_store_items_and_photos(items_without_photos)
            
            # Verify
            assert items_stored == 1
            assert photos_stored == 0
            
            # Verify no photo operations
            mock_photo_crud.delete_by_item_id.assert_not_called()
            mock_photo_crud.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_store_with_database_error(self, mock_db_session, sample_detailed_items):
        """Test batch storage when database operations fail."""
        with patch('src.tasks.crawl_handlers.ItemCRUD') as mock_item_crud:
            mock_item_crud.get_by_id.side_effect = Exception("Database error")
            
            # Execute and expect exception
            with pytest.raises(Exception, match="Database error"):
                await _batch_store_items_and_photos(sample_detailed_items)


class TestRegisterCrawlHandlers:
    """Tests for register_crawl_handlers function."""

    def test_register_crawl_handlers(self):
        """Test that all crawl handlers are registered correctly."""
        # Create mock queue
        mock_queue = MagicMock()
        
        # Execute
        register_crawl_handlers(mock_queue)
        
        # Verify all handlers are registered
        expected_handlers = [
            "crawl_vinted_search",
            "crawl_item_details", 
            "refresh_item_details"
        ]
        
        assert mock_queue.register_handler.call_count == len(expected_handlers)
        
        # Verify handler names
        registered_names = [call[0][0] for call in mock_queue.register_handler.call_args_list]
        for handler_name in expected_handlers:
            assert handler_name in registered_names