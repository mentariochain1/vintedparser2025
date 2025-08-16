"""Mock data generation utilities."""
import random
from typing import List, Dict, Any, Tuple
from .brand_data import BRAND_ITEMS, DEFAULT_ITEMS, PRICE_RANGES

def find_brand_items(search_term: str) -> Tuple[list, str]:
    """Find brand-specific items or return defaults."""
    search_lower = search_term.lower()
    
    for brand, brand_items_list in BRAND_ITEMS.items():
        if brand in search_lower:
            return brand_items_list, brand.title()
    
    return DEFAULT_ITEMS, search_term.title()

def generate_random_item_count() -> int:
    """Generate random number of items (3-5)."""
    return random.randint(3, 5)

def generate_item_id() -> int:
    """Generate realistic Vinted item ID."""
    return random.randint(466000000, 466999999)

def create_url_slug(title: str) -> str:
    """Create URL slug from item title."""
    slug = title.lower().replace(' ', '-').replace('&', 'and')
    return ''.join(c for c in slug if c.isalnum() or c == '-')

def generate_item_price(category: str) -> float:
    """Generate realistic price for category."""
    min_price, max_price = PRICE_RANGES.get(category, (15, 80))
    return round(random.uniform(min_price, max_price), 2)

def create_item_title(brand_name: str, item_name: str) -> str:
    """Create full item title."""
    return f"{brand_name} {item_name}"

def generate_user_login() -> str:
    """Generate random user login."""
    return f"user{random.randint(1000, 9999)}"

def generate_photo_url(item_id: int) -> str:
    """Generate photo URL for item."""
    random_num = random.randint(100, 999)
    return f"https://images1.vinted.net/t/01_00_{random_num}/{item_id}.jpeg?s=312x624"

def create_mock_item(brand_name: str, item_name: str, category: str, sizes: List[str], base_url: str) -> Dict[str, Any]:
    """Create single mock item."""
    item_id = generate_item_id()
    title = create_item_title(brand_name, item_name)
    url_slug = create_url_slug(title)
    price = generate_item_price(category)
    
    return {
        "id": item_id,
        "title": title,
        "price": {"amount": price, "currency_code": "EUR"},
        "brand": {"title": brand_name, "slug": brand_name.lower()},
        "size": {"title": random.choice(sizes)},
        "user": {"login": generate_user_login()},
        "photo": {"url": generate_photo_url(item_id)},
        "url": f"{base_url}/items/{item_id}-{url_slug}",
        "path": f"/items/{item_id}-{url_slug}",
        "_mock": True,
        "_realistic": True
    }

def create_mock_results(search_term: str, base_url: str) -> List[Dict[str, Any]]:
    """Create list of realistic mock items."""
    items_pool, brand_name = find_brand_items(search_term)
    num_results = generate_random_item_count()
    
    results = []
    for _ in range(num_results):
        item_name, category, sizes = random.choice(items_pool)
        mock_item = create_mock_item(brand_name, item_name, category, sizes, base_url)
        results.append(mock_item)
    
    return results