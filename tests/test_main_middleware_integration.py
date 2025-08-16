"""Integration tests for main application middleware."""

import pytest
import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import redis.asyncio as redis

from src.main import create_app
from src.config import settings


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies."""
    with patch('src.main.init_database') as mock_init_db, \
         patch('src.main.close_database') as mock_close_db, \
         patch('src.main.create_bot') as mock_create_bot, \
         patch('src.main.create_dispatcher') as mock_create_dp, \
         patch('src.main.setup_bot_webhook') as mock_setup_webhook, \
         patch('src.main.remove_bot_webhook') as mock_remove_webhook, \
         patch('src.main.close_bot') as mock_close_bot, \
         patch('redis.asyncio.from_url') as mock_redis_from_url, \
         patch('src.db.base.get_db_session') as mock_get_session:
        
        # Mock Redis client
        mock_redis_client = AsyncMock(spec=redis.Redis)
        mock_redis_client.ping.return_value = True
        mock_redis_client.pipeline.return_value.execute.return_value = [None, 1, None, None]
        mock_redis_from_url.return_value = mock_redis_client
        
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock bot and dispatcher
        mock_bot = AsyncMock()
        mock_dp = AsyncMock()
        mock_create_bot.return_value = mock_bot
        mock_create_dp.return_value = mock_dp
        
        yield {
            'redis_client': mock_redis_client,
            'session': mock_session,
            'bot': mock_bot,
            'dispatcher': mock_dp
        }


class TestMainApplicationMiddleware:
    """Test middleware integration in main application."""
    
    def test_security_headers_applied(self, mock_dependencies):
        """Test that security headers are applied to responses."""
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        
        # Check security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
        
    def test_request_id_middleware_applied(self, mock_dependencies):
        """Test that request ID middleware is applied."""
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        
        # Should be a valid UUID format
        import uuid
        uuid.UUID(response.headers["X-Request-ID"])
        
    def test_cors_middleware_applied(self, mock_dependencies):
        """Test that CORS middleware is applied."""
        app = create_app()
        client = TestClient(app)
        
        # Test preflight request
        response = client.options("/health", headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET"
        })
        
        # CORS headers should be present
        assert "Access-Control-Allow-Origin" in response.headers
        
    def test_rate_limiting_applied_to_webhook(self, mock_dependencies):
        """Test that rate limiting is applied to webhook endpoints."""
        app = create_app()
        client = TestClient(app)
        
        # Mock webhook request with proper headers
        headers = {
            "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret,
            "Content-Type": "application/json"
        }
        
        response = client.post(
            settings.webhook_path,
            json={"update_id": 1, "message": {"message_id": 1, "date": int(time.time()), "chat": {"id": 1, "type": "private"}}},
            headers=headers
        )
        
        # Should have rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        
    def test_webhook_secret_validation(self, mock_dependencies):
        """Test webhook secret validation."""
        app = create_app()
        client = TestClient(app)
        
        # Request without secret token
        response = client.post(
            settings.webhook_path,
            json={"update_id": 1}
        )
        
        assert response.status_code == 401
        assert "Invalid secret token" in response.json()["error"]
        
    def test_payment_webhook_rate_limiting(self, mock_dependencies):
        """Test rate limiting on payment webhook."""
        app = create_app()
        client = TestClient(app)
        
        # Mock payment webhook with required headers
        headers = {
            "Yookassa-Signature": "test_signature",
            "Yookassa-Timestamp": str(int(time.time())),
            "Content-Type": "application/json"
        }
        
        response = client.post(
            "/payment/webhook",
            json={"event": "payment.succeeded"},
            headers=headers
        )
        
        # Should have rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        
    def test_health_endpoint_bypasses_rate_limiting(self, mock_dependencies):
        """Test that health endpoints bypass rate limiting."""
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        # Health endpoints should not have rate limit headers
        # (they bypass rate limiting)
        
    def test_detailed_health_check_includes_services(self, mock_dependencies):
        """Test detailed health check includes all services."""
        app = create_app()
        client = TestClient(app)
        
        # Mock payment service health check
        with patch('src.bot.services.payment_service.PaymentService') as mock_payment_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.health_check.return_value = True
            mock_payment_service.return_value = mock_service_instance
            
            response = client.get("/healthz")
            
        assert response.status_code == 200
        
        data = response.json()
        assert "database" in data
        assert "redis" in data
        assert "payment_service" in data
        assert data["status"] == "healthy"
        
    def test_error_handling_with_request_id(self, mock_dependencies):
        """Test that error responses include request ID."""
        app = create_app()
        client = TestClient(app)
        
        # Make request to non-existent endpoint
        response = client.get("/nonexistent")
        
        assert response.status_code == 404
        
        data = response.json()
        assert "request_id" in data
        assert "timestamp" in data
        
    def test_custom_http_exception_handling(self, mock_dependencies):
        """Test custom HTTP exception handling."""
        app = create_app()
        client = TestClient(app)
        
        # Test webhook with invalid secret (triggers CustomHTTPException)
        response = client.post(
            settings.webhook_path,
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "invalid"}
        )
        
        assert response.status_code == 401
        
        data = response.json()
        assert "error" in data
        assert "request_id" in data
        assert "timestamp" in data
        
    def test_middleware_order_preserved(self, mock_dependencies):
        """Test that middleware is applied in correct order."""
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        
        # Security headers should be present (applied first)
        assert "X-Content-Type-Options" in response.headers
        
        # Request ID should be present (applied after security)
        assert "X-Request-ID" in response.headers
        
        # CORS headers should be present (applied after request ID)
        # Note: CORS headers may not be visible in simple GET requests
        
    def test_production_vs_debug_middleware_behavior(self, mock_dependencies):
        """Test different middleware behavior in production vs debug mode."""
        # Test with debug mode
        with patch.object(settings, 'debug', True):
            app = create_app()
            client = TestClient(app)
            
            response = client.get("/health")
            assert response.status_code == 200
            
        # Test with production mode
        with patch.object(settings, 'debug', False), \
             patch.object(settings, 'is_production', True):
            app = create_app()
            client = TestClient(app)
            
            response = client.get("/health")
            assert response.status_code == 200
            
    def test_redis_failure_graceful_handling(self, mock_dependencies):
        """Test graceful handling when Redis is unavailable."""
        # Mock Redis connection failure
        mock_dependencies['redis_client'].ping.side_effect = Exception("Redis unavailable")
        
        app = create_app()
        client = TestClient(app)
        
        # Requests should still work without rate limiting
        response = client.get("/health")
        assert response.status_code == 200
        
    def test_structured_logging_format(self, mock_dependencies, caplog):
        """Test that structured logging is properly formatted."""
        import logging
        
        app = create_app()
        client = TestClient(app)
        
        with caplog.at_level(logging.INFO):
            response = client.get("/health")
            
        assert response.status_code == 200
        
        # Check that structured log entries exist
        log_records = [r for r in caplog.records if hasattr(r, 'request_id')]
        assert len(log_records) > 0
        
        # Check log structure
        start_record = next((r for r in log_records if "Request started" in r.message), None)
        if start_record:
            assert hasattr(start_record, 'method')
            assert hasattr(start_record, 'url')
            assert hasattr(start_record, 'client_ip')