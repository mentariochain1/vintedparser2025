#!/usr/bin/env python3
"""Simple demo for the Vinted scraper without full bot dependencies."""

import sys
import logging
sys.path.insert(0, 'src/bot/services')

from vinted_scraper import SimpleVintedScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def demo_scraper_components():
    """Demo individual scraper components."""
    print("\n=== Testing Scraper Components ===")
    
    # Test parameter validation
    from vinted_scraper.param_utils import validate_search_params
    text, per_page = validate_search_params("  nike air max  ", 200, 96)
    print(f"Normalized params: '{text}', per_page={per_page}")
    
    # Test URL enrichment
    from vinted_scraper.url_utils import enrich_single_item
    item = {"id": 123456, "path": "/items/123456-test-item"}
    enriched = enrich_single_item(item, "https://www.vinted.at")
    print(f"Enriched URL: {enriched['url']}")
    
    # Test mock generation
    from vinted_scraper.mock_generator import create_mock_results
    mock_items = create_mock_results("nike", "https://www.vinted.at")
    print(f"Generated {len(mock_items)} mock items")
    for item in mock_items[:2]:
        print(f"  • {item['title']} - €{item['price']['amount']}")

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

def main():
    """Run all demos."""
    print("🔍 Vinted Scraper Demo")
    print("=" * 50)
    
    # Test components first
    demo_scraper_components()
    
    # Test direct scraper
    demo_sync_scraper()
    
    print("\n✅ Demo completed successfully!")

if __name__ == "__main__":
    main()