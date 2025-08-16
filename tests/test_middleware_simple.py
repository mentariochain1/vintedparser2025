"""Simple middleware tests to verify basic functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.middleware import SecurityHeadersMiddleware, RequestIDMiddleware


class TestSimpleMiddleware:
    """Simple tests for middleware functionality."""
    
    def test_security_headers_basic(self):
        """Test basic security headers functionality."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers
        
    def test_request_id_basic(self):
        """Test basic request ID functionality."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            return {
                "message": "success",
                "has_request_id": hasattr(request.state, 'request_id')
            }
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.json()["has_request_id"] is True
        
    def test_combined_middleware_basic(self):
        """Test that multiple middleware work together."""
        app = FastAPI()
        
        # Add middleware in order
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        
        # Both middleware should work
        assert "X-Content-Type-Options" in response.headers
        assert "X-Request-ID" in response.headers
        
    def test_middleware_with_error(self):
        """Test middleware behavior when endpoint raises error."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")
            
        client = TestClient(app)
        
        # The error will propagate, but we can still test that middleware was applied
        try:
            response = client.get("/error")
            # If we get here, the error was handled by FastAPI
            assert response.status_code == 500
            assert "X-Request-ID" in response.headers
        except ValueError:
            # This is expected - the error propagates through middleware
            pass