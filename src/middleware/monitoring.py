"""Monitoring middleware for request tracking."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.monitoring import record_request_metrics, get_logger

logger = get_logger(__name__)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics and performance."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request metrics and performance."""
        start_time = time.time()
        
        # Get request context
        request_id = getattr(request.state, 'request_id', 'unknown')
        user_id = None
        
        # Try to extract user_id from various sources
        if hasattr(request.state, 'user_id'):
            user_id = request.state.user_id
        elif 'user_id' in request.query_params:
            user_id = request.query_params['user_id']
        
        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            request_id=request_id,
            user_id=user_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else 'unknown',
            user_agent=request.headers.get('user-agent', 'unknown')
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            record_request_metrics(request, duration, response.status_code)
            
            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                request_id=request_id,
                user_id=user_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                response_size=response.headers.get('content-length', 'unknown')
            )
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            duration = time.time() - start_time
            
            # Record error metrics
            record_request_metrics(request, duration, 500)
            
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                request_id=request_id,
                user_id=user_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                error_type=type(e).__name__,
                component='middleware'
            )
            
            # Re-raise the exception
            raise