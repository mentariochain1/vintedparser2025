#!/usr/bin/env python3
"""
Test script to verify SSL certificate fix for image scraping.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.bot.services.image.image_downloader import scrape_item_images
from src.monitoring import get_logger

logger = get_logger(__name__)

async def test_ssl_fix():
    """Test SSL certificate fix for image scraping."""

    # Test with the same URL from the logs
    test_url = "https://www.vinted.at/items/7031194588-sport-bh-nike"

    print("🔧 Testing SSL certificate fix...")
    print(f"📄 Target URL: {test_url}")

    try:
        # Try to scrape images - this should now handle SSL errors gracefully
        image_urls = await scrape_item_images(test_url)

        if not image_urls:
            print("❌ No images found via web scraping")
            return

        print(f"✅ SUCCESS! Found {len(image_urls)} image URLs:")

        for i, url in enumerate(image_urls[:5], 1):
            print(f"  {i}. {url}")

        if len(image_urls) > 5:
            print(f"  ... and {len(image_urls) - 5} more")

        print("\n🎯 SSL certificate issue should be resolved!")
        print("📱 Images can now be embedded directly in Telegram messages.")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ssl_fix())
