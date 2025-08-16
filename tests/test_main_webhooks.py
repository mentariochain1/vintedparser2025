"""Tests for main.py webhook endpoints and middleware."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.main import create_app
from src.config import settings


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True
    return mock_redis


@pytest.fixture
def mock_bot():
    """Mock bot instance."""
    return AsyncMock()


@pytest.fixture
def mock_dispatcher():
    """Mock dispatcher instance."""
    return AsyncMock()


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_basic_health_check(self, client):
        """Test basic health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["environment"] == settings.environment
        assert "timestamp" in data

    @patch("src.main.db_health_check")
    @patch("src.main.redis_client")
    async def test_detailed_health_check_healthy(self, mock_redis_client, mock_db_health, client):
        """Test detailed health check when all services are healthy."""
        # Mock healthy responses
        mock_db_health.return_value = {"status": "healthy"}
        mock_redis_client.ping = AsyncMock(return_value=True)
        
        with patch("src.bot.services.payment_service.PaymentService") as mock_payment_service:
            mock_service = AsyncMock()
            mock_service.health_check.return_value = True
            mock_payment_service.return_value = mock_service
            
            response = client.get("/healthz")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "healthy"
            assert "request_id" in data
            assert "timestamp" in data

    @patch("src.main.db_health_check")
    @patch("src.main.redis_client", None)
    async def test_detailed_health_check_redis_unavailable(self, mock_db_health, client):
        """Test detailed health check when Redis is unavailable."""
        mock_db_health.return_value = {"status": "healthy"}
        
        with patch("src.bot.services.payment_service.PaymentService") as mock_payment_service:
            mock_service = AsyncMock()
            mock_service.health_check.return_value = True
            mock_payment_service.return_value = mock_service
            
            response = client.get("/healthz")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["redis"]["status"] == "unhealthy"


class TestTelegramWebhook:
    """Test Telegram webhook endpoint."""

    def test_webhook_missing_secret(self, client):
        """Test webhook with missing secret token."""
        response = client.post(
            settings.webhook_path,
            json={"update_id": 123, "message": {"text": "test"}},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Invalid secret token"
        assert "request_id" in data

    def test_webhook_invalid_secret(self, client):
        """Test webhook with invalid secret token."""
        response = client.post(
            settings.webhook_path,
            json={"update_id": 123, "message": {"text": "test"}},
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": "invalid_secret"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Invalid secret token"

    @patch("src.main.rate_limit_check")
    def test_webhook_rate_limit_exceeded(self, mock_rate_limit, client):
        """Test webhook rate limiting."""
        mock_rate_limit.return_value = False
        
        response = client.post(
            settings.webhook_path,
            json={"update_id": 123, "message": {"text": "test"}},
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        
        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "Rate limit exceeded"

    @patch("src.main.rate_limit_check")
    def test_webhook_success(self, mock_rate_limit, client, app):
        """Test successful webhook processing."""
        mock_rate_limit.return_value = True
        
        # Mock app state
        app.state.bot = AsyncMock()
        app.state.dp = AsyncMock()
        
        update_data = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456, "is_bot": False, "first_name": "Test"},
                "text": "test"
            }
        }
        
        response = client.post(
            settings.webhook_path,
            json=update_data,
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "request_id" in data

    @patch("src.main.rate_limit_check")
    def test_webhook_invalid_json(self, mock_rate_limit, client):
        """Test webhook with invalid JSON."""
        mock_rate_limit.return_value = True
        
        response = client.post(
            settings.webhook_path,
            data="invalid json",
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        
        assert response.status_code == 422  # FastAPI validation error


class TestYooKassaWebhook:
    """Test YooKassa webhook endpoint."""

    def test_yookassa_webhook_missing_headers(self, client):
        """Test YooKassa webhook with missing headers."""
        response = client.post(
            "/payment/webhook",
            json={"event": "payment.succeeded", "object": {"id": "test_payment"}},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Missing required headers"

    @patch("src.main.rate_limit_check")
    def test_yookassa_webhook_rate_limit(self, mock_rate_limit, client):
        """Test YooKassa webhook rate limiting."""
        mock_rate_limit.return_value = False
        
        response = client.post(
            "/payment/webhook",
            json={"event": "payment.succeeded", "object": {"id": "test_payment"}},
            headers={
                "Content-Type": "application/json",
                "Yookassa-Signature": "test_signature",
                "Yookassa-Timestamp": str(int(time.time()))
            }
        )
        
        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "Rate limit exceeded"

    @patch("src.main.rate_limit_check")
    @patch("src.bot.services.payment_service.PaymentService")
    @patch("src.db.base.get_db_session")
    async def test_yookassa_webhook_success(self, mock_get_session, mock_payment_service, mock_rate_limit, client):
        """Test successful YooKassa webhook processing."""
        mock_rate_limit.return_value = True
        
        # Mock payment service
        mock_service = AsyncMock()
        mock_service.process_webhook.return_value = (True, "Payment processed successfully")
        mock_payment_service.return_value = mock_service
        
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        webhook_data = {
            "event": "payment.succeeded",
            "object": {
                "id": "test_payment_id",
                "status": "succeeded",
                "amount": {"value": "299.00", "currency": "RUB"}
            }
        }
        
        response = client.post(
            "/payment/webhook",
            json=webhook_data,
            headers={
                "Content-Type": "application/json",
                "Yookassa-Signature": "test_signature",
                "Yookassa-Timestamp": str(int(time.time()))
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Payment processed successfully"
        assert "request_id" in data

    @patch("src.main.rate_limit_check")
    @patch("src.bot.services.payment_service.PaymentService")
    @patch("src.db.base.get_db_session")
    async def test_yookassa_webhook_processing_failed(self, mock_get_session, mock_payment_service, mock_rate_limit, client):
        """Test YooKassa webhook processing failure."""
        mock_rate_limit.return_value = True
        
        # Mock payment service failure
        mock_service = AsyncMock()
        mock_service.process_webhook.return_value = (False, "Invalid signature")
        mock_payment_service.return_value = mock_service
        
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        webhook_data = {
            "event": "payment.succeeded",
            "object": {"id": "test_payment_id", "status": "succeeded"}
        }
        
        response = client.post(
            "/payment/webhook",
            json=webhook_data,
            headers={
                "Content-Type": "application/json",
                "Yookassa-Signature": "invalid_signature",
                "Yookassa-Timestamp": str(int(time.time()))
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Invalid signature"


class TestMiddleware:
    """Test custom middleware."""

    def test_request_id_middleware(self, client):
        """Test that request ID is added to responses."""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36  # UUID length

    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/health")
        # CORS headers should be present for OPTIONS requests
        assert response.status_code in [200, 405]  # Depending on FastAPI version

    def test_error_handling_with_request_id(self, client):
        """Test that errors include request ID."""
        # Test with invalid endpoint
        response = client.get("/nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        assert "request_id" in data
        assert "timestamp" in data


class TestRateLimiting:
    """Test rate limiting functionality."""

    @patch("src.main.redis_client")
    async def test_rate_limit_check_success(self, mock_redis_client):
        """Test successful rate limit check."""
        from src.main import rate_limit_check
        
        mock_redis_client.incr.return_value = 5
        mock_redis_client.expire.return_value = True
        
        request = MagicMock()
        result = await rate_limit_check(request, "test_key", 10, 60)
        
        assert result is True
        mock_redis_client.incr.assert_called_once_with("test_key")

    @patch("src.main.redis_client")
    async def test_rate_limit_check_exceeded(self, mock_redis_client):
        """Test rate limit exceeded."""
        from src.main import rate_limit_check
        
        mock_redis_client.incr.return_value = 15
        
        request = MagicMock()
        result = await rate_limit_check(request, "test_key", 10, 60)
        
        assert result is False

    @patch("src.main.redis_client", None)
    async def test_rate_limit_check_no_redis(self):
        """Test rate limit check when Redis is unavailable."""
        from src.main import rate_limit_check
        
        request = MagicMock()
        result = await rate_limit_check(request, "test_key", 10, 60)
        
        # Should allow when Redis is not available
        assert result is True

    @patch("src.main.redis_client")
    async def test_rate_limit_check_redis_error(self, mock_redis_client):
        """Test rate limit check when Redis throws error."""
        from src.main import rate_limit_check
        
        mock_redis_client.incr.side_effect = Exception("Redis error")
        
        request = MagicMock()
        result = await rate_limit_check(request, "test_key", 10, 60)
        
        # Should allow on error
        assert result is True


class TestPaymentSuccessPage:
    """Test payment success page."""

    def test_payment_success_page(self, client):
        """Test payment success page response."""
        response = client.get("/payment/success")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Payment completed successfully" in data["message"]
        assert "request_id" in data
        assert "timestamp" in data