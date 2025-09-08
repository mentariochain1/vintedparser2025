#!/usr/bin/env python3
"""Test production configuration for SSL handling."""

import sys
import os
sys.path.append('src')

def test_config():
    """Test the configuration settings."""
    print("Testing configuration...")
    
    try:
        from config import settings
        
        print(f"Environment: {settings.environment}")
        print(f"Is Production: {settings.is_production}")
        print(f"Disable SSL Verification: {settings.disable_ssl_verification}")
        print(f"Debug Mode: {settings.debug}")
        
        # Test SSL decision logic
        use_ssl = not (settings.disable_ssl_verification or settings.is_production)
        print(f"Will use SSL verification: {use_ssl}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_scraper_with_config():
    """Test scraper with configuration."""
    print("\nTesting scraper with configuration...")
    
    try:
        from config import settings
        from bot.services.vinted_scraper.scraper import SimpleVintedScraper
        
        # Use the same logic as the search module
        use_ssl = not (settings.disable_ssl_verification or settings.is_production)
        
        print(f"Creating scraper with SSL verification: {use_ssl}")
        scraper = SimpleVintedScraper(base_url="https://www.vinted.at", verify_ssl=use_ssl)
        
        # Test a simple search
        results = scraper.search("test", per_page=1)
        
        if results:
            print(f"✅ SUCCESS: Found {len(results)} items")
        else:
            print("✅ SUCCESS: Search completed (no results)")
        
        scraper.close()
        return True
        
    except Exception as e:
        print(f"❌ Scraper test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    config_ok = test_config()
    if config_ok:
        test_scraper_with_config()
    else:
        print("❌ Configuration test failed, skipping scraper test")