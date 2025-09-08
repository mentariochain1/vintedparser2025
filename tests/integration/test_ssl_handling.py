#!/usr/bin/env python3
"""Test SSL handling in production-like environment."""

import sys
import os
sys.path.append('src')

from bot.services.vinted_scraper.scraper import SimpleVintedScraper
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

def test_ssl_handling():
    """Test SSL handling with different configurations."""
    print("Testing SSL handling...")
    
    # Test 1: Start with SSL disabled (production mode)
    print("\n1. Testing with SSL disabled from start...")
    try:
        scraper = SimpleVintedScraper(base_url="https://www.vinted.at", verify_ssl=False)
        results = scraper.search("nike", per_page=2)
        
        if results:
            print(f"✅ SUCCESS: Found {len(results)} items with SSL disabled")
            for item in results[:1]:  # Show first item
                print(f"  - {item.get('title')} - {item.get('price', {}).get('amount')} EUR")
        else:
            print("❌ No results with SSL disabled")
        
        scraper.close()
        
    except Exception as e:
        print(f"❌ Error with SSL disabled: {e}")
    
    # Test 2: Start with SSL enabled, let it fallback
    print("\n2. Testing with SSL enabled (should fallback)...")
    try:
        scraper = SimpleVintedScraper(base_url="https://www.vinted.at", verify_ssl=True)
        results = scraper.search("adidas", per_page=2)
        
        if results:
            print(f"✅ SUCCESS: Found {len(results)} items (with SSL fallback)")
            for item in results[:1]:  # Show first item
                print(f"  - {item.get('title')} - {item.get('price', {}).get('amount')} EUR")
        else:
            print("❌ No results with SSL fallback")
        
        scraper.close()
        
    except Exception as e:
        print(f"❌ Error with SSL fallback: {e}")

if __name__ == "__main__":
    test_ssl_handling()