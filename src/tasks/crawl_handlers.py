"""Task handlers for Vinted crawling operations."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from bot.services.vinted_service import VintedService
from db.base import get_db_session
from db.crud import ItemCRUD, PhotoCRUD
from db.models import Item, Photo
from tasks.queue import TaskQueue
from tasks.search_crawl_utils import crawl_deduplicator

logger = logging.getLogger(__name__)


async def crawl_vinted_search(
    query: str,
    max_pages: int = 5,
    per_page: int = 100,
    **filters
) -> Dict[str, Any]:
    """
    Crawl Vinted search results and store items with photos.
    
    Args:
        query: Search query string
        max_pages: Maximum number of pages to fetch
        per_page: Items per page (max 100)
        **filters: Additional search filters
        
    Returns:
        Dictionary with crawl results and statistics
    """
    logger.info(f"Starting Vinted crawl for query: '{query}' (max_pages={max_pages})")
    
    start_time = datetime.utcnow()
    stats = {
        "query": query,
        "started_at": start_time.isoformat(),
        "items_found": 0,
        "items_stored": 0,
        "photos_stored": 0,
        "errors": [],
        "duration_seconds": 0
    }
    
    try:
        # Initialize Vinted service
        vinted_service = VintedService()
        
        # Search for items
        search_results = await vinted_service.search_items(
            query=query,
            max_pages=max_pages,
            per_page=per_page,
            **filters
        )
        
        stats["items_found"] = len(search_results)
        
        if not search_results:
            logger.info(f"No items found for query: '{query}'")
            stats["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            return stats
        
        # Extract item IDs for detail fetching
        item_ids = [item["id"] for item in search_results]
        
        # Fetch detailed information for all items
        detailed_items = await vinted_service.get_item_details(item_ids)
        
        # Store items and photos in batches
        stored_items, stored_photos = await _batch_store_items_and_photos(detailed_items)
        
        stats["items_stored"] = stored_items
        stats["photos_stored"] = stored_photos
        
        end_time = datetime.utcnow()
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        
        # Mark search as completed in deduplication system
        await crawl_deduplicator.mark_search_completed(query, **filters)
        
        logger.info(
            f"Crawl completed for query '{query}': "
            f"{stats['items_stored']} items, {stats['photos_stored']} photos stored "
            f"in {stats['duration_seconds']:.2f}s"
        )
        
        return stats
        
    except Exception as e:
        error_msg = f"Error crawling Vinted search '{query}': {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        stats["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
        raise


async def crawl_item_details(item_ids: List[int]) -> Dict[str, Any]:
    """
    Crawl detailed information for specific item IDs.
    
    Args:
        item_ids: List of Vinted item IDs to fetch details for
        
    Returns:
        Dictionary with crawl results and statistics
    """
    logger.info(f"Starting item details crawl for {len(item_ids)} items")
    
    start_time = datetime.utcnow()
    stats = {
        "item_ids": item_ids,
        "started_at": start_time.isoformat(),
        "items_requested": len(item_ids),
        "items_fetched": 0,
        "items_stored": 0,
        "photos_stored": 0,
        "errors": [],
        "duration_seconds": 0
    }
    
    try:
        if not item_ids:
            logger.warning("No item IDs provided for detail crawl")
            return stats
        
        # Initialize Vinted service
        vinted_service = VintedService()
        
        # Fetch detailed information
        detailed_items = await vinted_service.get_item_details(item_ids)
        
        stats["items_fetched"] = len(detailed_items)
        
        if not detailed_items:
            logger.warning(f"No item details fetched for {len(item_ids)} requested items")
            stats["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            return stats
        
        # Store items and photos in batches
        stored_items, stored_photos = await _batch_store_items_and_photos(detailed_items)
        
        stats["items_stored"] = stored_items
        stats["photos_stored"] = stored_photos
        
        end_time = datetime.utcnow()
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        
        # Mark item details as completed in deduplication system
        await crawl_deduplicator.mark_item_details_completed(item_ids)
        
        logger.info(
            f"Item details crawl completed: "
            f"{stats['items_stored']} items, {stats['photos_stored']} photos stored "
            f"in {stats['duration_seconds']:.2f}s"
        )
        
        return stats
        
    except Exception as e:
        error_msg = f"Error crawling item details: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        stats["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
        raise


async def _batch_store_items_and_photos(items: List[Dict[str, Any]]) -> tuple[int, int]:
    """
    Store items and their photos in the database using batch operations.
    
    Args:
        items: List of item dictionaries with photo data
        
    Returns:
        Tuple of (items_stored, photos_stored) counts
    """
    if not items:
        return 0, 0
    
    items_stored = 0
    photos_stored = 0
    
    async with get_db_session() as session:
        try:
            # Process items in batches to avoid memory issues
            batch_size = 50
            
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                for item_data in batch:
                    try:
                        # Extract photos data before creating item
                        photos_data = item_data.pop("photos", [])
                        
                        # Check if item already exists
                        existing_item = await ItemCRUD.get_by_id(session, item_data["id"])
                        
                        if existing_item:
                            # Update existing item
                            await ItemCRUD.update(session, item_data["id"], **item_data)
                            logger.debug(f"Updated existing item {item_data['id']}")
                        else:
                            # Create new item
                            await ItemCRUD.create(session, **item_data)
                            logger.debug(f"Created new item {item_data['id']}")
                        
                        items_stored += 1
                        
                        # Store photos if any
                        if photos_data:
                            # Delete existing photos for this item to avoid duplicates
                            await PhotoCRUD.delete_by_item_id(session, item_data["id"])
                            
                            # Create new photos
                            for photo_data in photos_data:
                                await PhotoCRUD.create(
                                    session,
                                    item_id=item_data["id"],
                                    url=photo_data["url"],
                                    order_no=photo_data.get("order_no", 0)
                                )
                                photos_stored += 1
                        
                    except Exception as e:
                        logger.error(f"Error storing item {item_data.get('id', 'unknown')}: {e}")
                        continue
                
                # Commit batch
                await session.commit()
                logger.debug(f"Committed batch of {len(batch)} items")
            
            logger.info(f"Batch storage completed: {items_stored} items, {photos_stored} photos")
            
        except Exception as e:
            logger.error(f"Error in batch storage: {e}")
            await session.rollback()
            raise
    
    return items_stored, photos_stored


async def refresh_item_details(item_id: int) -> Dict[str, Any]:
    """
    Refresh details for a specific item.
    
    Args:
        item_id: Vinted item ID to refresh
        
    Returns:
        Dictionary with refresh results
    """
    logger.info(f"Refreshing details for item {item_id}")
    
    start_time = datetime.utcnow()
    stats = {
        "item_id": item_id,
        "started_at": start_time.isoformat(),
        "success": False,
        "photos_updated": 0,
        "error": None,
        "duration_seconds": 0
    }
    
    try:
        # Initialize Vinted service
        vinted_service = VintedService()
        
        # Fetch item details
        detailed_items = await vinted_service.get_item_details([item_id])
        
        if not detailed_items:
            stats["error"] = f"Item {item_id} not found or unavailable"
            stats["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            return stats
        
        # Store the updated item
        stored_items, stored_photos = await _batch_store_items_and_photos(detailed_items)
        
        stats["success"] = stored_items > 0
        stats["photos_updated"] = stored_photos
        
        end_time = datetime.utcnow()
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info(f"Item {item_id} refresh completed in {stats['duration_seconds']:.2f}s")
        
        return stats
        
    except Exception as e:
        error_msg = f"Error refreshing item {item_id}: {str(e)}"
        logger.error(error_msg)
        stats["error"] = error_msg
        stats["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
        raise


def register_crawl_handlers(queue: TaskQueue) -> None:
    """
    Register crawling task handlers.
    
    Args:
        queue: TaskQueue instance to register handlers with
    """
    logger.info("Registering Vinted crawl handlers...")
    
    # Register main crawl handlers
    queue.register_handler("crawl_vinted_search", crawl_vinted_search)
    queue.register_handler("crawl_item_details", crawl_item_details)
    queue.register_handler("refresh_item_details", refresh_item_details)
    
    logger.info("Vinted crawl handlers registered successfully")