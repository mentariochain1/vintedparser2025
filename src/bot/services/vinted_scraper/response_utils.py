"""Response processing utilities."""
import logging
from typing import List, Dict, Any
import requests

log = logging.getLogger("VintedResponseUtils")

def extract_json_data(response: requests.Response) -> dict:
    """Extract JSON data from response."""
    try:
        return response.json()
    except (ValueError, AttributeError) as e:
        log.error("Failed to parse JSON response: %s", e)
        return {}

def extract_items_from_data(data: dict) -> List[Dict[str, Any]]:
    """Extract items array from response data."""
    return data.get("items", [])

def parse_api_response(response: requests.Response) -> List[Dict[str, Any]]:
    """Parse API response and extract items."""
    data = extract_json_data(response)
    return extract_items_from_data(data)

def has_valid_items(items: List[Dict[str, Any]]) -> bool:
    """Check if items list is valid and not empty."""
    return bool(items)