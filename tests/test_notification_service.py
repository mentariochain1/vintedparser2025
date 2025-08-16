"""Tests for notification service."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot.services.notification_service import (
    NotificationService,
    NotificationItem,
    UserNotification
)
from src.db.models import User, SavedSearch, Item


class TestNotificationService:
    """Test cases for NotificationService."""
    
    @pytest.fixture
    def mock_bot(self):
        """Mock bot instance."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        return bot
    
    @pytest.fixture
    def notification_service(self, mock_bot):
        """NotificationService instance with mocked bot."""
        return NotificationService(mock_bot)
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = User(
            id=1,
            tg_id=123456789,
            username="testuser",
            first_name="Test",
            joined_at=datetime.utcnow(),
            trial_expires=datetime.utcnow() + timedelta(days=5),
            referrals_count=0
        )
        return user
    
    @pytest.fixture
    def sample_saved_search(self, sample_user):
        """Sample saved search for testing."""
        search = SavedSearch(
            id=1,
            user_id=sample_user.id,
            query="nike shoes",
            filters={"brand": "Nike", "min_price": 20, "max_price": 100},
            notifications_enabled=True
        )
        search.user = sample_user
        return search
    
    @pytest.fixture
    def sample_items(self):
        """Sample items for testing."""
        items = [
            Item(
                id=1,
                title="Nike Air Max 90",
                price=Decimal("75.00"),
                currency="EUR",
                brand="Nike",
                size="42",
                condition="Good",
                description="Great Nike shoes in good condition",
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
                description="Comfortable Adidas sneakers",
                seller_id=888,
                url="https://vinted.at/items/2",
                preview_img="https://example.com/img2.jpg",
                ships_to_at=True
            ),
            Item(
                id=3,
                title="Nike Running Shoes",
                price=Decimal("45.00"),
                currency="EUR",
                brand="Nike",
                size="43",
                condition="Good",
                description="Perfect for running",
                seller_id=777,
                url="https://vinted.at/items/3",
                preview_img="https://example.com/img3.jpg",
                ships_to_at=True
            )
        ]
        return items
    
    def test_item_matches_query_basic_match(self, notification_service, sample_items):
        """Test basic query matching."""
        item = sample_items[0]  # Nike Air Max 90
        query_words = ["nike", "shoes"]
        
        result = notification_service._item_matches_query(item, query_words, None)
        assert result is True
    
    def test_item_matches_query_no_match(self, notification_service, sample_items):
        """Test query not matching."""
        item = sample_items[1]  # Adidas Sneakers
        query_words = ["nike", "shoes"]
        
        result = notification_service._item_matches_query(item, query_words, None)
        assert result is False
    
    def test_item_matches_query_with_brand_filter(self, notification_service, sample_items):
        """Test query matching with brand filter."""
        item = sample_items[0]  # Nike Air Max 90
        query_words = ["shoes"]
        filters = {"brand": "Nike"}
        
        result = notification_service._item_matches_query(item, query_words, filters)
        assert result is True
    
    def test_item_matches_query_brand_filter_no_match(self, notification_service, sample_items):
        """Test query not matching brand filter."""
        item = sample_items[0]  # Nike Air Max 90
        query_words = ["shoes"]
        filters = {"brand": "Adidas"}
        
        result = notification_service._item_matches_query(item, query_words, filters)
        assert result is False
    
    def test_item_matches_query_with_price_filter(self, notification_service, sample_items):
        """Test query matching with price filter."""
        item = sample_items[0]  # Nike Air Max 90, price 75.00
        query_words = ["nike"]
        filters = {"min_price": 50, "max_price": 100}
        
        result = notification_service._item_matches_query(item, query_words, filters)
        assert result is True
    
    def test_item_matches_query_price_too_low(self, notification_service, sample_items):
        """Test query not matching due to price too low."""
        item = sample_items[2]  # Nike Running Shoes, price 45.00
        query_words = ["nike"]
        filters = {"min_price": 50}
        
        result = notification_service._item_matches_query(item, query_words, filters)
        assert result is False
    
    def test_item_matches_query_price_too_high(self, notification_service, sample_items):
        """Test query not matching due to price too high."""
        item = sample_items[0]  # Nike Air Max 90, price 75.00
        query_words = ["nike"]
        filters = {"max_price": 50}
        
        result = notification_service._item_matches_query(item, query_words, filters)
        assert result is False
    
    def test_match_items_to_search(self, notification_service, sample_items, sample_saved_search):
        """Test matching items to saved search."""
        # Should match Nike items within price range
        matching_items = notification_service._match_items_to_search(
            sample_items, sample_saved_search
        )
        
        assert len(matching_items) == 2  # Two Nike items
        assert matching_items[0].item_id == 1  # Nike Air Max 90
        assert matching_items[1].item_id == 3  # Nike Running Shoes
        assert matching_items[0].title == "Nike Air Max 90"
        assert matching_items[0].price == "75.00 EUR"
        assert matching_items[0].brand == "Nike"
    
    @pytest.mark.asyncio
    async def test_find_matching_users_no_items(self, notification_service):
        """Test finding matching users with no items."""
        mock_session = AsyncMock()
        
        result = await notification_service.find_matching_users(mock_session, [])
        
        assert result == []
        mock_session.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_find_matching_users_no_active_users(self, notification_service, sample_items):
        """Test finding matching users with no active users."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = await notification_service.find_matching_users(mock_session, sample_items)
        
        assert result == []
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_matching_users_with_matches(
        self, notification_service, sample_items, sample_user, sample_saved_search
    ):
        """Test finding matching users with actual matches."""
        # Setup user with saved search
        sample_user.saved_searches = [sample_saved_search]
        
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [sample_user]
        mock_session.execute.return_value = mock_result
        
        result = await notification_service.find_matching_users(mock_session, sample_items)
        
        assert len(result) == 1
        user_notification = result[0]
        assert user_notification.user_id == sample_user.id
        assert user_notification.tg_id == sample_user.tg_id
        assert user_notification.first_name == sample_user.first_name
        assert len(user_notification.items) == 2  # Two Nike items match
        assert user_notification.search_queries == ["nike shoes"]
    
    @pytest.mark.asyncio
    async def test_send_user_notification(self, notification_service, mock_bot):
        """Test sending notification to a single user."""
        notification = UserNotification(
            user_id=1,
            tg_id=123456789,
            first_name="Test",
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
        
        await notification_service._send_user_notification(notification)
        
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        
        assert call_args[1]["chat_id"] == 123456789
        assert "Test!" in call_args[1]["text"]
        assert "nike shoes" in call_args[1]["text"]
        assert "Nike Air Max 90" in call_args[1]["text"]
        assert "75.00 EUR" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "HTML"
        assert call_args[1]["disable_web_page_preview"] is True
    
    @pytest.mark.asyncio
    async def test_send_batch_notifications_success(self, notification_service, mock_bot):
        """Test successful batch notification sending."""
        notifications = [
            UserNotification(
                user_id=1,
                tg_id=123456789,
                first_name="Test1",
                items=[
                    NotificationItem(
                        item_id=1,
                        title="Test Item",
                        price="50.00 EUR",
                        brand="Test",
                        url="https://vinted.at/items/1",
                        preview_img=None
                    )
                ],
                search_queries=["test"]
            ),
            UserNotification(
                user_id=2,
                tg_id=987654321,
                first_name="Test2",
                items=[
                    NotificationItem(
                        item_id=2,
                        title="Another Item",
                        price="30.00 EUR",
                        brand="Another",
                        url="https://vinted.at/items/2",
                        preview_img=None
                    )
                ],
                search_queries=["another"]
            )
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await notification_service.send_batch_notifications(notifications)
        
        assert result["sent"] == 2
        assert result["failed"] == 0
        assert result["blocked"] == 0
        assert mock_bot.send_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_send_batch_notifications_with_blocked_user(self, notification_service, mock_bot):
        """Test batch notifications with blocked user."""
        notifications = [
            UserNotification(
                user_id=1,
                tg_id=123456789,
                first_name="Test1",
                items=[
                    NotificationItem(
                        item_id=1,
                        title="Test Item",
                        price="50.00 EUR",
                        brand="Test",
                        url="https://vinted.at/items/1",
                        preview_img=None
                    )
                ],
                search_queries=["test"]
            )
        ]
        
        # Mock bot to raise TelegramForbiddenError
        mock_bot.send_message.side_effect = TelegramForbiddenError(
            method="sendMessage", message="Forbidden: bot was blocked by the user"
        )
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await notification_service.send_batch_notifications(notifications)
        
        assert result["sent"] == 0
        assert result["failed"] == 0
        assert result["blocked"] == 1
    
    @pytest.mark.asyncio
    async def test_send_batch_notifications_with_telegram_error(self, notification_service, mock_bot):
        """Test batch notifications with Telegram error."""
        notifications = [
            UserNotification(
                user_id=1,
                tg_id=123456789,
                first_name="Test1",
                items=[
                    NotificationItem(
                        item_id=1,
                        title="Test Item",
                        price="50.00 EUR",
                        brand="Test",
                        url="https://vinted.at/items/1",
                        preview_img=None
                    )
                ],
                search_queries=["test"]
            )
        ]
        
        # Mock bot to raise TelegramBadRequest
        mock_bot.send_message.side_effect = TelegramBadRequest(
            method="sendMessage", message="Bad Request: chat not found"
        )
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await notification_service.send_batch_notifications(notifications)
        
        assert result["sent"] == 0
        assert result["failed"] == 1
        assert result["blocked"] == 0
    
    @pytest.mark.asyncio
    async def test_send_subscription_expiry_notifications(self, notification_service, mock_bot):
        """Test sending subscription expiry notifications."""
        # Create users with expiring subscriptions
        tomorrow = datetime.utcnow() + timedelta(days=1)
        
        trial_user = User(
            id=1,
            tg_id=123456789,
            first_name="TrialUser",
            trial_expires=tomorrow,
            subscription_expires=None
        )
        
        premium_user = User(
            id=2,
            tg_id=987654321,
            first_name="PremiumUser",
            trial_expires=datetime.utcnow() - timedelta(days=10),
            subscription_expires=tomorrow
        )
        
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [trial_user, premium_user]
        mock_session.execute.return_value = mock_result
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await notification_service.send_subscription_expiry_notifications(mock_session)
        
        assert result["sent"] == 2
        assert result["failed"] == 0
        assert result["blocked"] == 0
        assert mock_bot.send_message.call_count == 2
        
        # Check message content
        calls = mock_bot.send_message.call_args_list
        
        # Trial user message
        trial_call = calls[0]
        assert trial_call[1]["chat_id"] == 123456789
        assert "trial period expires tomorrow" in trial_call[1]["text"]
        
        # Premium user message
        premium_call = calls[1]
        assert premium_call[1]["chat_id"] == 987654321
        assert "premium subscription expires tomorrow" in premium_call[1]["text"]
    
    @pytest.mark.asyncio
    async def test_send_expiry_notification_trial_user(self, notification_service, mock_bot):
        """Test sending expiry notification to trial user."""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        user = User(
            id=1,
            tg_id=123456789,
            first_name="TestUser",
            trial_expires=tomorrow,
            subscription_expires=None
        )
        
        await notification_service._send_expiry_notification(user)
        
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        
        assert call_args[1]["chat_id"] == 123456789
        assert "TestUser!" in call_args[1]["text"]
        assert "trial period expires tomorrow" in call_args[1]["text"]
        assert "/pay to upgrade" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_send_expiry_notification_premium_user(self, notification_service, mock_bot):
        """Test sending expiry notification to premium user."""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        user = User(
            id=1,
            tg_id=123456789,
            first_name="TestUser",
            trial_expires=datetime.utcnow() - timedelta(days=10),
            subscription_expires=tomorrow
        )
        
        await notification_service._send_expiry_notification(user)
        
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        
        assert call_args[1]["chat_id"] == 123456789
        assert "TestUser!" in call_args[1]["text"]
        assert "premium subscription expires tomorrow" in call_args[1]["text"]
        assert "/pay to upgrade" in call_args[1]["text"]
    
    def test_notification_item_creation(self):
        """Test NotificationItem data class."""
        item = NotificationItem(
            item_id=1,
            title="Test Item",
            price="50.00 EUR",
            brand="TestBrand",
            url="https://vinted.at/items/1",
            preview_img="https://example.com/img.jpg"
        )
        
        assert item.item_id == 1
        assert item.title == "Test Item"
        assert item.price == "50.00 EUR"
        assert item.brand == "TestBrand"
        assert item.url == "https://vinted.at/items/1"
        assert item.preview_img == "https://example.com/img.jpg"
    
    def test_user_notification_creation(self):
        """Test UserNotification data class."""
        items = [
            NotificationItem(
                item_id=1,
                title="Test Item",
                price="50.00 EUR",
                brand="TestBrand",
                url="https://vinted.at/items/1",
                preview_img=None
            )
        ]
        
        notification = UserNotification(
            user_id=1,
            tg_id=123456789,
            first_name="TestUser",
            items=items,
            search_queries=["test query"]
        )
        
        assert notification.user_id == 1
        assert notification.tg_id == 123456789
        assert notification.first_name == "TestUser"
        assert len(notification.items) == 1
        assert notification.search_queries == ["test query"]
    
    def test_max_items_per_notification_limit(self, notification_service, sample_saved_search):
        """Test that items per notification are limited."""
        # Create more items than the limit
        items = []
        for i in range(10):  # More than max_items_per_notification (5)
            items.append(Item(
                id=i,
                title=f"Nike Shoes {i}",
                price=Decimal("50.00"),
                currency="EUR",
                brand="Nike",
                url=f"https://vinted.at/items/{i}",
                ships_to_at=True
            ))
        
        matching_items = notification_service._match_items_to_search(
            items, sample_saved_search
        )
        
        # Should be limited to max_items_per_notification
        assert len(matching_items) == notification_service.max_items_per_notification
    
    @pytest.mark.asyncio
    async def test_empty_notifications_list(self, notification_service):
        """Test handling empty notifications list."""
        result = await notification_service.send_batch_notifications([])
        
        assert result["sent"] == 0
        assert result["failed"] == 0
        assert result["blocked"] == 0