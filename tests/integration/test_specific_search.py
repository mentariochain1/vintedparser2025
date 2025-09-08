#!/usr/bin/env python3
"""Test search for specific terms that might be returning mock data."""

import sys
import os
sys.path.append('src')

from bot.services.vinted_scraper.scraper import SimpleVintedScraper
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

def test_specific_searches():
    """Test specific search terms."""
    print("Testing specific search terms...")
    
    scraper = SimpleVintedScraper(base_url="https://www.vinted.at")
    
    search_terms = ["nike", "adidas", "shirt", "dri-fit"]
    
    try:
        for term in search_terms:
            print(f"\n{'='*50}")
            print(f"Testing search for: '{term}'")
            print('='*50)
            
            results = scraper.search(term, per_page=3)
            
            print(f"Results count: {len(results)}")
            
            if results:
                for i, item in enumerate(results, 1):
                    print(f"\nItem {i}:")
                    print(f"  ID: {item.get('id')}")
                    print(f"  Title: {item.get('title')}")
                    price = item.get('price', {})
                    print(f"  Price: {price.get('amount')} {price.get('currency_code')}")
                    brand = item.get('brand', {}) or item.get('brand_title', '')
                    print(f"  Brand: {brand.get('title') if isinstance(brand, dict) else brand}")
                    print(f"  URL: {item.get('url')}")
                    
                    # Check data source
                    if item.get('_mock'):
                        print("  🔴 MOCK DATA - This should not happen!")
                    elif item.get('_source') == 'vinted_api':
                        print("  🟢 REAL API DATA")
                    elif item.get('_fallback'):
                        print("  🟡 FALLBACK DATA")
                    else:
                        print("  ❓ UNKNOWN SOURCE")
                        
                    # Check if ID looks realistic (Vinted IDs are usually 10 digits)
                    item_id = item.get('id')
                    if item_id and len(str(item_id)) >= 10:
                        print("  ✅ Realistic ID format")
                    else:
                        print("  ❌ Suspicious ID format")
            else:
                print("❌ No results returned")
                
    except Exception as e:
        print(f"❌ Error during search: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

if __name__ == "__main__":
    test_specific_searches()