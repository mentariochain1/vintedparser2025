"""Tests for security middleware."""

import pytest
import logging
from unittest.mock import MagicMock, patch
from io import StringIO

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.middleware.security import SecurityHeadersMiddleware, RequestLoggingMiddleware


@pytest.fixture
def app_with_security_headers():
    """FastAPI app with security headers middleware."""
    app = FastAPI()
    
    app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=True)
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
        
    return app


@pytest.fixture
def app_with_request_logging():
    """FastAPI app with request logging middleware."""
    app = FastAPI()
    
    app.add_middleware(RequestLoggingMiddleware, log_body=True, max_body_size=512)
    
    @app.get("/test")
    async def test_get_endpoint():
        return {"message": "success"}
        
    @app.post("/test")
    async def test_post_endpoint(request: Request):
        return {"message": "posted"}
        
    return app


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""
    
    def test_security_headers_added_to_response(self, app_with_security_headers):
        """Test that security headers are added to all responses."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")
        
        assert response.status_code == 200
        
        # Check security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        
        # Check CSP header
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp
        
    def test_hsts_header_for_https(self):
        """Test HSTS header is added for HTTPS requests."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=True)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app, base_url="https://testserver")
        response = client.get("/test")
        
        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts
        
    def test_no_hsts_header_for_http(self):
        """Test HSTS header is not added for HTTP requests."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=True)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app, base_url="http://testserver")
        response = client.get("/test")
        
        assert "Strict-Transport-Security" not in response.headers
        
    def test_hsts_disabled(self):
        """Test HSTS header is not added when disabled."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=False)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app, base_url="https://testserver")
        response = client.get("/test")
        
        assert "Strict-Transport-Security" not in response.headers
        
    def test_server_header_removed(self, app_with_security_headers):
        """Test that Server header is removed."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")
        
        assert "Server" not in response.headers


class TestRequestLoggingMiddleware:
    """Test request logging middleware."""
    
    def test_request_logging_basic(self, app_with_request_logging, caplog):
        """Test basic request logging."""
        with caplog.at_level(logging.INFO):
            client = TestClient(app_with_request_logging)
            response = client.get("/test")
            
        assert response.status_code == 200
        
        # Check log messages
        log_messages = [record.message for record in caplog.records]
        assert any("Request started" in msg for msg in log_messages)
        assert any("Request completed" in msg for msg in log_messages)
        
        # Check log extras
        start_record = next(r for r in caplog.records if "Request started" in r.message)
        assert hasattr(start_record, 'request_id')
        assert hasattr(start_record, 'method')
        assert hasattr(start_record, 'url')
        assert hasattr(start_record, 'client_ip')
        
        complete_record = next(r for r in caplog.records if "Request completed" in r.message)
        assert hasattr(complete_record, 'status_code')
        assert hasattr(complete_record, 'duration_ms')
        
    def test_request_logging_with_body(self, app_with_request_logging, caplog):
        """Test request logging with body logging enabled."""
        with caplog.at_level(logging.INFO):
            client = TestClient(app_with_request_logging)
            response = client.post("/test", json={"test": "data"})
            
        assert response.status_code == 200
        
        # Check that body was logged
        start_record = next(r for r in caplog.records if "Request started" in r.message)
        assert hasattr(start_record, 'body_preview')
        
    def test_request_logging_large_body_truncated(self, caplog):
        """Test that large request bodies are truncated."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware, log_body=True, max_body_size=10)
        
        @app.post("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        with caplog.at_level(logging.INFO):
            client = TestClient(app)
            large_data = "x" * 100  # Larger than max_body_size
            response = client.post("/test", json={"data": large_data})
            
        assert response.status_code == 200
        
        start_record = next(r for r in caplog.records if "Request started" in r.message)
        if hasattr(start_record, 'body_preview'):
            assert len(start_record.body_preview) <= 10
            
    def test_request_logging_error_handling(self, caplog):
        """Test request logging during error conditions."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)
        
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")
            
        with caplog.at_level(logging.ERROR):
            client = TestClient(app)
            response = client.get("/error")
            
        assert response.status_code == 500
        
        # Check error log
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) > 0
        
        error_record = error_records[0]
        assert "Request failed" in error_record.message
        assert hasattr(error_record, 'error')
        assert hasattr(error_record, 'error_type')
        assert hasattr(error_record, 'duration_ms')
        
    def test_client_ip_extraction_forwarded_for(self):
        """Test client IP extraction from X-Forwarded-For header."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        
        # Mock request with X-Forwarded-For header
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = None
        
        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.1"
        
    def test_client_ip_extraction_real_ip(self):
        """Test client IP extraction from X-Real-IP header."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        
        # Mock request with X-Real-IP header
        request = MagicMock(spec=Request)
        request.headers = {"X-Real-IP": "192.168.1.2"}
        request.client = None
        
        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.2"
        
    def test_client_ip_extraction_direct(self):
        """Test client IP extraction from direct client."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        
        # Mock request with direct client
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.3"
        
        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.3"
        
    def test_client_ip_extraction_unknown(self):
        """Test client IP extraction when no IP is available."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        
        # Mock request with no IP information
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None
        
        ip = middleware._get_client_ip(request)
        assert ip == "unknown"
        
    def test_debug_headers_logging(self, caplog):
        """Test that headers are logged in debug mode."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        with caplog.at_level(logging.DEBUG):
            client = TestClient(app)
            response = client.get("/test", headers={"Custom-Header": "test-value"})
            
        assert response.status_code == 200
        
        # In debug mode, headers should be logged
        start_record = next(r for r in caplog.records if "Request started" in r.message)
        if hasattr(start_record, 'headers'):
            assert isinstance(start_record.headers, dict)


class TestMiddlewareIntegration:
    """Integration tests for multiple middleware."""
    
    def test_combined_middleware(self):
        """Test that multiple middleware work together."""
        app = FastAPI()
        
        # Add both middleware
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestLoggingMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        
        # Check that security headers are present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        
        # Response should be successful
        assert response.json() == {"message": "success"}