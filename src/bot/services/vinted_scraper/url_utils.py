"""URL processing utilities."""
from typing import Dict, Any
from urllib.parse import urljoin

def normalize_base_url(url: str) -> str:
    """Normalize base URL by removing trailing slash."""
    return url.rstrip("/")

def create_full_url(item: Dict[str, Any], base_url: str) -> str:
    """Create full URL for an item."""
    if "url" in item and item["url"]:
        url = item["url"]
        if url.startswith("/"):
            return urljoin(base_url, url.lstrip("/"))
        return url
        
    path = item.get("path") or f"/items/{item.get('id')}"
    return urljoin(base_url, path.lstrip("/"))

def enrich_single_item(item: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    """Add full URL to single item."""
    item["url"] = create_full_url(item, base_url)
    return item

def enrich_items_list(items: list, base_url: str) -> list:
    """Add full URLs to list of items."""
    return [enrich_single_item(item, base_url) for item in items]