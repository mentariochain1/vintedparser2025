#!/usr/bin/env python3
"""Test the current scraper implementation."""

import sys
import os
sys.path.append('src')

from bot.services.vinted_scraper.scraper import SimpleVintedScraper
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

def test_scraper():
    """Test the current scraper implementation."""
    print("Testing current Vinted scraper...")
    
    scraper = SimpleVintedScraper(base_url="https://www.vinted.at")
    
    try:
        # Test search
        print("\n1. Testing search for 'nike'...")
        results = scraper.search("nike", per_page=5)
        
        print(f"Results count: {len(results)}")
        
        if results:
            for i, item in enumerate(results, 1):
                print(f"\nItem {i}:")
                print(f"  ID: {item.get('id')}")
                print(f"  Title: {item.get('title')}")
                print(f"  Price: {item.get('price', {}).get('amount')} {item.get('price', {}).get('currency_code')}")
                print(f"  Brand: {item.get('brand', {}).get('title')}")
                print(f"  URL: {item.get('url')}")
                print(f"  Source: {item.get('_source', 'unknown')}")
                print(f"  Mock: {item.get('_mock', False)}")
                
                # Check if this is real data
                if not item.get('_mock') and item.get('_source') == 'vinted_api':
                    print("  ✅ REAL DATA from Vinted API")
                elif item.get('_mock'):
                    print("  ❌ MOCK DATA")
                else:
                    print("  ❓ UNKNOWN SOURCE")
        else:
            print("❌ No results returned")
            
    except Exception as e:
        print(f"❌ Error during search: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

if __name__ == "__main__":
    test_scraper()