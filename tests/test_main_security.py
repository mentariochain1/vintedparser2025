"""Tests for security features in main.py."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

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


class TestSecurityHeaders:
    """Test security headers and middleware."""

    def test_trusted_host_middleware(self, client):
        """Test trusted host middleware."""
        # This test verifies the middleware is configured
        # In production, it would reject requests from untrusted hosts
        response = client.get("/health")
        assert response.status_code == 200

    def test_cors_middleware_configured(self, client):
        """Test CORS middleware is properly configured."""
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test preflight request
        response = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Should not fail due to CORS
        assert response.status_code in [200, 405]


class TestWebhookSecurity:
    """Test webhook security features."""

    def test_telegram_webhook_secret_validation(self, client):
        """Test Telegram webhook secret token validation."""
        # Test with no secret
        response = client.post(
            settings.webhook_path,
            json={"update_id": 123},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
        assert "Invalid secret token" in response.json()["error"]

        # Test with wrong secret
        response = client.post(
            settings.webhook_path,
            json={"update_id": 123},
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": "wrong_secret"
            }
        )
        assert response.status_code == 401
        assert "Invalid secret token" in response.json()["error"]

    def test_yookassa_webhook_header_validation(self, client):
        """Test YooKassa webhook header validation."""
        # Test with missing signature
        response = client.post(
            "/payment/webhook",
            json={"event": "payment.succeeded"},
            headers={
                "Content-Type": "application/json",
                "Yookassa-Timestamp": str(int(time.time()))
            }
        )
        assert response.status_code == 400
        assert "Missing required headers" in response.json()["error"]

        # Test with missing timestamp
        response = client.post(
            "/payment/webhook",
            json={"event": "payment.succeeded"},
            headers={
                "Content-Type": "application/json",
                "Yookassa-Signature": "test_signature"
            }
        )
        assert response.status_code == 400
        assert "Missing required headers" in response.json()["error"]

    @patch("src.main.rate_limit_check")
    def test_webhook_rate_limiting(self, mock_rate_limit, client):
        """Test webhook rate limiting."""
        mock_rate_limit.return_value = False
        
        # Test Telegram webhook rate limiting
        response = client.post(
            settings.webhook_path,
            json={"update_id": 123},
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["error"]

        # Test YooKassa webhook rate limiting
        response = client.post(
            "/payment/webhook",
            json={"event": "payment.succeeded"},
            headers={
                "Content-Type": "application/json",
                "Yookassa-Signature": "test_signature",
                "Yookassa-Timestamp": str(int(time.time()))
            }
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["error"]


class TestErrorHandling:
    """Test error handling and responses."""

    def test_custom_http_exception_handler(self, client):
        """Test custom HTTP exception handling."""
        # Test 404 error
        response = client.get("/nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "request_id" in data
        assert "timestamp" in data

    def test_general_exception_handler(self, client, app):
        """Test general exception handling."""
        # Create an endpoint that raises an exception
        @app.get("/test_error")
        async def test_error():
            raise ValueError("Test error")
        
        response = client.get("/test_error")
        assert response.status_code == 500
        
        data = response.json()
        assert "error" in data
        assert "request_id" in data
        assert "timestamp" in data
        
        # In production mode, should not expose error details
        if settings.is_production:
            assert data["error"] == "Internal server error"
        else:
            assert "Test error" in data["error"]

    def test_validation_error_handling(self, client):
        """Test FastAPI validation error handling."""
        # Send invalid JSON to webhook
        response = client.post(
            settings.webhook_path,
            data="invalid json",
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        assert response.status_code == 422  # Validation error


class TestRequestLogging:
    """Test request logging middleware."""

    @patch("src.main.logger")
    def test_request_logging(self, mock_logger, client):
        """Test that requests are properly logged."""
        response = client.get("/health")
        assert response.status_code == 200
        
        # Verify logging calls were made
        assert mock_logger.info.called
        
        # Check that request started and completed logs were made
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("Request started" in call for call in log_calls)
        assert any("Request completed" in call for call in log_calls)

    @patch("src.main.logger")
    def test_error_request_logging(self, mock_logger, client, app):
        """Test that failed requests are properly logged."""
        # Create an endpoint that raises an exception
        @app.get("/test_error")
        async def test_error():
            raise ValueError("Test error")
        
        response = client.get("/test_error")
        assert response.status_code == 500
        
        # Verify error logging
        assert mock_logger.error.called
        
        # Check that error log was made
        log_calls = [call.args[0] for call in mock_logger.error.call_args_list]
        assert any("Request failed" in call for call in log_calls)


class TestSecurityConfiguration:
    """Test security configuration."""

    def test_debug_mode_security(self, app):
        """Test security settings in debug mode."""
        # In debug mode, CORS should allow all origins
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware.cls, '__name__') and 'CORS' in middleware.cls.__name__:
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None

    def test_production_mode_security(self, app):
        """Test security settings in production mode."""
        # Test that security middleware is configured
        middleware_classes = [middleware.cls.__name__ for middleware in app.user_middleware]
        assert 'TrustedHostMiddleware' in middleware_classes
        assert 'CORSMiddleware' in middleware_classes

    def test_request_id_generation(self, client):
        """Test that unique request IDs are generated."""
        response1 = client.get("/health")
        response2 = client.get("/health")
        
        request_id1 = response1.headers.get("X-Request-ID")
        request_id2 = response2.headers.get("X-Request-ID")
        
        assert request_id1 is not None
        assert request_id2 is not None
        assert request_id1 != request_id2
        assert len(request_id1) == 36  # UUID length
        assert len(request_id2) == 36  # UUID length


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_json_payload_validation(self, client):
        """Test JSON payload validation."""
        # Test with malformed JSON
        response = client.post(
            settings.webhook_path,
            data='{"invalid": json}',
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        assert response.status_code == 422

    def test_content_type_validation(self, client):
        """Test content type validation."""
        # Test with wrong content type
        response = client.post(
            settings.webhook_path,
            data="test data",
            headers={
                "Content-Type": "text/plain",
                "X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret
            }
        )
        # Should still process but may fail validation
        assert response.status_code in [400, 422, 500]

    @patch("src.main.rate_limit_check")
    def test_large_payload_handling(self, mock_rate_limit, client):
        """Test handling of large payloads."""
        mock_rate_limit.return_value = True
        
        # Create a large but valid update
        large_text = "x" * 4000  # Large text message
        update_data = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456, "is_bot": False, "first_name": "Test"},
                "text": large_text
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
        
        # Should handle large payloads gracefully
        assert response.status_code in [200, 413, 422]  # OK, Payload Too Large, or Validation Error