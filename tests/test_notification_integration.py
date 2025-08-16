"""Integration tests for the notification system."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.bot.services.notification_service import NotificationService
from src.tasks.notification_handlers import (
    process_new_item_notifications,
    send_subscription_expiry_notifications
)
from src.db.models import User, SavedSearch, Item
from src.tasks.queue import TaskQueue


class TestNotificationIntegration:
    """Integration tests for the complete notification system."""
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.bot.services.notification_service.Bot')
    async def test_end_to_end_notification_flow(self, mock_bot_class, mock_get_session):
        """Test complete end-to-end notification flow."""
        # Setup test data
        now = datetime.utcnow()
        
        # Create test user with active trial
        test_user = User(
            id=1,
            tg_id=123456789,
            username="testuser",
            first_name="TestUser",
            joined_at=now - timedelta(days=2),
            trial_expires=now + timedelta(days=5),
            subscription_expires=None,
            referrals_count=0
        )
        
        # Create saved search
        saved_search = SavedSearch(
            id=1,
            user_id=test_user.id,
            query="nike shoes",
            filters={"brand": "Nike", "min_price": 30, "max_price": 100},
            notifications_enabled=True
        )
        saved_search.user = test_user
        test_user.saved_searches = [saved_search]
        
        # Create matching items
        matching_items = [
            Item(
                id=1,
                title="Nike Air Max 90",
                price=Decimal("75.00"),
                currency="EUR",
                brand="Nike",
                size="42",
                condition="Good",
                description="Great Nike shoes in excellent condition",
                seller_id=999,
                url="https://vinted.at/items/1",
                preview_img="https://example.com/img1.jpg",
                ships_to_at=True,
                created_at=now,
                updated_at=now
            ),
            Item(
                id=2,
                title="Nike Running Shoes",
                price=Decimal("45.00"),
                currency="EUR",
                brand="Nike",
                size="41",
                condition="Very Good",
                description="Perfect for running and daily wear",
                seller_id=888,
                url="https://vinted.at/items/2",
                preview_img="https://example.com/img2.jpg",
                ships_to_at=True,
                created_at=now,
                updated_at=now
            )
        ]
        
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock database queries
        # First query: get items by IDs
        mock_items_result = AsyncMock()
        mock_items_result.scalars.return_value.all.return_value = matching_items
        
        # Second query: get users with saved searches
        mock_users_result = AsyncMock()
        mock_users_result.scalars.return_value.all.return_value = [test_user]
        
        # Configure session.execute to return different results based on call order
        mock_session.execute.side_effect = [mock_items_result, mock_users_result]
        
        # Execute the notification flow
        result = await process_new_item_notifications([1, 2])
        
        # Verify results
        assert result["processed"] == 2
        assert result["notifications_sent"] == 1
        assert result["failed"] == 0
        assert result["blocked"] == 0
        
        # Verify bot was called to send message
        mock_bot.send_message.assert_called_once()
        
        # Verify message content
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["chat_id"] == 123456789
        assert "TestUser!" in call_args[1]["text"]
        assert "nike shoes" in call_args[1]["text"]
        assert "Nike Air Max 90" in call_args[1]["text"]
        assert "Nike Running Shoes" in call_args[1]["text"]
        assert "75.00 EUR" in call_args[1]["text"]
        assert "45.00 EUR" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "HTML"
        assert call_args[1]["disable_web_page_preview"] is True
        
        # Verify bot session was closed
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.bot.services.notification_service.Bot')
    async def test_notification_with_expired_user(self, mock_bot_class, mock_get_session):
        """Test that expired users don't receive notifications."""
        # Setup test data with expired user
        now = datetime.utcnow()
        
        expired_user = User(
            id=1,
            tg_id=123456789,
            username="expireduser",
            first_name="ExpiredUser",
            joined_at=now - timedelta(days=10),
            trial_expires=now - timedelta(days=2),  # Expired trial
            subscription_expires=None,
            referrals_count=0
        )
        
        saved_search = SavedSearch(
            id=1,
            user_id=expired_user.id,
            query="nike shoes",
            filters={},
            notifications_enabled=True
        )
        saved_search.user = expired_user
        expired_user.saved_searches = [saved_search]
        
        # Create matching item
        matching_item = Item(
            id=1,
            title="Nike Air Max 90",
            price=Decimal("75.00"),
            currency="EUR",
            brand="Nike",
            url="https://vinted.at/items/1",
            ships_to_at=True
        )
        
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock database queries
        mock_items_result = AsyncMock()
        mock_items_result.scalars.return_value.all.return_value = [matching_item]
        
        # No active users should be returned due to expired trial
        mock_users_result = AsyncMock()
        mock_users_result.scalars.return_value.all.return_value = []
        
        mock_session.execute.side_effect = [mock_items_result, mock_users_result]
        
        # Execute the notification flow
        result = await process_new_item_notifications([1])
        
        # Verify no notifications were sent
        assert result["processed"] == 1
        assert result["notifications_sent"] == 0
        
        # Verify bot was not called to send message
        mock_bot.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.bot.services.notification_service.Bot')
    async def test_notification_with_disabled_notifications(self, mock_bot_class, mock_get_session):
        """Test that users with disabled notifications don't receive alerts."""
        # Setup test data
        now = datetime.utcnow()
        
        test_user = User(
            id=1,
            tg_id=123456789,
            username="testuser",
            first_name="TestUser",
            joined_at=now - timedelta(days=2),
            trial_expires=now + timedelta(days=5),
            subscription_expires=None,
            referrals_count=0
        )
        
        # Create saved search with notifications disabled
        saved_search = SavedSearch(
            id=1,
            user_id=test_user.id,
            query="nike shoes",
            filters={},
            notifications_enabled=False  # Disabled
        )
        saved_search.user = test_user
        test_user.saved_searches = [saved_search]
        
        # Create matching item
        matching_item = Item(
            id=1,
            title="Nike Air Max 90",
            price=Decimal("75.00"),
            currency="EUR",
            brand="Nike",
            url="https://vinted.at/items/1",
            ships_to_at=True
        )
        
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock database queries
        mock_items_result = AsyncMock()
        mock_items_result.scalars.return_value.all.return_value = [matching_item]
        
        mock_users_result = AsyncMock()
        mock_users_result.scalars.return_value.all.return_value = [test_user]
        
        mock_session.execute.side_effect = [mock_items_result, mock_users_result]
        
        # Execute the notification flow
        result = await process_new_item_notifications([1])
        
        # Verify no notifications were sent (user found but notifications disabled)
        assert result["processed"] == 1
        assert result["notifications_sent"] == 0
        
        # Verify bot was not called to send message
        mock_bot.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.bot.services.notification_service.Bot')
    async def test_subscription_expiry_notification_flow(self, mock_bot_class, mock_get_session):
        """Test complete subscription expiry notification flow."""
        # Setup test data
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        
        # Trial user expiring tomorrow
        trial_user = User(
            id=1,
            tg_id=123456789,
            username="trialuser",
            first_name="TrialUser",
            joined_at=now - timedelta(days=6),
            trial_expires=tomorrow,
            subscription_expires=None,
            referrals_count=0
        )
        
        # Premium user expiring tomorrow
        premium_user = User(
            id=2,
            tg_id=987654321,
            username="premiumuser",
            first_name="PremiumUser",
            joined_at=now - timedelta(days=30),
            trial_expires=now - timedelta(days=23),  # Trial already expired
            subscription_expires=tomorrow,
            referrals_count=2
        )
        
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock database query to return expiring users
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [trial_user, premium_user]
        mock_session.execute.return_value = mock_result
        
        # Execute the expiry notification flow
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await send_subscription_expiry_notifications()
        
        # Verify results
        assert result["notifications_sent"] == 2
        assert result["failed"] == 0
        assert result["blocked"] == 0
        
        # Verify bot was called twice
        assert mock_bot.send_message.call_count == 2
        
        # Verify message content for trial user
        trial_call = mock_bot.send_message.call_args_list[0]
        assert trial_call[1]["chat_id"] == 123456789
        assert "TrialUser!" in trial_call[1]["text"]
        assert "trial period expires tomorrow" in trial_call[1]["text"]
        assert "/pay to upgrade" in trial_call[1]["text"]
        
        # Verify message content for premium user
        premium_call = mock_bot.send_message.call_args_list[1]
        assert premium_call[1]["chat_id"] == 987654321
        assert "PremiumUser!" in premium_call[1]["text"]
        assert "premium subscription expires tomorrow" in premium_call[1]["text"]
        assert "/pay to upgrade" in premium_call[1]["text"]
        
        # Verify bot session was closed
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.bot.services.notification_service.Bot')
    async def test_multiple_saved_searches_batching(self, mock_bot_class, mock_get_session):
        """Test that multiple saved searches are properly batched in notifications."""
        # Setup test data
        now = datetime.utcnow()
        
        test_user = User(
            id=1,
            tg_id=123456789,
            username="testuser",
            first_name="TestUser",
            joined_at=now - timedelta(days=2),
            trial_expires=now + timedelta(days=5),
            subscription_expires=None,
            referrals_count=0
        )
        
        # Create multiple saved searches
        saved_search1 = SavedSearch(
            id=1,
            user_id=test_user.id,
            query="nike shoes",
            filters={"brand": "Nike"},
            notifications_enabled=True
        )
        
        saved_search2 = SavedSearch(
            id=2,
            user_id=test_user.id,
            query="adidas sneakers",
            filters={"brand": "Adidas"},
            notifications_enabled=True
        )
        
        saved_search1.user = test_user
        saved_search2.user = test_user
        test_user.saved_searches = [saved_search1, saved_search2]
        
        # Create items matching different searches
        items = [
            Item(
                id=1,
                title="Nike Air Max 90",
                price=Decimal("75.00"),
                currency="EUR",
                brand="Nike",
                description="Nike shoes",
                url="https://vinted.at/items/1",
                ships_to_at=True
            ),
            Item(
                id=2,
                title="Adidas Ultraboost",
                price=Decimal("85.00"),
                currency="EUR",
                brand="Adidas",
                description="Adidas sneakers",
                url="https://vinted.at/items/2",
                ships_to_at=True
            )
        ]
        
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock database queries
        mock_items_result = AsyncMock()
        mock_items_result.scalars.return_value.all.return_value = items
        
        mock_users_result = AsyncMock()
        mock_users_result.scalars.return_value.all.return_value = [test_user]
        
        mock_session.execute.side_effect = [mock_items_result, mock_users_result]
        
        # Execute the notification flow
        result = await process_new_item_notifications([1, 2])
        
        # Verify results
        assert result["processed"] == 2
        assert result["notifications_sent"] == 1
        
        # Verify single batched message was sent
        mock_bot.send_message.assert_called_once()
        
        # Verify message contains both items and mentions multiple searches
        call_args = mock_bot.send_message.call_args
        message_text = call_args[1]["text"]
        
        assert "TestUser!" in message_text
        assert "Nike Air Max 90" in message_text
        assert "Adidas Ultraboost" in message_text
        assert "75.00 EUR" in message_text
        assert "85.00 EUR" in message_text
        # Should mention "saved searches" (plural) since multiple searches matched
        assert "saved searches" in message_text
    
    def test_task_queue_registration(self):
        """Test that notification handlers are properly registered with task queue."""
        from src.tasks.notification_handlers import register_notification_handlers
        
        # Create a real task queue instance
        queue = TaskQueue()
        
        # Register handlers
        register_notification_handlers(queue)
        
        # Verify handlers are registered
        expected_handlers = [
            "process_new_item_notifications",
            "send_subscription_expiry_notifications",
            "batch_notification_processor"
        ]
        
        for handler_name in expected_handlers:
            assert handler_name in queue._handlers
            assert callable(queue._handlers[handler_name])
    
    @pytest.mark.asyncio
    async def test_notification_service_rate_limiting(self):
        """Test that notification service respects rate limiting."""
        from src.bot.services.notification_service import UserNotification, NotificationItem
        
        # Create mock bot
        mock_bot = AsyncMock()
        
        # Create notification service
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
        
        # Mock asyncio.sleep to track rate limiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await service.send_batch_notifications(notifications)
        
        # Verify all notifications were sent
        assert result["sent"] == 3
        assert result["failed"] == 0
        assert result["blocked"] == 0
        
        # Verify rate limiting sleep was called between notifications
        assert mock_sleep.call_count == 3
        mock_sleep.assert_called_with(0.1)  # 100ms delay
        
        # Verify all bot calls were made
        assert mock_bot.send_message.call_count == 3