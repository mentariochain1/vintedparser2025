"""Tests for notification task handlers."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.tasks.notification_handlers import (
    process_new_item_notifications,
    send_subscription_expiry_notifications,
    batch_notification_processor,
    register_notification_handlers
)
from src.db.models import User, SavedSearch, Item
from src.tasks.queue import TaskQueue


class TestNotificationHandlers:
    """Test cases for notification task handlers."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def sample_items(self):
        """Sample items for testing."""
        return [
            Item(
                id=1,
                title="Nike Air Max 90",
                price=Decimal("75.00"),
                currency="EUR",
                brand="Nike",
                size="42",
                condition="Good",
                description="Great Nike shoes",
                seller_id=999,
                url="https://vinted.at/items/1",
                preview_img="https://example.com/img1.jpg",
                ships_to_at=True
            ),
            Item(
                id=2,
                title="Adidas Sneakers",
                price=Decimal("50.00"),
                currency="EUR",
                brand="Adidas",
                size="41",
                condition="Very Good",
                description="Comfortable sneakers",
                seller_id=888,
                url="https://vinted.at/items/2",
                preview_img="https://example.com/img2.jpg",
                ships_to_at=True
            )
        ]
    
    @pytest.mark.asyncio
    async def test_process_new_item_notifications_empty_list(self):
        """Test processing notifications with empty item list."""
        result = await process_new_item_notifications([])
        
        assert result["processed"] == 0
        assert result["notifications_sent"] == 0
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_process_new_item_notifications_success(
        self, mock_notification_service_class, mock_bot_class, mock_get_session, sample_items
    ):
        """Test successful processing of new item notifications."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_notification_service = AsyncMock()
        mock_notification_service_class.return_value = mock_notification_service
        
        # Mock database query result
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # Mock notification service methods
        mock_user_notifications = [
            MagicMock(user_id=1, tg_id=123456789, items=[MagicMock()])
        ]
        mock_notification_service.find_matching_users.return_value = mock_user_notifications
        mock_notification_service.send_batch_notifications.return_value = {
            "sent": 1,
            "failed": 0,
            "blocked": 0
        }
        
        # Test
        result = await process_new_item_notifications([1, 2])
        
        # Assertions
        assert result["processed"] == 2
        assert result["notifications_sent"] == 1
        assert result["failed"] == 0
        assert result["blocked"] == 0
        
        # Verify method calls
        mock_notification_service.find_matching_users.assert_called_once()
        mock_notification_service.send_batch_notifications.assert_called_once()
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_process_new_item_notifications_no_items_found(
        self, mock_notification_service_class, mock_bot_class, mock_get_session
    ):
        """Test processing notifications when no items are found in database."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock empty database query result
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Test
        result = await process_new_item_notifications([1, 2])
        
        # Assertions
        assert result["processed"] == 0
        assert result["notifications_sent"] == 0
        
        # Bot session should still be closed
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_process_new_item_notifications_no_matching_users(
        self, mock_notification_service_class, mock_bot_class, mock_get_session, sample_items
    ):
        """Test processing notifications when no users have matching searches."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_notification_service = AsyncMock()
        mock_notification_service_class.return_value = mock_notification_service
        
        # Mock database query result
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # Mock no matching users
        mock_notification_service.find_matching_users.return_value = []
        
        # Test
        result = await process_new_item_notifications([1, 2])
        
        # Assertions
        assert result["processed"] == 2
        assert result["notifications_sent"] == 0
        
        # Verify find_matching_users was called but send_batch_notifications was not
        mock_notification_service.find_matching_users.assert_called_once()
        mock_notification_service.send_batch_notifications.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_process_new_item_notifications_error_handling(
        self, mock_notification_service_class, mock_bot_class, mock_get_session
    ):
        """Test error handling in process_new_item_notifications."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock database error
        mock_session.execute.side_effect = Exception("Database error")
        
        # Test
        with pytest.raises(Exception, match="Database error"):
            await process_new_item_notifications([1, 2])
        
        # Bot session should still be closed
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_send_subscription_expiry_notifications_success(
        self, mock_notification_service_class, mock_bot_class, mock_get_session
    ):
        """Test successful sending of subscription expiry notifications."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_notification_service = AsyncMock()
        mock_notification_service_class.return_value = mock_notification_service
        
        # Mock notification service response
        mock_notification_service.send_subscription_expiry_notifications.return_value = {
            "sent": 3,
            "failed": 1,
            "blocked": 0
        }
        
        # Test
        result = await send_subscription_expiry_notifications()
        
        # Assertions
        assert result["notifications_sent"] == 3
        assert result["failed"] == 1
        assert result["blocked"] == 0
        
        # Verify method calls
        mock_notification_service.send_subscription_expiry_notifications.assert_called_once_with(
            mock_session
        )
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_send_subscription_expiry_notifications_error(
        self, mock_notification_service_class, mock_bot_class, mock_get_session
    ):
        """Test error handling in send_subscription_expiry_notifications."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_notification_service = AsyncMock()
        mock_notification_service_class.return_value = mock_notification_service
        
        # Mock service error
        mock_notification_service.send_subscription_expiry_notifications.side_effect = Exception(
            "Service error"
        )
        
        # Test
        with pytest.raises(Exception, match="Service error"):
            await send_subscription_expiry_notifications()
        
        # Bot session should still be closed
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.process_new_item_notifications')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_batch_notification_processor_success(
        self, mock_sleep, mock_bot_class, mock_process_notifications
    ):
        """Test successful batch notification processing."""
        # Setup mocks
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock process_new_item_notifications responses
        mock_process_notifications.side_effect = [
            {
                "processed": 2,
                "notifications_sent": 1,
                "failed": 0,
                "blocked": 0
            },
            {
                "processed": 3,
                "notifications_sent": 2,
                "failed": 1,
                "blocked": 0
            }
        ]
        
        # Test data
        notification_batches = [
            {"item_ids": [1, 2]},
            {"item_ids": [3, 4, 5]}
        ]
        
        # Test
        result = await batch_notification_processor(notification_batches)
        
        # Assertions
        assert result["batches_processed"] == 2
        assert result["total_sent"] == 3
        assert result["total_failed"] == 1
        assert result["total_blocked"] == 0
        
        # Verify method calls
        assert mock_process_notifications.call_count == 2
        mock_process_notifications.assert_any_call([1, 2])
        mock_process_notifications.assert_any_call([3, 4, 5])
        
        # Verify rate limiting sleep was called
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.0)
        
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.process_new_item_notifications')
    @patch('src.tasks.notification_handlers.Bot')
    async def test_batch_notification_processor_empty_batches(
        self, mock_bot_class, mock_process_notifications
    ):
        """Test batch processor with empty batches."""
        # Setup mocks
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Test data with empty item_ids
        notification_batches = [
            {"item_ids": []},
            {"other_field": "value"}  # No item_ids field
        ]
        
        # Test
        result = await batch_notification_processor(notification_batches)
        
        # Assertions
        assert result["batches_processed"] == 2
        assert result["total_sent"] == 0
        assert result["total_failed"] == 0
        assert result["total_blocked"] == 0
        
        # process_new_item_notifications should not be called
        mock_process_notifications.assert_not_called()
        mock_bot.session.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.process_new_item_notifications')
    @patch('src.tasks.notification_handlers.Bot')
    async def test_batch_notification_processor_error_handling(
        self, mock_bot_class, mock_process_notifications
    ):
        """Test error handling in batch notification processor."""
        # Setup mocks
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        # Mock process_new_item_notifications to raise error
        mock_process_notifications.side_effect = Exception("Processing error")
        
        # Test data
        notification_batches = [{"item_ids": [1, 2]}]
        
        # Test
        with pytest.raises(Exception, match="Processing error"):
            await batch_notification_processor(notification_batches)
        
        # Bot session should still be closed
        mock_bot.session.close.assert_called_once()
    
    def test_register_notification_handlers(self):
        """Test registration of notification handlers."""
        mock_queue = MagicMock(spec=TaskQueue)
        
        register_notification_handlers(mock_queue)
        
        # Verify all handlers were registered
        expected_handlers = [
            "process_new_item_notifications",
            "send_subscription_expiry_notifications", 
            "batch_notification_processor"
        ]
        
        assert mock_queue.register_handler.call_count == len(expected_handlers)
        
        # Check that each expected handler was registered
        registered_names = [
            call[0][0] for call in mock_queue.register_handler.call_args_list
        ]
        
        for handler_name in expected_handlers:
            assert handler_name in registered_names
    
    @pytest.mark.asyncio
    @patch('src.tasks.notification_handlers.get_async_session')
    @patch('src.tasks.notification_handlers.Bot')
    @patch('src.tasks.notification_handlers.NotificationService')
    async def test_process_new_item_notifications_integration(
        self, mock_notification_service_class, mock_bot_class, mock_get_session, sample_items
    ):
        """Integration test for process_new_item_notifications with realistic data."""
        # Setup mocks with realistic data
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        
        mock_notification_service = AsyncMock()
        mock_notification_service_class.return_value = mock_notification_service
        
        # Mock database query result
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # Mock realistic notification service responses
        from src.bot.services.notification_service import UserNotification, NotificationItem
        
        mock_user_notifications = [
            UserNotification(
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
                    )
                ],
                search_queries=["nike shoes"]
            )
        ]
        
        mock_notification_service.find_matching_users.return_value = mock_user_notifications
        mock_notification_service.send_batch_notifications.return_value = {
            "sent": 1,
            "failed": 0,
            "blocked": 0
        }
        
        # Test
        result = await process_new_item_notifications([1, 2])
        
        # Detailed assertions
        assert result["processed"] == 2
        assert result["notifications_sent"] == 1
        assert result["failed"] == 0
        assert result["blocked"] == 0
        
        # Verify the notification service was called with correct items
        find_users_call = mock_notification_service.find_matching_users.call_args
        passed_items = find_users_call[0][1]  # Second argument (items)
        assert len(passed_items) == 2
        assert passed_items[0].id == 1
        assert passed_items[1].id == 2
        
        # Verify batch notifications were sent with correct data
        send_batch_call = mock_notification_service.send_batch_notifications.call_args
        passed_notifications = send_batch_call[0][0]  # First argument (notifications)
        assert len(passed_notifications) == 1
        assert passed_notifications[0].user_id == 1
        assert len(passed_notifications[0].items) == 1