"""Utilities for Vinted search crawling tasks."""

import hashlib
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import redis.asyncio as redis

from src.config import settings

logger = logging.getLogger(__name__)


class SearchCrawlDeduplicator:
    """Handles deduplication of search crawl tasks using Redis."""
    
    def __init__(self, redis_url: str = None):
        """
        Initialize deduplicator.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or settings.redis_url
        self.redis: Optional[redis.Redis] = None
        self.dedup_prefix = "crawl_dedup"
        self.default_ttl = 300  # 5 minutes
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if self.redis is None:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            await self.redis.ping()
            logger.debug("Connected to Redis for crawl deduplication")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.redis = None
    
    def _generate_search_key(self, query: str, **filters) -> str:
        """
        Generate a unique key for a search query with filters.
        
        Args:
            query: Search query string
            **filters: Additional search filters
            
        Returns:
            Unique key for the search
        """
        # Create a simple string representation for consistent hashing
        parts = [f"query:{query.lower().strip()}"]
        
        # Add sorted filters
        for key in sorted(filters.keys()):
            value = filters[key]
            if isinstance(value, list):
                value_str = ','.join(map(str, sorted(value)))
            else:
                value_str = str(value)
            parts.append(f"{key}:{value_str}")
        
        key_string = '|'.join(parts)
        search_hash = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        
        return f"{self.dedup_prefix}:search:{search_hash}"
    
    def _generate_item_key(self, item_ids: list) -> str:
        """
        Generate a unique key for item detail requests.
        
        Args:
            item_ids: List of item IDs
            
        Returns:
            Unique key for the item detail request
        """
        # Sort IDs to ensure consistent key generation
        sorted_ids = sorted(set(item_ids))
        ids_hash = hashlib.md5(str(sorted_ids).encode()).hexdigest()
        
        return f"{self.dedup_prefix}:items:{ids_hash}"
    
    async def is_search_duplicate(
        self, 
        query: str, 
        ttl_seconds: int = None,
        **filters
    ) -> bool:
        """
        Check if a search query is a duplicate within the TTL window.
        
        Args:
            query: Search query string
            ttl_seconds: TTL for deduplication (default: 5 minutes)
            **filters: Additional search filters
            
        Returns:
            True if duplicate, False if new
        """
        if not self.redis:
            await self.connect()
        
        key = self._generate_search_key(query, **filters)
        ttl = ttl_seconds or self.default_ttl
        
        # Use SETNX with TTL for atomic deduplication
        result = await self.redis.set(key, "1", nx=True, ex=ttl)
        
        is_duplicate = not result  # True if key already existed
        
        if is_duplicate:
            logger.info(f"Duplicate search detected for query: '{query}'")
        else:
            logger.debug(f"New search registered for query: '{query}'")
        
        return is_duplicate
    
    async def is_item_details_duplicate(
        self, 
        item_ids: list, 
        ttl_seconds: int = None
    ) -> bool:
        """
        Check if an item details request is a duplicate within the TTL window.
        
        Args:
            item_ids: List of item IDs
            ttl_seconds: TTL for deduplication (default: 5 minutes)
            
        Returns:
            True if duplicate, False if new
        """
        if not self.redis:
            await self.connect()
        
        if not item_ids:
            return True  # Empty requests are always duplicates
        
        key = self._generate_item_key(item_ids)
        ttl = ttl_seconds or self.default_ttl
        
        # Use SETNX with TTL for atomic deduplication
        result = await self.redis.set(key, "1", nx=True, ex=ttl)
        
        is_duplicate = not result  # True if key already existed
        
        if is_duplicate:
            logger.info(f"Duplicate item details request for {len(item_ids)} items")
        else:
            logger.debug(f"New item details request for {len(item_ids)} items")
        
        return is_duplicate
    
    async def mark_search_completed(self, query: str, **filters) -> None:
        """
        Mark a search as completed and extend its TTL.
        
        Args:
            query: Search query string
            **filters: Additional search filters
        """
        if not self.redis:
            await self.connect()
        
        key = self._generate_search_key(query, **filters)
        
        # Extend TTL to prevent immediate re-crawling
        await self.redis.expire(key, self.default_ttl * 2)
        logger.debug(f"Marked search completed for query: '{query}'")
    
    async def mark_item_details_completed(self, item_ids: list) -> None:
        """
        Mark item details request as completed and extend its TTL.
        
        Args:
            item_ids: List of item IDs
        """
        if not self.redis:
            await self.connect()
        
        if not item_ids:
            return
        
        key = self._generate_item_key(item_ids)
        
        # Extend TTL to prevent immediate re-crawling
        await self.redis.expire(key, self.default_ttl * 2)
        logger.debug(f"Marked item details completed for {len(item_ids)} items")
    
    async def clear_search_dedup(self, query: str, **filters) -> bool:
        """
        Clear deduplication for a specific search.
        
        Args:
            query: Search query string
            **filters: Additional search filters
            
        Returns:
            True if key was deleted, False if not found
        """
        if not self.redis:
            await self.connect()
        
        key = self._generate_search_key(query, **filters)
        result = await self.redis.delete(key)
        
        if result:
            logger.info(f"Cleared deduplication for query: '{query}'")
        
        return bool(result)
    
    async def get_dedup_stats(self) -> Dict[str, Any]:
        """
        Get deduplication statistics.
        
        Returns:
            Dictionary with deduplication stats
        """
        if not self.redis:
            await self.connect()
        
        # Count keys by type
        search_keys = await self.redis.keys(f"{self.dedup_prefix}:search:*")
        item_keys = await self.redis.keys(f"{self.dedup_prefix}:items:*")
        
        return {
            "active_search_dedups": len(search_keys),
            "active_item_dedups": len(item_keys),
            "total_active_dedups": len(search_keys) + len(item_keys),
        }


# Global deduplicator instance
crawl_deduplicator = SearchCrawlDeduplicator()


async def enqueue_search_crawl(
    queue,
    query: str,
    max_pages: int = 5,
    per_page: int = 100,
    priority: int = 0,
    check_duplicate: bool = True,
    **filters
) -> Optional[str]:
    """
    Enqueue a Vinted search crawl task with deduplication.
    
    Args:
        queue: TaskQueue instance
        query: Search query string
        max_pages: Maximum number of pages to fetch
        per_page: Items per page
        priority: Task priority
        check_duplicate: Whether to check for duplicates
        **filters: Additional search filters
        
    Returns:
        Task ID if enqueued, None if duplicate
    """
    # Check for duplicates if enabled
    if check_duplicate:
        is_duplicate = await crawl_deduplicator.is_search_duplicate(query, **filters)
        if is_duplicate:
            logger.info(f"Skipping duplicate search crawl for query: '{query}'")
            return None
    
    # Enqueue the task
    task_id = await queue.enqueue(
        "crawl_vinted_search",
        query,
        max_pages=max_pages,
        per_page=per_page,
        priority=priority,
        **filters
    )
    
    logger.info(f"Enqueued search crawl task {task_id} for query: '{query}'")
    return task_id


async def enqueue_item_details_crawl(
    queue,
    item_ids: list,
    priority: int = 0,
    check_duplicate: bool = True
) -> Optional[str]:
    """
    Enqueue an item details crawl task with deduplication.
    
    Args:
        queue: TaskQueue instance
        item_ids: List of item IDs to fetch details for
        priority: Task priority
        check_duplicate: Whether to check for duplicates
        
    Returns:
        Task ID if enqueued, None if duplicate
    """
    if not item_ids:
        logger.warning("No item IDs provided for details crawl")
        return None
    
    # Check for duplicates if enabled
    if check_duplicate:
        is_duplicate = await crawl_deduplicator.is_item_details_duplicate(item_ids)
        if is_duplicate:
            logger.info(f"Skipping duplicate item details crawl for {len(item_ids)} items")
            return None
    
    # Enqueue the task
    task_id = await queue.enqueue(
        "crawl_item_details",
        item_ids,
        priority=priority
    )
    
    logger.info(f"Enqueued item details crawl task {task_id} for {len(item_ids)} items")
    return task_id


async def enqueue_item_refresh(
    queue,
    item_id: int,
    priority: int = 0
) -> str:
    """
    Enqueue an item refresh task.
    
    Args:
        queue: TaskQueue instance
        item_id: Item ID to refresh
        priority: Task priority
        
    Returns:
        Task ID
    """
    task_id = await queue.enqueue(
        "refresh_item_details",
        item_id,
        priority=priority
    )
    
    logger.info(f"Enqueued item refresh task {task_id} for item {item_id}")
    return task_id 