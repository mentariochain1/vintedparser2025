"""
Scraper integration service for Vinted bot.
Combines scraping capabilities with image processing.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.bot.services.vinted_service import VintedService
from src.bot.services.image import get_image_processor
from src.monitoring import get_logger, record_vinted_api_request
from src.exceptions import VintedAPIError, VintedServiceUnavailableError


logger = get_logger(__name__)


@dataclass
class SearchConfig:
    """Configuration for Vinted search."""
    query: str
    max_items: int
    max_pages: int = None
    per_page: int = 24
    filters: Dict[str, Any] = None

    def __post_init__(self):
        if self.max_pages is None:
            self.max_pages = max(1, (self.max_items + self.per_page - 1) // self.per_page)

        if self.filters is None:
            self.filters = {}


@dataclass
class SearchResult:
    """Result of Vinted search operation."""
    items: List[Dict[str, Any]]
    total_found: int
    success: bool
    error_message: Optional[str] = None
    processing_time: float = 0.0


class VintedScraperService:
    """
    Integration service that combines Vinted scraping with image processing.
    Handles search requests with specific item counts and image enhancement.
    """

    def __init__(self):
        """Initialize the scraper service."""
        self.vinted_service = VintedService()
        self.image_processor = get_image_processor()
        self.max_concurrent_searches = 3
        self._active_searches = 0

    async def search_items_with_images(self, config: SearchConfig) -> SearchResult:
        """
        Search for Vinted items with image processing.

        Args:
            config: Search configuration with query and limits

        Returns:
            SearchResult with processed items and images
        """
        import time
        start_time = time.time()

        # Validate search configuration
        if not config.query or not config.query.strip():
            return SearchResult(
                items=[],
                total_found=0,
                success=False,
                error_message="Empty search query",
                processing_time=0.0
            )

        if config.max_items < 1 or config.max_items > 100:
            return SearchResult(
                items=[],
                total_found=0,
                success=False,
                error_message="Invalid item count (must be 1-100)",
                processing_time=0.0
            )

        # Check concurrent search limit
        if self._active_searches >= self.max_concurrent_searches:
            return SearchResult(
                items=[],
                total_found=0,
                success=False,
                error_message="Too many concurrent searches. Please try again later.",
                processing_time=0.0
            )

        self._active_searches += 1

        try:
            logger.info(f"Starting Vinted search: '{config.query}' (max {config.max_items} items)")

            # Search using Vinted service
            items = await self._search_vinted_items(config)

            if not items:
                logger.warning(f"No items found for query: '{config.query}'")
                return SearchResult(
                    items=[],
                    total_found=0,
                    success=True,
                    error_message="No items found for this search",
                    processing_time=time.time() - start_time
                )

            # Limit results to requested count
            limited_items = items[:config.max_items]

            # Process images for the items
            processed_items = await self._process_item_images(limited_items)

            processing_time = time.time() - start_time

            logger.info(
                f"Search completed: {len(processed_items)} items processed in {processing_time:.2f}s"
            )

            return SearchResult(
                items=processed_items,
                total_found=len(processed_items),
                success=True,
                processing_time=processing_time
            )

        except VintedAPIError as e:
            logger.error(f"Vinted API error: {str(e)}")
            return SearchResult(
                items=[],
                total_found=0,
                success=False,
                error_message="Vinted service temporarily unavailable",
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Unexpected error in search: {str(e)}")
            return SearchResult(
                items=[],
                total_found=0,
                success=False,
                error_message="Search failed due to technical error",
                processing_time=time.time() - start_time
            )

        finally:
            self._active_searches -= 1

    async def _search_vinted_items(self, config: SearchConfig) -> List[Dict[str, Any]]:
        """
        Perform the actual Vinted search using the service.

        Args:
            config: Search configuration

        Returns:
            List of raw Vinted items
        """
        try:
            # Record API request for monitoring
            record_vinted_api_request("/search", 200, 0.0)

            # Use the existing Vinted service search method
            search_params = {
                'search_text': config.query.strip(),
                'per_page': config.per_page,
                'max_pages': config.max_pages,
                **config.filters
            }

            # Call the Vinted service search method
            # Note: This assumes the VintedService has a search_items method
            # If it doesn't exist, we'd need to implement it or use the existing method
            if hasattr(self.vinted_service, 'search_items'):
                items = await self.vinted_service.search_items(**search_params)
            else:
                # Fallback: implement basic search using the Vinted client
                items = await self._fallback_search(search_params)

            record_vinted_api_request("/search", 200, 0.0)

            logger.info(f"Vinted search returned {len(items)} items")
            return items

        except Exception as e:
            record_vinted_api_request("/search", 500, 0.0)
            logger.error(f"Vinted search failed: {str(e)}")
            raise VintedServiceUnavailableError(f"Search failed: {str(e)}")

    async def _fallback_search(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fallback search implementation using the Vinted client directly.

        Args:
            search_params: Search parameters

        Returns:
            List of Vinted items
        """
        try:
            # This is a simplified fallback - in a real implementation,
            # you'd use the actual Vinted client methods
            items = []

            for page in range(1, search_params.get('max_pages', 1) + 1):
                page_params = {
                    **search_params,
                    'page': page
                }

                # Simulate API call delay
                await asyncio.sleep(0.5)

                # Here you would call the actual Vinted API
                # For now, return empty list as this is a fallback
                page_items = []  # Replace with actual API call

                if not page_items:
                    break

                items.extend(page_items)

                # Stop if we have enough items
                if len(items) >= search_params.get('max_items', 100):
                    break

            return items

        except Exception as e:
            logger.error(f"Fallback search failed: {str(e)}")
            return []

    async def _process_item_images(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process images for search results.

        Args:
            items: Raw Vinted items

        Returns:
            Items enhanced with image data
        """
        try:
            # Use the image processor to enhance items with image data
            processed_items = self.image_processor.process_search_results(items)

            # Add additional processing if needed
            for item in processed_items:
                # Ensure required fields exist
                if 'title' not in item:
                    item['title'] = 'Unknown Item'

                if 'price' not in item:
                    item['price'] = {'amount': 0.0, 'currency_code': 'EUR'}

                # Add search metadata
                item['_processed_at'] = asyncio.get_event_loop().time()
                item['_has_processed_images'] = item.get('_has_images', False)

            return processed_items

        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            # Return items without enhanced image data
            return items

    async def get_item_with_images(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed item information with processed images.

        Args:
            item_id: Vinted item ID

        Returns:
            Item with enhanced image data or None
        """
        try:
            # Get item details from Vinted service
            if hasattr(self.vinted_service, 'get_item_details'):
                item = await self.vinted_service.get_item_details(item_id)
            else:
                return None

            if not item:
                return None

            # Process images for the item
            processed_items = await self._process_item_images([item])
            return processed_items[0] if processed_items else item

        except Exception as e:
            logger.error(f"Error getting item {item_id} with images: {str(e)}")
            return None

    def get_search_stats(self) -> Dict[str, Any]:
        """Get current search statistics."""
        return {
            'active_searches': self._active_searches,
            'max_concurrent_searches': self.max_concurrent_searches,
            'vinted_service_available': self.vinted_service is not None,
            'image_processor_available': self.image_processor is not None
        }

    async def close(self):
        """Clean up resources."""
        if self.image_processor:
            self.image_processor.close()

        logger.info("VintedScraperService closed")


# Global instance
_scraper_service = None


def get_scraper_service() -> VintedScraperService:
    """Get global scraper service instance."""
    global _scraper_service
    if _scraper_service is None:
        _scraper_service = VintedScraperService()
    return _scraper_service


async def search_vinted_items(query: str, max_items: int, **filters) -> SearchResult:
    """
    Convenience function for searching Vinted items.

    Args:
        query: Search query
        max_items: Maximum number of items to return
        **filters: Additional search filters

    Returns:
        SearchResult with processed items
    """
    config = SearchConfig(
        query=query,
        max_items=max_items,
        filters=filters
    )

    service = get_scraper_service()
    return await service.search_items_with_images(config)
