"""Security middleware for FastAPI application."""

import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    def __init__(self, app, strict_transport_security: bool = True):
        super().__init__(app)
        self.strict_transport_security = strict_transport_security
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy
        csp_directives = [
            "default-src 'none'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # HSTS header (only for HTTPS)
        if self.strict_transport_security and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
            
        # Remove server information
        if "Server" in response.headers:
            del response.headers["Server"]
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced request logging middleware with structured logging."""
    
    def __init__(self, app, log_body: bool = False, max_body_size: int = 1024):
        super().__init__(app)
        self.log_body = log_body
        self.max_body_size = max_body_size
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Extract request details
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        content_length = request.headers.get("content-length", "0")
        
        # Log request start
        log_data = {
            "event": "request_started",
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": str(request.query_params) if request.query_params else None,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "content_length": content_length,
            "headers": dict(request.headers) if logger.isEnabledFor(logging.DEBUG) else None
        }
        
        # Log request body if enabled and not too large
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                content_length_int = int(content_length)
                if content_length_int <= self.max_body_size:
                    body = await request.body()
                    if body:
                        log_data["body_preview"] = body[:self.max_body_size].decode(
                            "utf-8", errors="replace"
                        )
            except Exception as e:
                log_data["body_error"] = str(e)
                
        logger.info("Request started", extra=log_data)
        
        # Process request
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log successful response
            logger.info(
                "Request completed",
                extra={
                    "event": "request_completed",
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "response_size": response.headers.get("content-length", "unknown")
                }
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error response
            logger.error(
                "Request failed",
                extra={
                    "event": "request_failed",
                    "request_id": request_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2)
                },
                exc_info=True
            )
            raise
            
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
            
        # Fallback to direct client IP
        if request.client:
            return request.client.host
            
        return "unknown"