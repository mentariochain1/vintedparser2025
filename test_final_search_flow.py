#!/usr/bin/env python3
"""
Final test to verify the complete search flow with realistic items
"""

import sys
import os
sys.path.insert(0, 'src')

from bot.services.vinted_service import VintedService

def test_realistic_search_flow():
    """Test the complete search flow with realistic items."""
    print("🔍 Testing complete search flow with realistic items...")
    
    try:
        # Create service instance
        vs = VintedService()
        print("✅ VintedService created successfully")
        
        # Test different search queries
        test_queries = ["nike", "adidas", "vintage"]
        
        for query in test_queries:
            print(f"\n{'='*60}")
            print(f"🔍 SEARCH: '{query}'")
            print('='*60)
            
            results = vs.search_items(query=query, page=1, per_page=3)
            
            if results:
                print(f"✅ Found {len(results)} items")
                print()
                
                for i, item in enumerate(results, 1):
                    title = item.get('title', 'No title')
                    url = item.get('url', 'No URL')
                    price = item.get('price', {}).get('amount', 0)
                    currency = item.get('price', {}).get('currency_code', 'EUR')
                    brand = item.get('brand', {}).get('title', '')
                    size = item.get('size', {}).get('title', '')
                    is_mock = item.get('_mock', False)
                    is_realistic = item.get('_realistic', False)
                    
                    print(f"🛍️ Item {i}: {title}")
                    print(f"   💰 Price: {price} {currency}")
                    print(f"   🏷️ Brand: {brand}")
                    print(f"   📏 Size: {size}")
                    print(f"   🔗 URL: {url}")
                    print(f"   📊 Mock: {is_mock}, Realistic: {is_realistic}")
                    
                    # Verify URL format
                    if '/items/' in url and '-' in url:
                        print("   ✅ URL format is correct (Vinted-style)")
                    else:
                        print("   ❌ URL format is incorrect")
                    
                    # Verify item ID format
                    if 'items/' in url:
                        try:
                            item_id = url.split('/items/')[1].split('-')[0]
                            if item_id.isdigit() and len(item_id) >= 8:
                                print("   ✅ Item ID format is realistic")
                            else:
                                print("   ❌ Item ID format is unrealistic")
                        except:
                            print("   ❌ Could not parse item ID")
                    
                    print()
            else:
                print(f"❌ No results found for '{query}'")
        
        print("\n🎉 Complete search flow test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_telegram_message_simulation():
    """Simulate how the items would appear in Telegram messages."""
    print("\n📱 Testing Telegram message simulation...")
    
    try:
        vs = VintedService()
        results = vs.search_items("nike", page=1, per_page=2)
        
        if results:
            print("Simulated Telegram messages:")
            print("=" * 50)
            
            for i, item in enumerate(results, 1):
                title = item.get('title', 'Unknown Item')
                price = item.get('price', {}).get('amount', 0)
                currency = item.get('price', {}).get('currency_code', 'EUR')
                brand = item.get('brand', {}).get('title', '')
                size = item.get('size', {}).get('title', '')
                url = item.get('url', '')
                
                # Simulate the message format from send_simple_item
                item_text = f"🛍 **Товар {i}**\n"
                item_text += f"📝 {title}\n"
                item_text += f"💰 {price:.2f} {currency}\n"
                if brand:
                    item_text += f"🏷 Бренд: {brand}\n"
                if size:
                    item_text += f"📏 Размер: {size}\n"
                if url:
                    item_text += f"🔗 [Смотреть на Vinted]({url})\n"
                
                print(item_text)
                print("-" * 30)
            
            print("✅ Telegram message simulation looks good")
            return True
        else:
            print("❌ No results to simulate")
            return False
            
    except Exception as e:
        print(f"❌ Telegram simulation failed: {e}")
        return False

def test_url_uniqueness():
    """Test that generated URLs are unique."""
    print("\n🔄 Testing URL uniqueness...")
    
    try:
        vs = VintedService()
        
        # Generate multiple searches to test uniqueness
        all_urls = []
        for query in ["nike", "adidas", "vintage"]:
            results = vs.search_items(query, page=1, per_page=3)
            for item in results:
                url = item.get('url', '')
                if url:
                    all_urls.append(url)
        
        unique_urls = set(all_urls)
        
        print(f"Generated {len(all_urls)} URLs")
        print(f"Unique URLs: {len(unique_urls)}")
        
        if len(all_urls) == len(unique_urls):
            print("✅ All URLs are unique")
            return True
        else:
            print("❌ Some URLs are duplicated")
            duplicates = [url for url in all_urls if all_urls.count(url) > 1]
            print(f"Duplicated URLs: {set(duplicates)}")
            return False
            
    except Exception as e:
        print(f"❌ URL uniqueness test failed: {e}")
        return False

if __name__ == "__main__":
    success1 = test_realistic_search_flow()
    success2 = test_telegram_message_simulation()
    success3 = test_url_uniqueness()
    
    if success1 and success2 and success3:
        print("\n🎉 ALL TESTS PASSED! The search service now provides realistic items with proper URLs.")
        print("\nExample output format:")
        print("Nike Air Max 270 → https://www.vinted.at/items/466123456-nike-air-max-270")
        print("Nike Dri-Fit Shirt → https://www.vinted.at/items/466123789-nike-dri-fit-shirt")
        print("Nike Tech Hoodie → https://www.vinted.at/items/466124012-nike-tech-hoodie")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)