"""Test configuration and fixtures."""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment variables
os.environ.update({
    "BOT_TOKEN": "test_token",
    "WEBHOOK_DOMAIN": "https://test.example.com",
    "WEBHOOK_SECRET": "test_secret",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_SERVICE_KEY": "test_service_key",
    "SUPABASE_ANON_KEY": "test_anon_key",
    "YOOKASSA_SHOP_ID": "test_shop_id",
    "YOOKASSA_SECRET_KEY": "test_secret_key",
    "REFERRAL_SECRET": "test_referral_secret",
    "VINTED_RATE_LIMIT": "30",
    "MAX_CONCURRENT_REQUESTS": "10",
    "DEFAULT_TRIAL_DAYS": "7",
    "REFERRAL_BONUS_DAYS": "3",
    "REDIS_URL": "redis://localhost:6379/1",
})

from src.db.models import User, Payment, Item, Photo, SavedSearch, Referral


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def sample_user() -> User:
    """Create sample user for testing."""
    return User(
        id=1,
        tg_id=123456789,
        username="testuser",
        first_name="Test",
        joined_at=datetime.utcnow(),
        trial_expires=datetime.utcnow() + timedelta(days=7),
        subscription_expires=None,
        referrals_count=0,
        referred_by=None,
    )


@pytest.fixture
def sample_user_with_subscription(sample_user: User) -> User:
    """Create sample user with active subscription."""
    sample_user.subscription_expires = datetime.utcnow() + timedelta(days=30)
    return sample_user


@pytest.fixture
def sample_expired_user() -> User:
    """Create sample user with expired trial and subscription."""
    return User(
        id=2,
        tg_id=987654321,
        username="expireduser",
        first_name="Expired",
        joined_at=datetime.utcnow() - timedelta(days=30),
        trial_expires=datetime.utcnow() - timedelta(days=1),
        subscription_expires=datetime.utcnow() - timedelta(days=1),
        referrals_count=0,
        referred_by=None,
    )


@pytest.fixture
def sample_payment() -> Payment:
    """Create sample payment for testing."""
    return Payment(
        id=1,
        user_id=1,
        yookassa_id="test_payment_id",
        amount=299.0,
        currency="RUB",
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_item() -> Item:
    """Create sample Vinted item for testing."""
    return Item(
        id=12345,
        title="Test Item",
        price=25.0,
        currency="EUR",
        brand="Test Brand",
        size="M",
        condition="Good",
        description="Test description",
        seller_id=67890,
        url="https://www.vinted.at/items/12345",
        preview_img="https://example.com/preview.jpg",
        ships_to_at=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_photos(sample_item: Item) -> list[Photo]:
    """Create sample photos for testing."""
    return [
        Photo(
            id=1,
            item_id=sample_item.id,
            url="https://example.com/photo1.jpg",
            order_no=0,
            created_at=datetime.utcnow(),
        ),
        Photo(
            id=2,
            item_id=sample_item.id,
            url="https://example.com/photo2.jpg",
            order_no=1,
            created_at=datetime.utcnow(),
        ),
    ]


@pytest.fixture
def sample_saved_search(sample_user: User) -> SavedSearch:
    """Create sample saved search for testing."""
    return SavedSearch(
        id=1,
        user_id=sample_user.id,
        query="vintage sneakers",
        filters={"brand_ids": [1, 2, 3], "price_to": 50},
        notifications_enabled=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_referral() -> Referral:
    """Create sample referral for testing."""
    return Referral(
        id=1,
        inviter_id=1,
        invitee_id=2,
        bonus_awarded=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_vinted_item() -> MagicMock:
    """Create mock Vinted item for API responses."""
    item = MagicMock()
    item.id = 12345
    item.title = "Test Item"
    item.price = 25.0
    item.currency = "EUR"
    item.brand = "Test Brand"
    item.size = "M"
    item.condition = "Good"
    item.url = "https://www.vinted.at/items/12345"
    item.photo = "https://example.com/preview.jpg"
    item.seller_id = 67890
    item.description = "Test description"
    item.photos = [
        MagicMock(url="https://example.com/photo1.jpg"),
        MagicMock(url="https://example.com/photo2.jpg"),
    ]
    return item


@pytest.fixture
def mock_vinted_search_result(mock_vinted_item: MagicMock) -> MagicMock:
    """Create mock Vinted search result."""
    result = MagicMock()
    result.items = [mock_vinted_item]
    return result


@pytest.fixture
def mock_vinted_item_info(mock_vinted_item: MagicMock) -> MagicMock:
    """Create mock Vinted item info result."""
    result = MagicMock()
    result.item = mock_vinted_item
    return result


@pytest.fixture
def mock_yookassa_payment() -> MagicMock:
    """Create mock YooKassa payment."""
    payment = MagicMock()
    payment.id = "test_payment_id"
    payment.status = "pending"
    payment.amount = MagicMock()
    payment.amount.value = "299.00"
    payment.amount.currency = "RUB"
    payment.created_at = datetime.utcnow().isoformat()
    payment.confirmation = MagicMock()
    payment.confirmation.confirmation_url = "https://yookassa.ru/checkout/test_payment_id"
    payment.metadata = {"user_id": "1"}
    return payment


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = 1
    redis.exists.return_value = False
    redis.setnx.return_value = True
    redis.expire.return_value = True
    return redis


@pytest.fixture
def mock_bot() -> MagicMock:
    """Create mocked Telegram bot."""
    bot = MagicMock()
    bot.token = "TEST_TOKEN"
    return bot


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock()
    settings.bot_token = "test_token"
    settings.webhook_domain = "https://test.example.com"
    settings.webhook_secret = "test_secret"
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_key = "test_service_key"
    settings.supabase_anon_key = "test_anon_key"
    settings.yookassa_shop_id = "test_shop_id"
    settings.yookassa_secret_key = "test_secret_key"
    settings.referral_secret = "test_referral_secret"
    settings.default_trial_days = 7
    settings.referral_bonus_days = 3
    settings.vinted_rate_limit = 30
    settings.max_concurrent_requests = 10
    settings.redis_url = "redis://localhost:6379/1"
    return settings


@pytest.fixture
def valid_webhook_signature() -> tuple[bytes, str, str]:
    """Create valid webhook signature for testing."""
    import hashlib
    import hmac
    
    payload = b'{"event": "payment.succeeded", "object": {"id": "test_payment"}}'
    timestamp = str(int(time.time()))
    secret_key = "test_secret_key"
    
    message = payload + timestamp.encode()
    signature = hmac.new(secret_key.encode(), message, hashlib.sha256).hexdigest()
    
    return payload, signature, timestamp


@pytest.fixture
def mock_database_error() -> Exception:
    """Create mock database error."""
    return Exception("Database connection failed")


@pytest.fixture
def mock_api_error() -> Exception:
    """Create mock API error."""
    return Exception("External API unavailable")


# Async context managers for testing
@pytest.fixture
async def async_context_manager():
    """Async context manager for testing."""
    class AsyncContextManager:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return AsyncContextManager()


# Utility functions for tests
def create_mock_user(
    user_id: int = 1,
    tg_id: int = 123456789,
    username: str = "testuser",
    trial_days: int = 7,
    subscription_days: int | None = None,
    referrals_count: int = 0,
) -> User:
    """Create a mock user with specified parameters."""
    now = datetime.utcnow()
    return User(
        id=user_id,
        tg_id=tg_id,
        username=username,
        first_name="Test",
        joined_at=now,
        trial_expires=now + timedelta(days=trial_days),
        subscription_expires=now + timedelta(days=subscription_days) if subscription_days else None,
        referrals_count=referrals_count,
        referred_by=None,
    )


def create_mock_payment(
    payment_id: int = 1,
    user_id: int = 1,
    yookassa_id: str = "test_payment",
    amount: float = 299.0,
    status: str = "pending",
) -> Payment:
    """Create a mock payment with specified parameters."""
    return Payment(
        id=payment_id,
        user_id=user_id,
        yookassa_id=yookassa_id,
        amount=amount,
        currency="RUB",
        status=status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def create_mock_item(
    item_id: int = 12345,
    title: str = "Test Item",
    price: float = 25.0,
    brand: str = "Test Brand",
) -> Item:
    """Create a mock item with specified parameters."""
    return Item(
        id=item_id,
        title=title,
        price=price,
        currency="EUR",
        brand=brand,
        size="M",
        condition="Good",
        description="Test description",
        seller_id=67890,
        url=f"https://www.vinted.at/items/{item_id}",
        preview_img=f"https://example.com/preview_{item_id}.jpg",
        ships_to_at=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )