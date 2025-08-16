#!/usr/bin/env python3
"""
Simple demo script for the notification system functionality.

This script demonstrates the core notification logic without full imports.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NotificationItem:
    """Data class for notification item details."""
    item_id: int
    title: str
    price: str
    brand: Optional[str]
    url: str
    preview_img: Optional[str]


@dataclass
class UserNotification:
    """Data class for user notification with matched items."""
    user_id: int
    tg_id: int
    first_name: Optional[str]
    items: List[NotificationItem]
    search_queries: List[str]


# Mock classes for demo
class MockItem:
    def __init__(self, id, title, price, currency, brand, description, url, preview_img=None):
        self.id = id
        self.title = title
        self.price = Decimal(str(price))
        self.currency = currency
        self.brand = brand
        self.description = description
        self.url = url
        self.preview_img = preview_img


class MockSavedSearch:
    def __init__(self, id, user_id, query, filters=None, notifications_enabled=True):
        self.id = id
        self.user_id = user_id
        self.query = query
        self.filters = filters or {}
        self.notifications_enabled = notifications_enabled


class SimpleNotificationService:
    """Simplified notification service for demo purposes."""
    
    def __init__(self, bot):
        self.bot = bot
        self.max_items_per_notification = 5
    
    def _item_matches_query(self, item, query_words, filters):
        """Check if an item matches search query and filters."""
        # Create searchable text from item
        searchable_text = " ".join(filter(None, [
            item.title.lower() if item.title else "",
            item.brand.lower() if item.brand else "",
            item.description.lower() if item.description else ""
        ]))
        
        # Check if all query words are present
        for word in query_words:
            if word not in searchable_text:
                return False
        
        # Apply filters if present
        if filters:
            # Brand filter
            if "brand" in filters and filters["brand"]:
                if not item.brand or item.brand.lower() != filters["brand"].lower():
                    return False
            
            # Price range filter
            if "min_price" in filters and filters["min_price"]:
                if item.price < filters["min_price"]:
                    return False
                    
            if "max_price" in filters and filters["max_price"]:
                if item.price > filters["max_price"]:
                    return False
        
        return True
    
    def _match_items_to_search(self, items, saved_search):
        """Match items against a saved search query."""
        matching_items = []
        query_lower = saved_search.query.lower()
        query_words = query_lower.split()
        
        for item in items:
            # Check if item matches the search query
            if self._item_matches_query(item, query_words, saved_search.filters):
                notification_item = NotificationItem(
                    item_id=item.id,
                    title=item.title,
                    price=f"{item.price} {item.currency}",
                    brand=item.brand,
                    url=item.url,
                    preview_img=item.preview_img
                )
                matching_items.append(notification_item)
        
        return matching_items
    
    async def _send_user_notification(self, notification):
        """Send notification to a single user."""
        # Build notification message
        greeting = f"👋 {notification.first_name or 'Hello'}!"
        
        if len(notification.search_queries) == 1:
            header = f"🔍 New items found for your search: <b>{notification.search_queries[0]}</b>"
        else:
            header = f"🔍 New items found for your saved searches"
        
        items_text = []
        for i, item in enumerate(notification.items, 1):
            brand_text = f" by {item.brand}" if item.brand else ""
            item_text = f"{i}. <b>{item.title}</b>{brand_text}\n💰 {item.price}\n🔗 <a href='{item.url}'>View on Vinted</a>"
            items_text.append(item_text)
        
        message = f"{greeting}\n\n{header}\n\n" + "\n\n".join(items_text)
        
        if len(notification.items) == self.max_items_per_notification:
            message += f"\n\n<i>Showing first {self.max_items_per_notification} items. Check your searches for more!</i>"
        
        await self.bot.send_message(
            chat_id=notification.tg_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


async def demo_notification_matching():
    """Demonstrate item matching against saved searches."""
    print("🔍 Demo: Item Matching Against Saved Searches")
    print("=" * 50)
    
    # Mock the bot
    mock_bot = AsyncMock()
    
    # Create notification service
    service = SimpleNotificationService(mock_bot)
    
    # Create test data
    saved_search = MockSavedSearch(
        id=1,
        user_id=1,
        query="nike shoes",
        filters={"brand": "Nike", "min_price": 30, "max_price": 100}
    )
    
    items = [
        MockItem(1, "Nike Air Max 90", 75.00, "EUR", "Nike", "Great Nike shoes", "https://vinted.at/items/1"),
        MockItem(2, "Adidas Sneakers", 50.00, "EUR", "Adidas", "Comfortable sneakers", "https://vinted.at/items/2"),
        MockItem(3, "Nike Running Shoes", 45.00, "EUR", "Nike", "Perfect for running", "https://vinted.at/items/3"),
        MockItem(4, "Nike Expensive Shoes", 150.00, "EUR", "Nike", "Luxury Nike shoes", "https://vinted.at/items/4"),
    ]
    
    # Test matching
    matching_items = service._match_items_to_search(items, saved_search)
    
    print(f"Search Query: '{saved_search.query}'")
    print(f"Filters: {saved_search.filters}")
    print(f"Total Items: {len(items)}")
    print(f"Matching Items: {len(matching_items)}")
    print()
    
    print("Matching items:")
    for item in matching_items:
        print(f"✅ {item.title} - {item.price} - {item.brand}")
    
    print()
    print("Non-matching items:")
    non_matching = [item for item in items if item.id not in [m.item_id for m in matching_items]]
    for item in non_matching:
        reason = ""
        if item.brand != "Nike":
            reason = "wrong brand"
        elif item.price > 100:
            reason = "price too high"
        else:
            reason = "unknown"
        print(f"❌ {item.title} - {item.price} {item.currency} - {item.brand} (reason: {reason})")


async def demo_user_notification_creation():
    """Demonstrate creating user notifications."""
    print("\n📧 Demo: User Notification Creation")
    print("=" * 50)
    
    # Mock the bot
    mock_bot = AsyncMock()
    
    service = SimpleNotificationService(mock_bot)
    
    # Create test notification
    notification = UserNotification(
        user_id=1,
        tg_id=123456789,
        first_name="TestUser",
        items=[
            NotificationItem(
                item_id=1,
                title="Nike Air Max 90",
                price="75.00 EUR",
                brand="Nike",
                url="https://vinted.at/items/1",
                preview_img="https://example.com/img1.jpg"
            ),
            NotificationItem(
                item_id=2,
                title="Nike Running Shoes",
                price="45.00 EUR",
                brand="Nike",
                url="https://vinted.at/items/2",
                preview_img="https://example.com/img2.jpg"
            )
        ],
        search_queries=["nike shoes"]
    )
    
    # Send notification (mocked)
    await service._send_user_notification(notification)
    
    # Display what would be sent
    print("Notification would be sent to:")
    print(f"User ID: {notification.tg_id}")
    print(f"First Name: {notification.first_name}")
    print(f"Items Count: {len(notification.items)}")
    print(f"Search Queries: {notification.search_queries}")
    print()
    
    # Show the message that would be sent
    call_args = mock_bot.send_message.call_args
    if call_args:
        print("Message content:")
        print("-" * 30)
        print(call_args[1]["text"])
        print("-" * 30)


async def demo_filter_logic():
    """Demonstrate advanced filtering logic."""
    print("\n🔧 Demo: Advanced Filtering Logic")
    print("=" * 50)
    
    service = SimpleNotificationService(AsyncMock())
    
    # Test different filter scenarios
    test_cases = [
        {
            "name": "Brand filter only",
            "search": MockSavedSearch(1, 1, "shoes", {"brand": "Nike"}),
            "items": [
                MockItem(1, "Nike Air Max", 50, "EUR", "Nike", "Nike shoes", "url1"),
                MockItem(2, "Adidas Boost", 60, "EUR", "Adidas", "Adidas shoes", "url2"),
            ]
        },
        {
            "name": "Price range filter",
            "search": MockSavedSearch(1, 1, "shoes", {"min_price": 40, "max_price": 80}),
            "items": [
                MockItem(1, "Cheap Shoes", 30, "EUR", "Brand", "Cheap shoes", "url1"),
                MockItem(2, "Mid Shoes", 60, "EUR", "Brand", "Mid range shoes", "url2"),
                MockItem(3, "Expensive Shoes", 100, "EUR", "Brand", "Expensive shoes", "url3"),
            ]
        },
        {
            "name": "Combined filters",
            "search": MockSavedSearch(1, 1, "running", {"brand": "Nike", "min_price": 50, "max_price": 100}),
            "items": [
                MockItem(1, "Nike Running Low", 40, "EUR", "Nike", "Nike running shoes", "url1"),
                MockItem(2, "Nike Running Mid", 70, "EUR", "Nike", "Nike running shoes", "url2"),
                MockItem(3, "Nike Running High", 120, "EUR", "Nike", "Nike running shoes", "url3"),
                MockItem(4, "Adidas Running", 70, "EUR", "Adidas", "Adidas running shoes", "url4"),
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Query: '{test_case['search'].query}'")
        print(f"Filters: {test_case['search'].filters}")
        
        matching = service._match_items_to_search(test_case['items'], test_case['search'])
        
        print(f"Results: {len(matching)}/{len(test_case['items'])} items matched")
        for item in matching:
            print(f"  ✅ {item.title} - {item.price}")
        
        non_matching = [item for item in test_case['items'] if item.id not in [m.item_id for m in matching]]
        for item in non_matching:
            print(f"  ❌ {item.title} - {item.price} {item.currency}")


async def main():
    """Run all notification system demos."""
    print("🤖 Vinted Parser Bot - Notification System Demo")
    print("=" * 60)
    print()
    
    try:
        await demo_notification_matching()
        await demo_user_notification_creation()
        await demo_filter_logic()
        
        print("\n✅ All demos completed successfully!")
        print("\nThe notification system includes:")
        print("• Smart item matching against saved searches")
        print("• Advanced filtering (brand, price range, etc.)")
        print("• Batch notification processing with rate limiting")
        print("• Subscription expiry notifications")
        print("• Comprehensive error handling")
        print("• Full test coverage")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())