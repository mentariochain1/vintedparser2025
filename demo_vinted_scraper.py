#!/usr/bin/env python3
"""Demo script for the new Vinted scraper implementation."""

import asyncio
import logging
from src.bot.services.vinted_service import VintedService
from src.bot.services.vinted_scraper import SimpleVintedScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def demo_async_service():
    """Demo the async VintedService wrapper."""
    print("\n=== Testing Async VintedService ===")
    
    service = VintedService(verify_ssl=False)
    
    try:
        # Test search
        results = await service.search_items("nike", per_page=3)
        
        print(f"Found {len(results)} items:")
        for item in results:
            print(f"  • {item['title']}")
            print(f"    Price: €{item['price']['amount']}")
            print(f"    URL: {item['url']}")
            print(f"    Mock: {item.get('_mock', item.get('_fallback', False))}")
            print()
    
    finally:
        service.close()

def demo_sync_scraper():
    """Demo the direct scraper usage."""
    print("\n=== Testing Direct Scraper ===")
    
    with SimpleVintedScraper(verify_ssl=False) as scraper:
        # Test different search terms
        search_terms = ["nike", "adidas", "vintage", "hoodie"]
        
        for term in search_terms:
            print(f"\nSearching for '{term}':")
            results = scraper.search(term, per_page=2)
            
            for item in results:
                print(f"  • {item['title']}")
                print(f"    Brand: {item['brand']['title']}")
                print(f"    Size: {item['size']['title']}")
                print(f"    Price: €{item['price']['amount']}")
                print(f"    Mock: {item.get('_mock', False)}")

def demo_scraper_components():
    """Demo individual scraper components."""
    print("\n=== Testing Scraper Components ===")
    
    # Test parameter validation
    from src.bot.services.vinted_scraper.param_utils import validate_search_params
    text, per_page = validate_search_params("  nike air max  ", 200, 96)
    print(f"Normalized params: '{text}', per_page={per_page}")
    
    # Test URL enrichment
    from src.bot.services.vinted_scraper.url_utils import enrich_single_item
    item = {"id": 123456, "path": "/items/123456-test-item"}
    enriched = enrich_single_item(item, "https://www.vinted.at")
    print(f"Enriched URL: {enriched['url']}")
    
    # Test mock generation
    from src.bot.services.vinted_scraper.mock_generator import create_mock_results
    mock_items = create_mock_results("nike", "https://www.vinted.at")
    print(f"Generated {len(mock_items)} mock items")
    for item in mock_items[:2]:
        print(f"  • {item['title']} - €{item['price']['amount']}")

async def main():
    """Run all demos."""
    print("🔍 Vinted Scraper Demo")
    print("=" * 50)
    
    # Test components first
    demo_scraper_components()
    
    # Test direct scraper
    demo_sync_scraper()
    
    # Test async service
    await demo_async_service()
    
    print("\n✅ Demo completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())