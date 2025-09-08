"""Test configuration and fixtures for Vinted Parser Bot."""

import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

# Test configuration
TEST_CONFIG = {
    "bot_token": "test_bot_token",
    "webhook_domain": "https://test.example.com",
    "webhook_path": "/telegram",
    "webhook_secret": "test_secret",
    "database_url": "postgresql+asyncpg://test:test@localhost:5432/test_db",
    "redis_url": "redis://localhost:6379/1",
    "environment": "test",
    "debug": True,
    "log_level": "DEBUG"
}


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return TEST_CONFIG.copy()


@pytest.fixture
def mock_settings(test_config):
    """Mock settings for testing."""
    mock = Mock()
    for key, value in test_config.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.close.return_value = None
    return redis_mock


@pytest.fixture
def mock_database_session():
    """Mock database session for testing."""
    session_mock = AsyncMock()
    session_mock.execute.return_value = AsyncMock()
    session_mock.commit.return_value = None
    session_mock.rollback.return_value = None
    session_mock.close.return_value = None
    return session_mock


@pytest.fixture
def sample_vinted_item() -> Dict[str, Any]:
    """Sample Vinted item for testing."""
    return {
        "id": 12345,
        "title": "Test Item",
        "price": {"amount": 25.99, "currency_code": "EUR"},
        "brand": {"title": "Nike", "slug": "nike"},
        "size": {"title": "M"},
        "user": {
            "login": "testuser",
            "city": "Vienna"
        },
        "photo": {"url": "https://example.com/photo.jpg"},
        "url": "https://www.vinted.at/items/12345-test-item",
        "ships_to_at": True
    }


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Sample user data for testing."""
    return {
        "tg_id": 123456789,
        "username": "testuser",
        "first_name": "Test",
        "trial_expires": "2025-12-31T23:59:59Z",
        "subscription_expires": None,
        "referred_by": None,
        "referrals_count": 0
    }


@pytest.fixture
def mock_telegram_update(sample_user_data) -> Dict[str, Any]:
    """Mock Telegram update for testing."""
    return {
        "update_id": 12345,
        "message": {
            "message_id": 1,
            "from": {
                "id": sample_user_data["tg_id"],
                "username": sample_user_data["username"],
                "first_name": sample_user_data["first_name"]
            },
            "chat": {"id": 123456789, "type": "private"},
            "date": 1640995200,
            "text": "/start"
        }
    }


@pytest.fixture
def mock_telegram_callback_update(sample_user_data) -> Dict[str, Any]:
    """Mock Telegram callback update for testing."""
    return {
        "update_id": 12346,
        "callback_query": {
            "id": "123456789",
            "from": {
                "id": sample_user_data["tg_id"],
                "username": sample_user_data["username"],
                "first_name": sample_user_data["first_name"]
            },
            "message": {
                "message_id": 2,
                "chat": {"id": 123456789, "type": "private"},
                "date": 1640995200
            },
            "chat_instance": "123456789",
            "data": "search:start"
        }
    }


# Custom pytest marks
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "external: marks tests that require external services"
    )
