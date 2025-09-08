"""Main Vinted scraper class."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from urllib.parse import urljoin

from .config import DEFAULT_DOMAIN, MAX_PER_PAGE
from .session_manager import SessionManager
from .param_utils import validate_search_params, build_search_params
from .response_utils import parse_api_response, has_valid_items
from .url_utils import enrich_items_list
from .mock_generator import create_mock_results

log = logging.getLogger("SimpleVintedScraper")

class SimpleVintedScraper:
    """Minimal, robust Vinted scraper with working item URLs."""
    
    def __init__(self, base_url: str = DEFAULT_DOMAIN, *, mobile: bool = False, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.session_manager = SessionManager(self.base_url, mobile, verify_ssl)

    def search(self, search_text: str, page: int = 1, per_page: int = 24, **filters: Any) -> List[Dict[str, Any]]:
        """Search Vinted listings with working URLs."""
        # Validate and normalize inputs
        search_text, per_page = validate_search_params(search_text, per_page, MAX_PER_PAGE)
        
        if not search_text:
            return []

        # Build and execute request
        params = build_search_params(search_text, page, per_page, **filters)
        api_url = urljoin(self.base_url, "/api/v2/catalog/items")
        
        try:
            response = self.session_manager.make_request(api_url, params)
        except Exception as e:
            log.error("Request failed with exception: %s", e)
            # If SSL error and we're using SSL verification, try without SSL
            if "SSL" in str(e) and self.session_manager.verify_ssl:
                log.warning("SSL error detected, retrying without SSL verification")
                self.session_manager.verify_ssl = False
                try:
                    self.session_manager.create_session()
                    response = self.session_manager.make_request(api_url, params)
                except Exception as retry_error:
                    log.error("Retry without SSL also failed: %s", retry_error)
                    return []
            else:
                return []
        
        # Process response
        items = self._process_response(response, search_text)
        return enrich_items_list(items, self.base_url)

    def _process_response(self, response, search_text: str) -> List[Dict[str, Any]]:
        """Process API response, prioritize real data over mock."""
        if response is None:
            log.error("No response received from API - this should not happen if session is working")
            return []

        # Log response details for debugging
        log.info("Processing API response: status=%d, content_type=%s, size=%d bytes", 
                response.status_code, response.headers.get('content-type', 'unknown'), len(response.content))

        items = parse_api_response(response)
        
        if not has_valid_items(items):
            log.warning("API returned no items for search: %s", search_text)
            # Don't fall back to mock data - return empty list for real searches
            return []

        log.info("Successfully retrieved %d real items from API for search: %s", len(items), search_text)
        
        # Add debug info to items to distinguish from mock
        for item in items:
            item['_source'] = 'vinted_api'
            item['_search_term'] = search_text
            
        return items

    def search_items(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """Compatibility alias for search method."""
        return self.search(*args, **kwargs)

    def close(self) -> None:
        """Close scraper and cleanup resources."""
        self.session_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Legacy alias
VintedService = SimpleVintedScraper