"""Parameter validation and building utilities."""
from typing import Any, Dict

def normalize_search_text(text: str) -> str:
    """Normalize search text."""
    return text.strip()

def normalize_per_page(per_page: int, max_per_page: int) -> int:
    """Normalize per_page parameter."""
    return min(per_page, max_per_page)

def validate_search_params(search_text: str, per_page: int, max_per_page: int) -> tuple:
    """Validate and normalize search parameters."""
    normalized_text = normalize_search_text(search_text)
    normalized_per_page = normalize_per_page(per_page, max_per_page)
    return normalized_text, normalized_per_page

def build_base_params(search_text: str, page: int, per_page: int) -> Dict[str, Any]:
    """Build base search parameters."""
    return {
        "search_text": search_text,
        "page": page,
        "per_page": per_page,
    }

def add_filters_to_params(params: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
    """Add non-None filters to parameters."""
    for key, value in filters.items():
        if value is not None:
            params[key] = value
    return params

def build_search_params(search_text: str, page: int, per_page: int, **filters) -> Dict[str, Any]:
    """Build complete search parameters."""
    params = build_base_params(search_text, page, per_page)
    return add_filters_to_params(params, filters)