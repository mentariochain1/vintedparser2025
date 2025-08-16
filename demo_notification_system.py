#!/usr/bin/env python3
"""
Demo script for the notification system.

This script demonstrates the key functionality of the notification system
without requiring a full database setup.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

# Mock the database models for demo purposes
class MockUser:
    def __init__(self, id, tg_id, first_name, trial_expires, subscription_expires=None):
        self.id = id
        self.tg_id = tg_id
        self.first_name = first_name
        self.trial_expires = trial_expires
        self.subscription_expires = subscription_expires
        self.saved_searches = []

class MockSavedSearch:
    def __init__(self, id, user_id, query, filters=None, notifications_enabled=True):
        self.id = id
        self.user_id = user_id
        self.query = query
        self.filters = filters or {}
        self.notifications_enabled = notifications_enabled

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


async def demo_notification_matching():
    """Demonstrate item matching against saved searches."""
    print("🔍 Demo: Item Matching Against Saved Searches")
    print("=" * 50)
    
    # Import the notification service (with mocked dependencies)
    import sys
    sys.path.append('.')
    
    # Mock the bot
    mock_bot = AsyncMock()
    
    # Create notification service with mocked bot
    from src.bot.services.notification_service import NotificationService
    service = NotificationService(mock_bot)
    
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
    
    for item in matching_items:
        print(f"✅ {item.title} - {item.price} {item.brand}")
    
    print()
    print("Non-matching items:")
    non_matching = [item for item in items if item.id not in [m.item_id for m in matching_items]]
    for item in non_matching:
        print(f"❌ {item.title} - {item.price} {item.brand} (reason: ", end="")
        if item.brand != "Nike":
            print("wrong brand)")
        elif item.price > 100:
            print("price too high)")
        else:
            print("unknown)")


async def demo_user_notification_creation():
    """Demonstrate creating user notifications."""
    print("\n📧 Demo: User Notification Creation")
    print("=" * 50)
    
    # Mock the bot
    mock_bot = AsyncMock()
    
    from src.bot.services.notification_service import NotificationService, UserNotification, NotificationItem
    service = NotificationService(mock_bot)
    
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


async def demo_batch_notifications():
    """Demonstrate batch notification processing."""
    print("\n📬 Demo: Batch Notification Processing")
    print("=" * 50)
    
    # Mock the bot
    mock_bot = AsyncMock()
    
    from src.bot.services.notification_service import NotificationService, UserNotification, NotificationItem
    service = NotificationService(mock_bot)
    
    # Create multiple notifications
    notifications = []
    for i in range(3):
        notifications.append(
            UserNotification(
                user_id=i + 1,
                tg_id=123456789 + i,
                first_name=f"User{i + 1}",
                items=[
                    NotificationItem(
                        item_id=i + 1,
                        title=f"Test Item {i + 1}",
                        price="50.00 EUR",
                        brand="Test",
                        url=f"https://vinted.at/items/{i + 1}",
                        preview_img=None
                    )
                ],
                search_queries=[f"test query {i + 1}"]
            )
        )
    
    # Process batch (with mocked sleep for rate limiting)
    import asyncio
    original_sleep = asyncio.sleep
    sleep_calls = []
    
    async def mock_sleep(duration):
        sleep_calls.append(duration)
        # Don't actually sleep in demo
        pass
    
    asyncio.sleep = mock_sleep
    
    try:
        result = await service.send_batch_notifications(notifications)
        
        print(f"Batch Results:")
        print(f"  Sent: {result['sent']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Blocked: {result['blocked']}")
        print(f"  Rate limiting delays: {len(sleep_calls)} calls")
        print(f"  Delay duration: {sleep_calls[0] if sleep_calls else 'N/A'}s")
        
    finally:
        asyncio.sleep = original_sleep


async def demo_subscription_expiry():
    """Demonstrate subscription expiry notification."""
    print("\n⏰ Demo: Subscription Expiry Notification")
    print("=" * 50)
    
    # Mock the bot
    mock_bot = AsyncMock()
    
    from src.bot.services.notification_service import NotificationService
    service = NotificationService(mock_bot)
    
    # Create test users with expiring subscriptions
    tomorrow = datetime.utcnow() + timedelta(days=1)
    
    trial_user = MockUser(
        id=1,
        tg_id=123456789,
        first_name="TrialUser",
        trial_expires=tomorrow,
        subscription_expires=None
    )
    
    premium_user = MockUser(
        id=2,
        tg_id=987654321,
        first_name="PremiumUser",
        trial_expires=datetime.utcnow() - timedelta(days=10),
        subscription_expires=tomorrow
    )
    
    # Send expiry notifications
    await service._send_expiry_notification(trial_user)
    await service._send_expiry_notification(premium_user)
    
    print("Expiry notifications sent to:")
    print(f"1. Trial User (ID: {trial_user.tg_id})")
    print(f"2. Premium User (ID: {premium_user.tg_id})")
    print()
    
    # Show messages that would be sent
    calls = mock_bot.send_message.call_args_list
    for i, call in enumerate(calls, 1):
        print(f"Message {i}:")
        print("-" * 20)
        print(call[1]["text"][:200] + "..." if len(call[1]["text"]) > 200 else call[1]["text"])
        print("-" * 20)
        print()


async def main():
    """Run all notification system demos."""
    print("🤖 Vinted Parser Bot - Notification System Demo")
    print("=" * 60)
    print()
    
    try:
        await demo_notification_matching()
        await demo_user_notification_creation()
        await demo_batch_notifications()
        await demo_subscription_expiry()
        
        print("\n✅ All demos completed successfully!")
        print("\nThe notification system includes:")
        print("• Smart item matching against saved searches")
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