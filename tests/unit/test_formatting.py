#!/usr/bin/env python3
"""Test the formatting of search results."""

import sys
import os
import asyncio
sys.path.append('src')

from bot.services.vinted_scraper.scraper import SimpleVintedScraper
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

async def format_vinted_item(item: dict, search_term: str = None) -> str:
    """Format Vinted item data for display (simplified version)."""
    try:
        # Extract data from vinted scraper structure
        title = item.get('title', 'Unknown Item')

        # Handle price structure from vinted scraper
        price_info = item.get('price', {})
        if isinstance(price_info, dict):
            price_raw = price_info.get('amount', 0.0)
            currency = price_info.get('currency_code', 'EUR')
            # Ensure price is a float
            try:
                price = float(price_raw) if price_raw is not None else 0.0
            except (ValueError, TypeError):
                price = 0.0
        else:
            price = 0.0
            currency = 'EUR'

        # Format price properly
        if currency == 'EUR' and price > 0:
            try:
                from bot.services.currency_service import format_price_with_rub
                price_display = await format_price_with_rub(price)
            except:
                price_display = f"{price:.2f} EUR"
        else:
            price_display = f"{price:.2f} {currency}"
        
        # Handle brand structure
        brand_info = item.get('brand', {})
        brand = brand_info.get('title', '') if isinstance(brand_info, dict) else ''
        
        # Handle size structure
        size_info = item.get('size', {})
        size = size_info.get('title', '') if isinstance(size_info, dict) else ''
        
        # Handle user/location structure
        user_info = item.get('user', {})
        location = user_info.get('city', '') if isinstance(user_info, dict) else ''
        
        # Get URL
        url = item.get('url', '')

        # Create formatted message
        message_parts = [f"🛍️ {title}"]
        if brand:
            message_parts.append(f"🏷️ Бренд: {brand}")
        if size:
            message_parts.append(f"📏 Размер: {size}")
        message_parts.append(f"💰 Цена: {price_display}")
        message_parts.append(f"📍 Местоположение: {location if location else 'Не указано'}")
        if search_term:
            message_parts.append(f"🔍 Найдено по запросу: {search_term}")
        if url:
            message_parts.append(f"🔗 Открыть на Vinted")

        return '\n'.join(message_parts)

    except Exception as e:
        print(f"Error formatting item: {e}")
        return f"🛍️ Товар\n❌ Ошибка при форматировании данных"

async def test_formatting():
    """Test the formatting of search results."""
    print("Testing search result formatting...")
    
    scraper = SimpleVintedScraper(base_url="https://www.vinted.at")
    
    try:
        # Get some real results
        results = scraper.search("nike", per_page=2)
        
        if results:
            print(f"\nFound {len(results)} items. Testing formatting...")
            
            for i, item in enumerate(results, 1):
                print(f"\n{'='*50}")
                print(f"Item {i} - Raw Data:")
                print(f"  ID: {item.get('id')}")
                print(f"  Title: {item.get('title')}")
                print(f"  Price: {item.get('price')}")
                print(f"  Brand: {item.get('brand')}")
                print(f"  URL: {item.get('url')}")
                
                # Test formatting
                formatted = await format_vinted_item(item, "nike")
                print(f"\nFormatted Output:")
                print(formatted)
                print('='*50)
        else:
            print("❌ No results to test formatting")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

if __name__ == "__main__":
    asyncio.run(test_formatting())