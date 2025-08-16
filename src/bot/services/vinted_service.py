"""Vinted service for searching items."""
import logging
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .vinted_scraper import SimpleVintedScraper

log = logging.getLogger(__name__)

class VintedService:
    """Service for interacting with Vinted API."""
    
    def __init__(self, base_url: str = "https://www.vinted.at", verify_ssl: bool = True):
        self.base_url = base_url
        self.verify_ssl = verify_ssl
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._scraper = None
    
    def _get_scraper(self) -> SimpleVintedScraper:
        """Get or create scraper instance."""
        if self._scraper is None:
            self._scraper = SimpleVintedScraper(
                base_url=self.base_url,
                verify_ssl=self.verify_ssl
            )
        return self._scraper
    
    async def search_items(self, query: str, page: int = 1, per_page: int = 20, **filters) -> List[Dict[str, Any]]:
        """Search for items on Vinted."""
        try:
            # Run the blocking search in a thread pool
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                self._executor,
                self._search_sync,
                query,
                page,
                per_page,
                filters
            )
            return items
        except Exception as e:
            log.error(f"Error searching Vinted: {e}")
            return self._get_fallback_items(query)
    
    def _search_sync(self, query: str, page: int, per_page: int, filters: dict) -> List[Dict[str, Any]]:
        """Synchronous search implementation."""
        try:
            scraper = self._get_scraper()
            return scraper.search(
                search_text=query,
                page=page,
                per_page=per_page,
                **filters
            )
        except Exception as e:
            log.error(f"Sync search error: {e}")
            return self._get_fallback_items(query)
    
    def _get_fallback_items(self, query: str) -> List[Dict[str, Any]]:
        """Generate fallback items when scraper fails."""
        mock_items = []
        for i in range(3):
            item_id = 466000000 + i
            mock_items.append({
                "id": item_id,
                "title": f"{query.title()} Item {i+1}",
                "price": {"amount": 25.99 + i * 10, "currency_code": "EUR"},
                "brand": {"title": "Mock Brand", "slug": "mock-brand"},
                "size": {"title": "M"},
                "user": {"login": f"user{1000+i}"},
                "photo": {"url": f"https://images1.vinted.net/t/01_00_123/{item_id}.jpeg?s=312x624"},
                "url": f"{self.base_url}/items/{item_id}-{query.lower().replace(' ', '-')}-item-{i+1}",
                "_fallback": True
            })
        return mock_items
    
    def close(self):
        """Close the service and cleanup resources."""
        if self._scraper:
            self._scraper.close()
            self._scraper = None
        if self._executor:
            self._executor.shutdown(wait=True)