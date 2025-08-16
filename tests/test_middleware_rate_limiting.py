"""Tests for rate limiting middleware."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
import redis.asyncio as redis

from src.middleware.rate_limiting import RateLimitMiddleware, rate_limit


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_client = AsyncMock(spec=redis.Redis)
    return mock_client


@pytest.fixture
def app_with_rate_limiting(mock_redis):
    """FastAPI app with rate limiting middleware."""
    app = FastAPI()
    
    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=mock_redis,
        default_max_requests=5,
        default_window_seconds=60
    )
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
        
    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}
        
    return app, mock_redis


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""
    
    def test_rate_limit_allows_requests_within_limit(self, app_with_rate_limiting):
        """Test that requests within limit are allowed."""
        app, mock_redis = app_with_rate_limiting
        
        # Mock Redis responses for rate limiting
        mock_redis.pipeline.return_value.execute.return_value = [None, 3, None, None]
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        
    def test_rate_limit_blocks_requests_over_limit(self, app_with_rate_limiting):
        """Test that requests over limit are blocked."""
        app, mock_redis = app_with_rate_limiting
        
        # Mock Redis responses indicating limit exceeded
        mock_redis.pipeline.return_value.execute.return_value = [None, 6, None, None]
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
        assert "X-RateLimit-Limit" in response.headers
        assert "Retry-After" in response.headers
        
    def test_rate_limit_skips_health_endpoints(self, app_with_rate_limiting):
        """Test that health endpoints skip rate limiting."""
        app, mock_redis = app_with_rate_limiting
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        # Redis should not be called for health endpoints
        mock_redis.pipeline.assert_not_called()
        
    def test_rate_limit_handles_redis_failure(self, app_with_rate_limiting):
        """Test that requests are allowed when Redis fails."""
        app, mock_redis = app_with_rate_limiting
        
        # Mock Redis failure
        mock_redis.pipeline.side_effect = Exception("Redis connection failed")
        
        client = TestClient(app)
        response = client.get("/test")
        
        # Request should be allowed despite Redis failure
        assert response.status_code == 200
        
    def test_rate_limit_extracts_client_ip_from_headers(self, app_with_rate_limiting):
        """Test client IP extraction from various headers."""
        app, mock_redis = app_with_rate_limiting
        
        mock_redis.pipeline.return_value.execute.return_value = [None, 1, None, None]
        
        client = TestClient(app)
        
        # Test X-Forwarded-For header
        response = client.get("/test", headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"})
        assert response.status_code == 200
        
        # Test X-Real-IP header
        response = client.get("/test", headers={"X-Real-IP": "192.168.1.2"})
        assert response.status_code == 200


class TestRateLimitDecorator:
    """Test rate limit decorator."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_decorator_sets_config(self):
        """Test that rate limit decorator sets configuration."""
        
        @rate_limit(max_requests=10, window_seconds=30, key_suffix="test")
        async def test_handler(request: Request):
            return {"message": "success"}
            
        # Mock request
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        
        await test_handler(request)
        
        # Check that rate limit config was set
        assert hasattr(request.state, 'rate_limit_config')
        config = request.state.rate_limit_config
        assert config["max_requests"] == 10
        assert config["window_seconds"] == 30
        assert config["key_suffix"] == "test"
        
    @pytest.mark.asyncio
    async def test_rate_limit_decorator_without_request(self):
        """Test decorator works when no request object is found."""
        
        @rate_limit(max_requests=10, window_seconds=30)
        async def test_handler(data: dict):
            return {"message": "success"}
            
        result = await test_handler({"test": "data"})
        assert result == {"message": "success"}


class TestRateLimitMiddlewareIntegration:
    """Integration tests for rate limiting middleware."""
    
    @pytest.mark.asyncio
    async def test_sliding_window_rate_limiting(self, mock_redis):
        """Test sliding window rate limiting logic."""
        middleware = RateLimitMiddleware(
            app=None,
            redis_client=mock_redis,
            default_max_requests=3,
            default_window_seconds=60
        )
        
        # Mock Redis pipeline operations
        mock_pipe = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe
        
        # Test first request (allowed)
        mock_pipe.execute.return_value = [None, 0, None, None]
        is_allowed, remaining, reset_time = await middleware._check_rate_limit(
            "test_key", 3, 60, increment=True
        )
        
        assert is_allowed is True
        assert remaining == 2
        assert reset_time > time.time()
        
        # Test request at limit (allowed)
        mock_pipe.execute.return_value = [None, 2, None, None]
        is_allowed, remaining, reset_time = await middleware._check_rate_limit(
            "test_key", 3, 60, increment=True
        )
        
        assert is_allowed is True
        assert remaining == 0
        
        # Test request over limit (blocked)
        mock_pipe.execute.return_value = [None, 3, None, None]
        is_allowed, remaining, reset_time = await middleware._check_rate_limit(
            "test_key", 3, 60, increment=True
        )
        
        assert is_allowed is False
        assert remaining == 0
        
    def test_rate_limit_headers_in_response(self, app_with_rate_limiting):
        """Test that rate limit headers are added to responses."""
        app, mock_redis = app_with_rate_limiting
        
        # Mock Redis responses
        mock_redis.pipeline.return_value.execute.return_value = [None, 2, None, None]
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "5"
        
    def test_custom_rate_limit_config(self, mock_redis):
        """Test custom rate limit configuration per endpoint."""
        app = FastAPI()
        
        app.add_middleware(
            RateLimitMiddleware,
            redis_client=mock_redis,
            default_max_requests=10,
            default_window_seconds=60
        )
        
        @app.get("/limited")
        @rate_limit(max_requests=2, window_seconds=30)
        async def limited_endpoint(request: Request):
            return {"message": "limited"}
            
        mock_redis.pipeline.return_value.execute.return_value = [None, 1, None, None]
        
        client = TestClient(app)
        response = client.get("/limited")
        
        assert response.status_code == 200
        # Should use custom limit of 2, not default of 10
        assert response.headers["X-RateLimit-Limit"] == "2"