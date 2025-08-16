"""Tests for Vinted search crawl utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import hashlib

from src.tasks.search_crawl_utils import (
    SearchCrawlDeduplicator,
    enqueue_search_crawl,
    enqueue_item_details_crawl,
    enqueue_item_refresh
)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.set.return_value = True  # Default: not duplicate
    mock_redis.expire.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.keys.return_value = []
    return mock_redis


@pytest.fixture
def deduplicator(mock_redis):
    """SearchCrawlDeduplicator instance with mocked Redis."""
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        dedup = SearchCrawlDeduplicator("redis://test:6379/0")
        return dedup


class TestSearchCrawlDeduplicator:
    """Tests for SearchCrawlDeduplicator class."""

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, deduplicator, mock_redis):
        """Test Redis connection and disconnection."""
        # Test connect
        await deduplicator.connect()
        assert deduplicator.redis is not None
        mock_redis.ping.assert_called_once()
        
        # Test disconnect
        await deduplicator.disconnect()
        assert deduplicator.redis is None
        mock_redis.close.assert_called_once()

    def test_generate_search_key(self, deduplicator):
        """Test search key generation."""
        # Test basic query
        key1 = deduplicator._generate_search_key("nike shoes")
        assert key1.startswith("crawl_dedup:search:")
        assert len(key1) > 20  # Should have hash suffix
        
        # Test same query should generate same key
        key2 = deduplicator._generate_search_key("nike shoes")
        assert key1 == key2
        
        # Test case insensitive
        key3 = deduplicator._generate_search_key("NIKE SHOES")
        assert key1 == key3
        
        # Test with filters - verify they generate consistent keys
        key4 = deduplicator._generate_search_key("nike", brand_ids=[1, 2])
        key5 = deduplicator._generate_search_key("nike", brand_ids=[1, 2])  # Same order
        assert key4 == key5  # Should be same for identical inputs
        
        # Test that different filters generate different keys
        key6 = deduplicator._generate_search_key("nike", brand_ids=[3, 4])
        assert key4 != key6
        
        # Test different queries generate different keys
        key6 = deduplicator._generate_search_key("adidas shoes")
        assert key1 != key6

    def test_generate_item_key(self, deduplicator):
        """Test item key generation."""
        # Test basic item list
        key1 = deduplicator._generate_item_key([12345, 67890])
        assert key1.startswith("crawl_dedup:items:")
        
        # Test same items in different order should generate same key
        key2 = deduplicator._generate_item_key([67890, 12345])
        assert key1 == key2
        
        # Test with duplicates should be deduplicated
        key3 = deduplicator._generate_item_key([12345, 12345, 67890])
        assert key1 == key3
        
        # Test different items generate different keys
        key4 = deduplicator._generate_item_key([11111, 22222])
        assert key1 != key4

    @pytest.mark.asyncio
    async def test_is_search_duplicate_new(self, deduplicator, mock_redis):
        """Test duplicate check for new search."""
        # Mock Redis SETNX to return True (key was set, not duplicate)
        mock_redis.set.return_value = True
        
        # Test
        is_duplicate = await deduplicator.is_search_duplicate("nike shoes")
        
        # Verify
        assert is_duplicate is False
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[1]['nx'] is True  # SETNX flag
        assert call_args[1]['ex'] == 300  # Default TTL

    @pytest.mark.asyncio
    async def test_is_search_duplicate_existing(self, deduplicator, mock_redis):
        """Test duplicate check for existing search."""
        # Mock Redis SETNX to return False (key already exists, is duplicate)
        mock_redis.set.return_value = False
        
        # Test
        is_duplicate = await deduplicator.is_search_duplicate("nike shoes")
        
        # Verify
        assert is_duplicate is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_search_duplicate_with_custom_ttl(self, deduplicator, mock_redis):
        """Test duplicate check with custom TTL."""
        mock_redis.set.return_value = True
        
        # Test with custom TTL
        await deduplicator.is_search_duplicate("nike shoes", ttl_seconds=600)
        
        # Verify TTL was used
        call_args = mock_redis.set.call_args
        assert call_args[1]['ex'] == 600

    @pytest.mark.asyncio
    async def test_is_item_details_duplicate_new(self, deduplicator, mock_redis):
        """Test duplicate check for new item details request."""
        mock_redis.set.return_value = True
        
        # Test
        is_duplicate = await deduplicator.is_item_details_duplicate([12345, 67890])
        
        # Verify
        assert is_duplicate is False
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_item_details_duplicate_empty_list(self, deduplicator):
        """Test duplicate check with empty item list."""
        # Test
        is_duplicate = await deduplicator.is_item_details_duplicate([])
        
        # Verify - empty lists are always duplicates
        assert is_duplicate is True

    @pytest.mark.asyncio
    async def test_mark_search_completed(self, deduplicator, mock_redis):
        """Test marking search as completed."""
        await deduplicator.mark_search_completed("nike shoes", brand_ids=[1])
        
        # Verify expire was called to extend TTL
        mock_redis.expire.assert_called_once()
        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == 600  # 2 * default_ttl

    @pytest.mark.asyncio
    async def test_mark_item_details_completed(self, deduplicator, mock_redis):
        """Test marking item details as completed."""
        await deduplicator.mark_item_details_completed([12345, 67890])
        
        # Verify expire was called
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_item_details_completed_empty_list(self, deduplicator, mock_redis):
        """Test marking item details completed with empty list."""
        await deduplicator.mark_item_details_completed([])
        
        # Verify no Redis calls for empty list
        mock_redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_search_dedup(self, deduplicator, mock_redis):
        """Test clearing search deduplication."""
        mock_redis.delete.return_value = 1  # Key was deleted
        
        # Test
        result = await deduplicator.clear_search_dedup("nike shoes")
        
        # Verify
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_search_dedup_not_found(self, deduplicator, mock_redis):
        """Test clearing search deduplication when key not found."""
        mock_redis.delete.return_value = 0  # No key was deleted
        
        # Test
        result = await deduplicator.clear_search_dedup("nike shoes")
        
        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_get_dedup_stats(self, deduplicator, mock_redis):
        """Test getting deduplication statistics."""
        # Mock Redis keys response
        mock_redis.keys.side_effect = [
            ["crawl_dedup:search:hash1", "crawl_dedup:search:hash2"],  # Search keys
            ["crawl_dedup:items:hash3"]  # Item keys
        ]
        
        # Test
        stats = await deduplicator.get_dedup_stats()
        
        # Verify
        assert stats["active_search_dedups"] == 2
        assert stats["active_item_dedups"] == 1
        assert stats["total_active_dedups"] == 3
        
        # Verify Redis calls
        assert mock_redis.keys.call_count == 2


class TestEnqueueFunctions:
    """Tests for enqueue utility functions."""

    @pytest.fixture
    def mock_queue(self):
        """Mock TaskQueue for testing."""
        queue = AsyncMock()
        queue.enqueue.return_value = "test-task-id-123"
        return queue

    @pytest.fixture
    def mock_deduplicator(self):
        """Mock deduplicator for testing."""
        with patch('src.tasks.search_crawl_utils.crawl_deduplicator') as mock_dedup:
            mock_dedup.is_search_duplicate = AsyncMock(return_value=False)
            mock_dedup.is_item_details_duplicate = AsyncMock(return_value=False)
            yield mock_dedup

    @pytest.mark.asyncio
    async def test_enqueue_search_crawl_success(self, mock_queue, mock_deduplicator):
        """Test successful search crawl enqueue."""
        # Test
        task_id = await enqueue_search_crawl(
            mock_queue,
            "nike shoes",
            max_pages=3,
            per_page=50,
            priority=1,
            brand_ids=[1, 2]
        )
        
        # Verify
        assert task_id == "test-task-id-123"
        
        # Verify deduplication check
        mock_deduplicator.is_search_duplicate.assert_called_once_with(
            "nike shoes", 
            brand_ids=[1, 2]
        )
        
        # Verify queue enqueue
        mock_queue.enqueue.assert_called_once_with(
            "crawl_vinted_search",
            "nike shoes",
            max_pages=3,
            per_page=50,
            priority=1,
            brand_ids=[1, 2]
        )

    @pytest.mark.asyncio
    async def test_enqueue_search_crawl_duplicate(self, mock_queue, mock_deduplicator):
        """Test search crawl enqueue when duplicate detected."""
        # Setup duplicate detection
        mock_deduplicator.is_search_duplicate = AsyncMock(return_value=True)
        
        # Test
        task_id = await enqueue_search_crawl(mock_queue, "nike shoes")
        
        # Verify
        assert task_id is None
        mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_search_crawl_skip_duplicate_check(self, mock_queue, mock_deduplicator):
        """Test search crawl enqueue with duplicate check disabled."""
        # Test
        task_id = await enqueue_search_crawl(
            mock_queue,
            "nike shoes",
            check_duplicate=False
        )
        
        # Verify
        assert task_id == "test-task-id-123"
        mock_deduplicator.is_search_duplicate.assert_not_called()
        mock_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_item_details_crawl_success(self, mock_queue, mock_deduplicator):
        """Test successful item details crawl enqueue."""
        # Test
        task_id = await enqueue_item_details_crawl(
            mock_queue,
            [12345, 67890],
            priority=2
        )
        
        # Verify
        assert task_id == "test-task-id-123"
        
        # Verify deduplication check
        mock_deduplicator.is_item_details_duplicate.assert_called_once_with([12345, 67890])
        
        # Verify queue enqueue
        mock_queue.enqueue.assert_called_once_with(
            "crawl_item_details",
            [12345, 67890],
            priority=2
        )

    @pytest.mark.asyncio
    async def test_enqueue_item_details_crawl_empty_list(self, mock_queue):
        """Test item details crawl enqueue with empty item list."""
        # Test
        task_id = await enqueue_item_details_crawl(mock_queue, [])
        
        # Verify
        assert task_id is None
        mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_item_details_crawl_duplicate(self, mock_queue, mock_deduplicator):
        """Test item details crawl enqueue when duplicate detected."""
        # Setup duplicate detection
        mock_deduplicator.is_item_details_duplicate = AsyncMock(return_value=True)
        
        # Test
        task_id = await enqueue_item_details_crawl(mock_queue, [12345, 67890])
        
        # Verify
        assert task_id is None
        mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_item_refresh(self, mock_queue):
        """Test item refresh enqueue."""
        # Test
        task_id = await enqueue_item_refresh(mock_queue, 12345, priority=3)
        
        # Verify
        assert task_id == "test-task-id-123"
        mock_queue.enqueue.assert_called_once_with(
            "refresh_item_details",
            12345,
            priority=3
        )


class TestIntegration:
    """Integration tests for search crawl utilities."""

    @pytest.mark.asyncio
    async def test_deduplicator_key_consistency(self):
        """Test that key generation is consistent across instances."""
        dedup1 = SearchCrawlDeduplicator()
        dedup2 = SearchCrawlDeduplicator()
        
        # Test search keys - same inputs should generate same keys
        key1 = dedup1._generate_search_key("nike shoes", brand_ids=[1, 2])
        key2 = dedup2._generate_search_key("nike shoes", brand_ids=[1, 2])
        assert key1 == key2
        
        # Test item keys
        key3 = dedup1._generate_item_key([12345, 67890])
        key4 = dedup2._generate_item_key([67890, 12345])
        assert key3 == key4

    @pytest.mark.asyncio
    async def test_full_deduplication_flow(self, mock_redis):
        """Test complete deduplication flow."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            dedup = SearchCrawlDeduplicator()
            
            # First check - should not be duplicate
            mock_redis.set.return_value = True
            is_dup1 = await dedup.is_search_duplicate("nike shoes")
            assert is_dup1 is False
            
            # Second check - should be duplicate
            mock_redis.set.return_value = False
            is_dup2 = await dedup.is_search_duplicate("nike shoes")
            assert is_dup2 is True
            
            # Mark completed
            await dedup.mark_search_completed("nike shoes")
            mock_redis.expire.assert_called_once()
            
            # Clear deduplication
            mock_redis.delete.return_value = 1
            cleared = await dedup.clear_search_dedup("nike shoes")
            assert cleared is True