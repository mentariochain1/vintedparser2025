"""Vinted API integration service."""

import time
import random
import requests
import cloudscraper
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlencode, quote
import json
from monitoring import get_logger
logger = get_logger(__name__)
import re
from datetime import datetime, timedelta
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import base64

class SimpleVintedScraper:
    """
    Simplified robust Vinted scraper using only basic requests and BeautifulSoup.
    100% free solution with multiple fallback strategies.
    """

    def __init__(self, base_url: str = "https://www.vinted.at"):
        """Initialize the simple Vinted scraper."""
        self.base_url = base_url
        self.session = requests.Session()
        self.last_request_time = 0
        self.request_delay = random.uniform(2, 4)
        self.session_expires_at = None
        self.session_duration = timedelta(minutes=20)
        self.success_count = 0
        self.request_count = 0

        # Multiple realistic user agents (updated for 2025)
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ]

        self.current_user_agent = random.choice(self.user_agents)
        self.session_id = self._generate_session_id()

        # Image processing settings
        self.max_images_per_item = 10  # Limit images to avoid spam
        self.image_size_limit = 5 * 1024 * 1024  # 5MB limit per image

        logger.info("SimpleVintedScraper initialized")

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16]

    def _get_headers(self, api_request: bool = False) -> Dict[str, str]:
        """Get realistic headers for requests."""
        base_headers = {
            "User-Agent": self.current_user_agent,
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8,de-AT;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

        if api_request:
            base_headers.update({
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": "XMLHttpRequest"
            })
        else:
            base_headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            })

        return base_headers

    def _create_session(self) -> bool:
        """Create a new session with proper initialization using cloudscraper."""
        try:
            # Rotate user agent
            self.current_user_agent = random.choice(self.user_agents)
            self.session_id = self._generate_session_id()

            # Create new cloudscraper session (bypasses Cloudflare)
            self.session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'darwin',
                    'desktop': True
                }
            )
            
            # Update headers after creating cloudscraper session
            self.session.headers.update(self._get_headers())

            logger.info(f"Creating cloudscraper session {self.session_id}")

            # Make initial request to get cookies and establish session
            response = self.session.get(self.base_url, timeout=30)

            if response.status_code == 200:
                self.session_expires_at = datetime.now() + self.session_duration
                cookies = list(response.cookies.keys())
                logger.info(f"Cloudscraper session {self.session_id} created. Cookies: {cookies}")
                
                # Try to get additional session data from the page
                if 'vinted' in response.text.lower():
                    logger.info("Successfully connected to Vinted with cloudscraper")
                else:
                    logger.warning("Response doesn't seem to be from Vinted")
                
                return True
            else:
                logger.error(f"Failed to create cloudscraper session: Status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error creating cloudscraper session: {str(e)}")
            return False

    def _is_session_valid(self) -> bool:
        """Check if current session is valid."""
        if not self.session or not self.session_expires_at:
            return False
        return datetime.now() < self.session_expires_at

    def _ensure_session(self) -> bool:
        """Ensure we have a valid session."""
        if not self._is_session_valid():
            return self._create_session()
        return True

    def _respect_rate_limit(self):
        """Implement rate limiting."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        # Adaptive delay based on success rate
        success_rate = self.success_count / max(self.request_count, 1)
        if success_rate < 0.5 and self.request_count > 3:
            delay = self.request_delay * 3  # Increased delay when failing
        else:
            delay = self.request_delay

        # Add some randomness to make it look more human
        delay += random.uniform(0.5, 1.5)

        if time_since_last_request < delay:
            sleep_time = delay - time_since_last_request
            logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Dict[str, Any] = None, api_request: bool = False, max_retries: int = 3) -> Optional[requests.Response]:
        """Make a request with retry logic."""
        for attempt in range(max_retries):
            try:
                if not self._ensure_session():
                    logger.error("Cannot establish session")
                    return None

                self._respect_rate_limit()

                # Update headers for this request
                headers = self._get_headers(api_request=api_request)

                logger.info(f"Making request to {url} (attempt {attempt + 1}/{max_retries})")

                response = self.session.get(url, params=params, headers=headers, timeout=30)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait_time = (2 ** attempt) * 3
                    logger.warning(f"Rate limited (429). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif response.status_code in [401, 403]:
                    logger.warning(f"Access denied ({response.status_code}). Creating new session...")
                    self.session = None
                    self.session_expires_at = None
                    if not self._create_session():
                        return None
                else:
                    logger.warning(f"Request failed: {response.status_code}")
                    if attempt == max_retries - 1:
                        return None
                    time.sleep(2 ** attempt)

            except requests.exceptions.Timeout:
                logger.error("Request timeout")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2 ** attempt)

        return None

    async def _fetch_search_page_httpx (self ,search_params :Dict [str ,Any ])->List [Dict [str ,Any ]]:
        """Direct HTTP fallback to fetch catalog items when SDK parsing fails."""
        try :
            domain = getattr (self ,'current_domain','at')
            base_url =f"https://www.vinted.{domain}/api/v2/catalog/items"
            # Map parameters to HTTP query
            query_params ={}
            for k ,v in search_params .items ():
                if k =="query":
                    query_params ["search_text"]=v
                else :
                    query_params [k ]=v
            headers ={
            "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Accept":"application/json, text/plain, */*"
            }
            async with httpx .AsyncClient (timeout =self .timeout ,headers =headers )as client :
                resp =await client .get (base_url ,params =query_params )
                status =resp .status_code
                if status !=200 :
                    logger .warning (f"Direct HTTP search returned non-200", status_code=status ,params =query_params ,component ="vinted_service")
                    return []
                data =resp .json ()
                if not isinstance (data ,dict ):
                    return []
                # Reuse heuristic extractor (inline) to get items list
                def _extract_items_from_dict_http (d :Dict [str ,Any ]):
                    for key in ['items','catalog_items','catalogItems','results']:
                        val =d .get (key )
                        if isinstance (val ,list ):
                            return val
                        if isinstance (val ,dict )and isinstance (val .get ('items'),list ):
                            return val .get ('items')
                    for key in ['data','payload','result','catalog','search','feed','content']:
                        val =d .get (key )
                        if isinstance (val ,list ):
                            return val
                        if isinstance (val ,dict ):
                            for inner in ['items','catalog_items','catalogItems','results']:
                                iv =val .get (inner )
                                if isinstance (iv ,list ):
                                    return iv
                    return None
                raw_items =_extract_items_from_dict_http (data )
                if not raw_items or not hasattr (raw_items ,'__iter__'):
                    logger .warning (f"Direct HTTP: no items found in response", keys =list (data .keys ())[:25] ,component ="vinted_service")
                    return []
                # Transform into simplified structure expected by pipeline
                items :List [Dict [str ,Any ]]=[]
                for it in raw_items :
                    try :
                        if not isinstance (it ,dict ):
                            continue
                        item_id =it .get ('id')
                        title =it .get ('title') or it .get ('description') or it .get ('name')
                        if not item_id or not title :
                            continue
                        # Price handling tolerant to multiple shapes
                        price_raw =it .get ('price')
                        currency_code ='EUR'
                        price_value =0.0
                        if isinstance (price_raw ,dict ):
                            amount =price_raw .get ('amount')
                            currency_code =price_raw .get ('currency_code','EUR')
                            try :
                                price_value =float (amount )if amount is not None else 0.0
                            except Exception :
                                price_value =0.0
                        elif isinstance (price_raw ,(int ,float )):
                            price_value =float (price_raw )
                        elif isinstance (price_raw ,str ):
                            try :
                                price_value =float (price_raw .replace (',','.' ))
                            except Exception :
                                price_value =0.0
                        # Preview image from either photo or photos[0]
                        preview =it .get ('photo')
                        if not preview and isinstance (it .get ('photos'),list )and it .get ('photos'):
                            first_photo =it .get ('photos')[0 ]
                            preview =first_photo .get ('full_size_url') or first_photo .get ('url') if isinstance (first_photo ,dict )else first_photo
                        item_dict ={
                        "id":item_id ,
                        "title":title ,
                        "price":price_value ,
                        "currency":currency_code ,
                        "brand":(it .get ('brand') or {}).get ('title') if isinstance (it .get ('brand'),dict )else it .get ('brand'),
                        "size":(it .get ('size') or {}).get ('title') if isinstance (it .get ('size'),dict )else it .get ('size'),
                        "condition":it .get ('condition'),
                        "url":it .get ('url') or f"https://www.vinted.{domain}/items/{item_id}",
                        "preview_img":preview ,
                        "seller_id":(it .get ('user') or {}).get ('id') or it .get ('seller_id'),
                        "ships_to_at":True ,
                        }
                        items .append (item_dict )
                    except Exception :
                        continue
                logger .info (f"Direct HTTP fetched items", count =len (items ) ,component ="vinted_service")
                return items
        except Exception as e :
            logger .error (f"Direct HTTP search failed: {e }", error_type =type (e ).__name__ ,component ="vinted_service")
            return []

    async def search_items (
    self ,
    query :str ,
    max_pages :int =5 ,
    per_page :int =100 ,
    **filters
    )->List [Dict [str ,Any ]]:
        """
        Search for items on Vinted that ship to Austria.

        Args:
            query: Search query string
            max_pages: Maximum number of pages to fetch
            per_page: Items per page (max 100)
            **filters: Additional search filters

        Returns:
            List of item dictionaries
        """
        if not self .vinted_client :
            self ._initialize_client ()

        all_items =[]

        search_params ={
        "query":query ,
        "country_ids":14 ,
        "per_page":min (per_page ,100 ),
        "order":"newest_first",
        **filters
        }

        start_time = time.time()
        try :

            page_tasks =[]
            for page in range (1 ,max_pages +1 ):
                task =self ._fetch_search_page (search_params ,page )
                page_tasks .append (task )

            page_results =await aiometer .run_on_each (
            lambda task :task ,
            page_tasks ,
            max_at_once =self .max_concurrent ,
            max_per_second =self .rate_limit /60 ,
            )

            # Fallback: if run_on_each returns None or non-iterable, use asyncio.gather
            if not page_results or not hasattr(page_results, '__iter__'):
                logger.warning(
                    f"aiometer.run_on_each returned invalid result, falling back to asyncio.gather",
                    result_type=type(page_results).__name__ if page_results is not None else "None",
                    query=query,
                    component="vinted_service"
                )
                # Recreate fresh coroutines to avoid 'cannot reuse already awaited coroutine'
                fallback_tasks = [
                    self._fetch_search_page(search_params, page)
                    for page in range(1, max_pages + 1)
                ]
                page_results = await asyncio.gather(*fallback_tasks, return_exceptions=False)

            # Ensure page_results is not None and is iterable
            if page_results and hasattr(page_results, '__iter__'):
                for page_items in page_results :
                    # Ensure page_items is a non-empty list before extending
                    if page_items and isinstance(page_items, list) and len(page_items) > 0:
                        all_items .extend (page_items )
            else:
                logger.warning(
                    f"aiometer.run_on_each returned invalid result",
                    result_type=type(page_results).__name__ if page_results else "None",
                    query=query,
                    component="vinted_service"
                )

            duration = time.time() - start_time
            record_vinted_api_request("/search", 200, duration)
            
            logger .info (
                f"Found {len (all_items )} items for query: {query }",
                query=query,
                items_count=len(all_items),
                duration_ms=round(duration * 1000, 2)
            )
            return all_items if isinstance(all_items, list) else []

        except Exception as e :
            duration = time.time() - start_time
            record_vinted_api_request("/search", 500, duration)
            
            # Convert to appropriate VintedAPIError
            if "429" in str(e) or "rate limit" in str(e).lower():
                vinted_error = VintedRateLimitError(
                    "Vinted API rate limit exceeded",
                    details={"query": query, "duration": duration}
                )
            elif "503" in str(e) or "unavailable" in str(e).lower():
                vinted_error = VintedServiceUnavailableError(
                    "Vinted service temporarily unavailable",
                    details={"query": query, "duration": duration}
                )
            else:
                vinted_error = VintedAPIError(
                    f"Vinted API error: {str(e)}",
                    details={"query": query, "duration": duration, "original_error": str(e)}
                )
            
            error_handler.log_error(vinted_error, {
                "query": query,
                "duration_ms": round(duration * 1000, 2),
                "component": "vinted_service"
            })
            raise vinted_error

    async def _fetch_search_page (
    self ,
    search_params :Dict [str ,Any ],
    page :int
    )->List [Dict [str ,Any ]]:
        """
        Fetch a single page of search results with retry logic.

        Args:
            search_params: Search parameters
            page: Page number to fetch

        Returns:
            List of items from the page
        """
        params ={**search_params ,"page":page }
        
        # Log the attempt with sanitized parameters (remove sensitive data if any)
        sanitized_params = {
            k: v for k, v in params.items() 
            if k not in ['api_key', 'token', 'authorization']
        }
        logger.debug(
            f"Starting search page fetch",
            page=page,
            params=sanitized_params,
            component="vinted_service"
        )

        for attempt in range (3 ):
            try :

                if attempt >0 :
                    delay =2 **attempt
                    logger.info(
                        f"Retrying page {page} after delay",
                        page=page,
                        attempt=attempt + 1,
                        delay_seconds=delay,
                        component="vinted_service"
                    )
                    await asyncio .sleep (delay )

                try:
                    result = self.vinted_client.search(**params)
                    
                    # Log successful API response with result structure info
                    logger.debug(
                        f"Vinted API response received",
                        page=page,
                        attempt=attempt + 1,
                        result_type=type(result).__name__,
                        result_structure={
                            "has_items_attr": hasattr(result, 'items'),
                            "has_error_attr": hasattr(result, 'error'),
                            "is_dict": isinstance(result, dict),
                            "is_none": result is None,
                        },
                        component="vinted_service"
                    )
                    
                    # Check if Vinted returned an actual error response (not just HTTP status)
                    if isinstance(result, dict) and 'error' in result:
                        error_value = result.get('error')
                        # Only treat it as an error if it's not just an HTTP status
                        if error_value and not str(error_value).startswith('HTTP '):
                            logger.warning(
                                f"Vinted API returned error response",
                                page=page,
                                attempt=attempt + 1,
                                error_type="api_error_response",
                                error_data=error_value,
                                params=sanitized_params,
                                component="vinted_service"
                            )
                            # Fall back to direct HTTP call to tolerate schema changes
                            http_items = await self._fetch_search_page_httpx({**params})
                            return http_items or []
                    
                    # Check if result is None or falsy
                    if not result:
                        logger.warning(
                            f"Vinted API returned empty/null result",
                            page=page,
                            attempt=attempt + 1,
                            result_type=type(result).__name__,
                            params=sanitized_params,
                            component="vinted_service"
                        )
                        # Try direct HTTP fallback
                        http_items = await self._fetch_search_page_httpx({**params})
                        return http_items or []
                    
                except Exception as search_error:
                    logger.error(
                        f"Vinted search failed with parsing error",
                        page=page,
                        attempt=attempt + 1,
                        error_type=type(search_error).__name__,
                        error_message=str(search_error),
                        params=sanitized_params,
                        component="vinted_service"
                    )
                    # Retry on transient/parsing errors instead of exiting immediately
                    if attempt < 2:
                        continue
                    else:
                        logger.error(
                            f"Failed to fetch page after parsing errors",
                            page=page,
                            total_attempts=3,
                            final_error_type=type(search_error).__name__,
                            final_error_message=str(search_error),
                            params=sanitized_params,
                            component="vinted_service"
                        )
                        # Final fallback on parse failures
                        http_items = await self._fetch_search_page_httpx({**params})
                        return http_items or []

                # Enhanced debug logging to understand the result structure
                result_info = {
                    "type": type(result).__name__,
                    "has_items_attr": hasattr(result, 'items'),
                    "items_type": type(getattr(result, 'items', None)).__name__ if hasattr(result, 'items') else None,
                    "items_callable": callable(getattr(result, 'items', None)) if hasattr(result, 'items') else False,
                    "items_is_none": getattr(result, 'items', None) is None if hasattr(result, 'items') else True
                }
                
                logger.debug(
                    f"Analyzing search result structure",
                    page=page,
                    result_info=result_info,
                    component="vinted_service"
                )
                # If result is a dict, log its top-level keys for diagnostics
                if isinstance(result, dict):
                    try:
                        logger.debug(
                            f"Vinted result top-level keys",
                            page=page,
                            keys=list(result.keys())[:25],
                            component="vinted_service"
                        )
                    except Exception:
                        pass

                # Helper to try extracting items list from various shapes
                def _extract_items_from_dict(data: Dict[str, Any]):
                    # Known direct keys
                    for key in ['items', 'catalog_items', 'catalogItems', 'results']:
                        value = data.get(key)
                        if isinstance(value, list):
                            return value
                        if isinstance(value, dict):
                            for inner_key in ['items', 'results']:
                                inner = value.get(inner_key)
                                if isinstance(inner, list):
                                    return inner
                    # Common containers
                    for key in ['data', 'payload', 'result', 'catalog', 'search', 'feed', 'content']:
                        value = data.get(key)
                        if isinstance(value, list):
                            return value
                        if isinstance(value, dict):
                            for inner_key in ['items', 'catalog_items', 'catalogItems', 'results']:
                                inner = value.get(inner_key)
                                if isinstance(inner, list):
                                    return inner
                            # One more nested level for common shapes like data.catalog.items
                            for first in ['data', 'catalog', 'result', 'payload']:
                                nested = value.get(first)
                                if isinstance(nested, dict):
                                    for inner_key in ['items', 'catalog_items', 'catalogItems', 'results']:
                                        inner = nested.get(inner_key)
                                        if isinstance(inner, list):
                                            return inner
                    # Heuristic scan for list of item-like dicts
                    def _is_item_like(x: Any) -> bool:
                        return isinstance(x, dict) and (
                            'id' in x or 'title' in x or 'url' in x
                        )
                    for _, v in data.items():
                        if isinstance(v, list) and any(_is_item_like(e) for e in v):
                            return v
                        if isinstance(v, dict):
                            for __, vv in v.items():
                                if isinstance(vv, list) and any(_is_item_like(e) for e in vv):
                                    return vv
                    return None

                # Validate that result has items and process accordingly
                # Important: for dicts, don't use hasattr(result, 'items') since that's the dict.items() method
                dict_has_items_key = isinstance(result, dict) and (
                    ('items' in result) or ('catalog_items' in result) or ('catalogItems' in result)
                )
                obj_has_items_attr = (not isinstance(result, dict)) and hasattr(result, 'items')
                if dict_has_items_key or obj_has_items_attr:
                    items = []
                    
                    # Handle both object attribute and dict key access
                    if isinstance(result, dict):
                        # Try known keys used by Vinted APIs
                        result_items = (
                            result.get('items')
                            or result.get('catalog_items')
                            or result.get('catalogItems')
                        )
                    else:
                        result_items = result.items
                        if callable(result_items):
                            result_items = result_items()
                    
                    # Log items extraction result
                    logger.debug(
                        f"Extracted items from result",
                        page=page,
                        items_extracted=result_items is not None,
                        items_type=type(result_items).__name__ if result_items else None,
                        items_iterable=hasattr(result_items, '__iter__') if result_items else False,
                        component="vinted_service"
                    )
                    
                    # Ensure result_items is iterable and not None
                    if result_items and hasattr(result_items, '__iter__'):
                        items = []  # Ensure we always have a list to work with
                        items_processed = 0
                        items_skipped = 0
                        skip_reasons = {}
                        
                        for item in result_items:
                            try:
                                # Handle both tuple and dict/object formats
                                if isinstance(item, tuple):
                                    # Skip tuples as they're not proper item objects
                                    logger.debug(
                                        f"Skipping tuple item",
                                        page=page,
                                        item_type="tuple",
                                        item_content=str(item)[:100] + "..." if len(str(item)) > 100 else str(item),
                                        component="vinted_service"
                                    )
                                    items_skipped += 1
                                    skip_reasons["tuple_format"] = skip_reasons.get("tuple_format", 0) + 1
                                    continue
                                
                                # Function to safely get item attribute/key
                                def get_item_value(item, key, default=None):
                                    if isinstance(item, dict):
                                        return item.get(key, default)
                                    else:
                                        return getattr(item, key, default)
                                
                                # Check if item has required fields
                                item_id = get_item_value(item, 'id')
                                item_title = get_item_value(item, 'title')
                                
                                if not item_id or not item_title:
                                    missing_fields = []
                                    if not item_id:
                                        missing_fields.append('id')
                                    if not item_title:
                                        missing_fields.append('title')
                                    
                                    logger.debug(
                                        f"Skipping item without required fields",
                                        page=page,
                                        item_type=type(item).__name__,
                                        missing_fields=missing_fields,
                                        available_fields=list(item.keys()) if isinstance(item, dict) else [attr for attr in dir(item) if not attr.startswith('_')],
                                        component="vinted_service"
                                    )
                                    items_skipped += 1
                                    skip_reasons["missing_required_fields"] = skip_reasons.get("missing_required_fields", 0) + 1
                                    continue
                                
                                # Extract item data
                                item_price = get_item_value(item, 'price')
                                item_dict = {
                                    "id": item_id,
                                    "title": item_title,
                                    "price": float(item_price) if item_price else 0.0,
                                    "currency": get_item_value(item, 'currency', 'EUR'),
                                    "brand": get_item_value(item, 'brand'),
                                    "size": get_item_value(item, 'size'),
                                    "condition": get_item_value(item, 'condition'),
                                    "url": get_item_value(item, 'url', f"https://www.vinted.at/items/{item_id}"),
                                    "preview_img": get_item_value(item, 'photo'),
                                    "seller_id": get_item_value(item, 'seller_id'),
                                    "ships_to_at": True,
                                }
                                
                                # Only add items with valid IDs
                                if item_dict["id"]:
                                    items.append(item_dict)
                                    items_processed += 1
                                else:
                                    logger.debug(
                                        f"Skipping item with invalid/missing ID",
                                        page=page,
                                        item_title=item_dict.get("title", "Unknown")[:50],
                                        item_id=item_dict["id"],
                                        component="vinted_service"
                                    )
                                    items_skipped += 1
                                    skip_reasons["invalid_id"] = skip_reasons.get("invalid_id", 0) + 1
                                
                            except Exception as item_error:
                                logger.warning(
                                    f"Error processing individual item",
                                    page=page,
                                    error_type=type(item_error).__name__,
                                    error_message=str(item_error),
                                    item_type=type(item).__name__,
                                    component="vinted_service"
                                )
                                items_skipped += 1
                                skip_reasons["processing_error"] = skip_reasons.get("processing_error", 0) + 1
                                continue

                        # Log comprehensive page processing results
                        logger.info(
                            f"Completed page {page} processing",
                            page=page,
                            attempt=attempt + 1,
                            items_found=len(items),
                            items_processed=items_processed,
                            items_skipped=items_skipped,
                            skip_reasons=skip_reasons,
                            params=sanitized_params,
                            component="vinted_service"
                        )
                        return items if items else []  # Always return a list
                    else:
                        logger.warning(
                            f"Result items is not iterable or is empty",
                            page=page,
                            attempt=attempt + 1,
                            result_items_type=type(result_items).__name__ if result_items is not None else "None",
                            result_items_value=(str(result_items)[:100] if result_items is not None else "None"),
                            params=sanitized_params,
                            component="vinted_service"
                        )
                        # Final fallback: perform a single-page direct HTTP fetch
                        http_items = await self._fetch_search_page_httpx({**params})
                        return http_items or []
                else:
                    # Try heuristic extraction for dict results
                    if isinstance(result, dict):
                        heuristic_items = _extract_items_from_dict(result)
                        if heuristic_items and hasattr(heuristic_items, '__iter__'):
                            result_items = heuristic_items
                            logger.info(
                                f"Extracted items using heuristic keys",
                                page=page,
                                attempt=attempt + 1,
                                items_count=len(result_items),
                                params=sanitized_params,
                                component="vinted_service"
                            )
                            # Process items using existing pipeline
                            items = []
                            items_processed = 0
                            items_skipped = 0
                            skip_reasons = {}
                            for item in result_items:
                                try:
                                    if isinstance(item, tuple):
                                        items_skipped += 1
                                        skip_reasons["tuple_format"] = skip_reasons.get("tuple_format", 0) + 1
                                        continue
                                    def get_item_value(item, key, default=None):
                                        if isinstance(item, dict):
                                            return item.get(key, default)
                                        else:
                                            return getattr(item, key, default)
                                    item_id = get_item_value(item, 'id')
                                    item_title = get_item_value(item, 'title') or get_item_value(item, 'description') or get_item_value(item, 'name')
                                    if not item_id or not item_title:
                                        items_skipped += 1
                                        skip_reasons["missing_required_fields"] = skip_reasons.get("missing_required_fields", 0) + 1
                                        continue
                                    item_price = get_item_value(item, 'price')
                                    item_dict = {
                                        "id": item_id,
                                        "title": item_title,
                                        "price": float(item_price) if isinstance(item_price, (int, float, str)) and str(item_price).replace('.', '', 1).isdigit() else 0.0,
                                        "currency": get_item_value(item, 'currency', 'EUR'),
                                        "brand": get_item_value(item, 'brand') or (get_item_value(item, 'brand', {}) or {}).get('title') if isinstance(get_item_value(item, 'brand'), dict) else get_item_value(item, 'brand'),
                                        "size": get_item_value(item, 'size') or (get_item_value(item, 'size', {}) or {}).get('title') if isinstance(get_item_value(item, 'size'), dict) else get_item_value(item, 'size'),
                                        "condition": get_item_value(item, 'condition'),
                                        "url": get_item_value(item, 'url', f"https://www.vinted.at/items/{item_id}"),
                                        "preview_img": get_item_value(item, 'photo') or (get_item_value(item, 'photos') or [{}])[0] if isinstance(get_item_value(item, 'photos'), list) and get_item_value(item, 'photos') else None,
                                        "seller_id": get_item_value(item, 'seller_id'),
                                        "ships_to_at": True,
                                    }
                                    items.append(item_dict)
                                    items_processed += 1
                                except Exception:
                                    items_skipped += 1
                                    skip_reasons["processing_error"] = skip_reasons.get("processing_error", 0) + 1
                                    continue
                            logger.info(
                                f"Completed page {page} heuristic processing",
                                page=page,
                                attempt=attempt + 1,
                                items_found=len(items),
                                items_processed=items_processed,
                                items_skipped=items_skipped,
                                skip_reasons=skip_reasons,
                                params=sanitized_params,
                                component="vinted_service"
                            )
                            return items if items else []

                    logger.warning(
                        f"Result does not contain items list",
                        page=page,
                        attempt=attempt + 1,
                        result_type=type(result).__name__,
                        is_dict=isinstance(result, dict),
                        has_items_attr=(hasattr(result, 'items') if not isinstance(result, dict) else False),
                        available_attrs=[attr for attr in dir(result) if not attr.startswith('_')] if result and not isinstance(result, dict) else [],
                        params=sanitized_params,
                        component="vinted_service"
                    )
                    # Final fallback: direct HTTP fetch
                    http_items = await self._fetch_search_page_httpx({**params})
                    return http_items or []

            except Exception as e :
                logger.error(
                    f"Page fetch attempt failed",
                    page=page,
                    attempt=attempt + 1,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    params=sanitized_params,
                    component="vinted_service"
                )
                if attempt ==2 :
                    logger.error(
                        f"Failed to fetch page after all attempts",
                        page=page,
                        total_attempts=3,
                        final_error_type=type(e).__name__,
                        final_error_message=str(e),
                        params=sanitized_params,
                        component="vinted_service"
                    )
                    return []

        # This should never be reached due to the logic above, but adding for completeness
        logger.error(
            f"Unexpected end of retry loop for page {page}",
            page=page,
            params=sanitized_params,
            component="vinted_service"
        )
        return []

    async def get_item_details (self ,item_ids :List [int ])->List [Dict [str ,Any ]]:
        """
        Fetch detailed information for multiple items including all photos.

        Args:
            item_ids: List of item IDs to fetch details for

        Returns:
            List of detailed item dictionaries
        """
        if not self .vinted_client :
            self ._initialize_client ()

        if not item_ids :
            return []

        start_time = time.time()
        try :

            detail_tasks =[
            self ._fetch_item_detail (item_id )for item_id in item_ids
            ]

            detailed_items =await aiometer .run_on_each (
            lambda task :task ,
            detail_tasks ,
            max_at_once =self .max_concurrent ,
            max_per_second =self .rate_limit /60 ,
            )

            # Fallback in case of None/non-iterable from aiometer
            if not detailed_items or not hasattr(detailed_items, '__iter__'):
                logger.warning(
                    f"aiometer.run_on_each returned invalid result for details, falling back to asyncio.gather",
                    result_type=type(detailed_items).__name__ if detailed_items is not None else "None",
                    requested_count=len(item_ids)
                )
                # Recreate fresh coroutines
                fallback_detail_tasks = [
                    self._fetch_item_detail(item_id) for item_id in item_ids
                ]
                detailed_items = await asyncio.gather(*fallback_detail_tasks, return_exceptions=False)

            valid_items =[item for item in detailed_items if item is not None ]

            duration = time.time() - start_time
            record_vinted_api_request("/item_details", 200, duration)

            logger .info (
                f"Fetched details for {len (valid_items )}/{len (item_ids )} items",
                requested_count=len(item_ids),
                fetched_count=len(valid_items),
                duration_ms=round(duration * 1000, 2)
            )
            return valid_items

        except Exception as e :
            duration = time.time() - start_time
            record_vinted_api_request("/item_details", 500, duration)
            
            logger .error (
                f"Error fetching item details: {e }",
                requested_count=len(item_ids),
                error_type=type(e).__name__,
                component="vinted_service",
                duration_ms=round(duration * 1000, 2)
            )
            raise

    async def _fetch_item_detail (self ,item_id :int )->Optional [Dict [str ,Any ]]:
        """
        Fetch detailed information for a single item with retry logic.

        Args:
            item_id: Item ID to fetch details for

        Returns:
            Detailed item dictionary or None if failed
        """
        for attempt in range (3 ):
            try :

                if attempt >0 :
                    delay =2 **attempt
                    await asyncio .sleep (delay )

                item_info =self .vinted_client .item_info (item_id )

                if item_info and hasattr (item_info ,'item'):
                    item =item_info .item

                    photos =[]
                    if hasattr (item ,'photos')and item .photos :
                        for photo in item .photos :
                            photo_url =photo .url if hasattr (photo ,'url')else str (photo )
                            photos .append (photo_url )

                    item_dict ={
                    "id":item .id ,
                    "title":item .title ,
                    "price":float (item .price )if item .price else 0.0 ,
                    "currency":getattr (item ,'currency','EUR'),
                    "brand":getattr (item ,'brand',None ),
                    "size":getattr (item ,'size',None ),
                    "condition":getattr (item ,'condition',None ),
                    "description":getattr (item ,'description',None ),
                    "seller_id":getattr (item ,'seller_id',None ),
                    "url":item .url if hasattr (item ,'url')else f"https://www.vinted.at/items/{item .id }",
                    "preview_img":photos [0 ]if photos else None ,
                    "photos":photos ,
                    "ships_to_at":True ,
                    }

                    logger .debug (f"Fetched details for item {item_id }")
                    return item_dict
                else :
                    logger .warning (f"No details found for item {item_id }")
                    return None

            except Exception as e :
                logger .warning (f"Attempt {attempt +1 } failed for item {item_id }: {e }")
                if attempt ==2 :
                    logger .error (f"Failed to fetch item {item_id } after 3 attempts: {e }")
                    return None

        return None

    async def search_and_get_details (
    self ,
    query :str ,
    max_pages :int =5 ,
    per_page :int =100 ,
    **filters
    )->List [Dict [str ,Any ]]:
        """
        Search for items and fetch their detailed information in one call.

        Args:
            query: Search query string
            max_pages: Maximum number of pages to fetch
            per_page: Items per page (max 100)
            **filters: Additional search filters

        Returns:
            List of detailed item dictionaries
        """

        search_results =await self .search_items (
        query =query ,
        max_pages =max_pages ,
        per_page =per_page ,
        **filters
        )

        if not search_results :
            return []

        item_ids =[item ["id"]for item in search_results ]

        detailed_items =await self .get_item_details (item_ids )

        return detailed_items

    def get_item_url (self ,item_id :int )->str :
        """
        Generate Vinted item URL.

        Args:
            item_id: Item ID

        Returns:
            Full Vinted item URL
        """
        return f"https://www.vinted.at/items/{item_id }"

    async def health_check (self )->bool :
        """
        Perform a health check by making a simple search request.

        Returns:
            True if service is healthy, False otherwise
        """
        start_time = time.time()
        try :

            result =await self .search_items (
            query ="test",
            max_pages =1 ,
            per_page =1
            )
            
            duration = time.time() - start_time
            record_vinted_api_request("/health_check", 200, duration)
            
            logger.info(
                "Vinted service health check passed",
                duration_ms=round(duration * 1000, 2)
            )
            return True
        except Exception as e :
            duration = time.time() - start_time
            record_vinted_api_request("/health_check", 500, duration)
            
            logger .error (
                f"Vinted service health check failed: {e }",
                error_type=type(e).__name__,
                component="vinted_service",
                duration_ms=round(duration * 1000, 2)
            )
            return False 