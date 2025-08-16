"""Background tasks for search functionality."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SearchTaskManager:
    """Manager for search-related background tasks."""

    def __init__(self):
        self.vinted_service = None
        self._active_searches: Dict[str, asyncio.Task] = {}

    def _get_vinted_service(self):
        """Get VintedService instance, creating it lazily."""
        if self.vinted_service is None:
            # Import here to avoid circular imports and network calls during import
            from bot.services.vinted_service import VintedService
            self.vinted_service = VintedService()
        return self.vinted_service

    async def queue_search_task(
        self,
        search_id: str,
        query: str,
        user_id: int,
        max_pages: int = 5,
        **filters
    ) -> str:
        """
        Queue a background search task.

        Args:
            search_id: Unique identifier for this search
            query: Search query string
            user_id: User ID who initiated the search
            max_pages: Maximum pages to crawl
            **filters: Additional search filters

        Returns:
            Task ID for tracking
        """
        if search_id in self._active_searches:
            self._active_searches[search_id].cancel()

        task = asyncio.create_task(
            self._execute_search_task(
                search_id=search_id,
                query=query,
                user_id=user_id,
                max_pages=max_pages,
                **filters
            )
        )

        self._active_searches[search_id] = task

        logger.info(f"Queued search task {search_id} for user {user_id}: {query}")
        return search_id

    async def _execute_search_task(
        self,
        search_id: str,
        query: str,
        user_id: int,
        max_pages: int = 5,
        **filters
    ) -> None:
        """
        Execute a search task in the background.

        Args:
            search_id: Unique identifier for this search
            query: Search query string
            user_id: User ID who initiated the search
            max_pages: Maximum pages to crawl
            **filters: Additional search filters
        """
        try:
            logger.info(f"Starting search task {search_id} for user {user_id}")

            items = await self._get_vinted_service().search_and_get_details(
                query=query,
                max_pages=max_pages,
                per_page=100,
                **filters
            )

            if items:
                await self._store_search_results(search_id, items, user_id)
                logger.info(f"Search task {search_id} completed: {len(items)} items stored")
            else:
                logger.info(f"Search task {search_id} completed: no items found")

        except asyncio.CancelledError:
            logger.info(f"Search task {search_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Search task {search_id} failed: {e}")
        finally:
            if search_id in self._active_searches:
                del self._active_searches[search_id]

    async def _store_search_results(
        self,
        search_id: str,
        items: List[Dict[str, Any]],
        user_id: int
    ) -> None:
        """
        Store search results in the database.

        Args:
            search_id: Search identifier
            items: List of item dictionaries
            user_id: User ID who initiated the search
        """
        # Import here to avoid circular imports
        from db.base import get_db_session
        from db.crud import ItemCRUD, PhotoCRUD
        
        async with get_db_session() as session:
            try:
                for item_data in items:
                    existing_item = await ItemCRUD.get_by_id(session, item_data['id'])

                    if existing_item:
                        await ItemCRUD.update(
                            session=session,
                            item_id=item_data['id'],
                            **{k: v for k, v in item_data.items()
                               if k not in ['id', 'photos']}
                        )
                        item = existing_item
                    else:
                        item = await ItemCRUD.create(
                            session=session,
                            **{k: v for k, v in item_data.items()
                               if k != 'photos'}
                        )

                    photos = item_data.get('photos', [])
                    if photos:
                        await PhotoCRUD.delete_by_item_id(session, item.id)

                        for photo_data in photos:
                            await PhotoCRUD.create(
                                session=session,
                                item_id=item.id,
                                url=photo_data['url'],
                                order_no=photo_data['order_no']
                            )

                await session.commit()
                logger.info(f"Stored {len(items)} items for search {search_id}")

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to store search results for {search_id}: {e}")
                raise

    async def get_search_results(
        self,
        search_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get stored search results.

        Args:
            search_id: Search identifier
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of item dictionaries with photos
        """
        # Import here to avoid circular imports
        from db.base import get_db_session
        from db.crud import ItemCRUD, PhotoCRUD
        
        async with get_db_session() as session:
            items = await ItemCRUD.get_recent(session, limit=limit, offset=offset)

            results = []
            for item in items:
                photos = await PhotoCRUD.get_by_item_id(session, item.id)

                item_dict = {
                    'id': item.id,
                    'title': item.title,
                    'price': float(item.price),
                    'currency': item.currency,
                    'brand': item.brand,
                    'size': item.size,
                    'condition': item.condition,
                    'description': item.description,
                    'seller_id': item.seller_id,
                    'url': item.url,
                    'preview_img': item.preview_img,
                    'ships_to_at': item.ships_to_at,
                    'photos': [
                        {'url': photo.url, 'order_no': photo.order_no}
                        for photo in sorted(photos, key=lambda p: p.order_no)
                    ]
                }
                results.append(item_dict)

            return results

    async def is_search_complete(self, search_id: str) -> bool:
        """
        Check if a search task is complete.

        Args:
            search_id: Search identifier

        Returns:
            True if search is complete, False if still running
        """
        if search_id not in self._active_searches:
            return True

        task = self._active_searches[search_id]
        return task.done()

    async def cancel_search(self, search_id: str) -> bool:
        """
        Cancel a running search task.

        Args:
            search_id: Search identifier

        Returns:
            True if task was cancelled, False if not found
        """
        if search_id not in self._active_searches:
            return False

        task = self._active_searches[search_id]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        return True

    def get_active_searches(self) -> List[str]:
        """
        Get list of active search IDs.

        Returns:
            List of active search identifiers
        """
        return [
            search_id for search_id, task in self._active_searches.items()
            if not task.done()
        ]


search_task_manager = SearchTaskManager()