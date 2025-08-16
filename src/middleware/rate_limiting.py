"""Rate limiting middleware using Redis."""

import time
import logging
from typing import Callable, Optional
from functools import wraps

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting middleware."""
    
    def __init__(
        self,
        app,
        redis_client: redis.Redis,
        default_max_requests: int = 60,
        default_window_seconds: int = 60,
        key_prefix: str = "rate_limit"
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        self.key_prefix = key_prefix
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to requests."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz"]:
            return await call_next(request)
            
        # Get client identifier
        client_ip = self._get_client_ip(request)
        
        # Check if rate limiting should be applied
        rate_limit_config = getattr(request.state, "rate_limit_config", None)
        if rate_limit_config:
            max_requests = rate_limit_config.get("max_requests", self.default_max_requests)
            window_seconds = rate_limit_config.get("window_seconds", self.default_window_seconds)
            key_suffix = rate_limit_config.get("key_suffix", request.url.path)
        else:
            max_requests = self.default_max_requests
            window_seconds = self.default_window_seconds
            key_suffix = request.url.path
            
        # Create rate limit key
        rate_limit_key = f"{self.key_prefix}:{client_ip}:{key_suffix}"
        
        # Check rate limit
        try:
            is_allowed, remaining, reset_time = await self._check_rate_limit(
                rate_limit_key, max_requests, window_seconds
            )
            
            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "client_ip": client_ip,
                        "path": request.url.path,
                        "rate_limit_key": rate_limit_key,
                        "max_requests": max_requests,
                        "window_seconds": window_seconds
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": str(remaining),
                        "X-RateLimit-Reset": str(reset_time),
                        "Retry-After": str(window_seconds)
                    }
                )
                
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Allow request on Redis failure
            
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        try:
            is_allowed, remaining, reset_time = await self._check_rate_limit(
                rate_limit_key, max_requests, window_seconds, increment=False
            )
            
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            
        except Exception as e:
            logger.error(f"Failed to add rate limit headers: {e}")
            
        return response
        
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
        
    async def _check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        increment: bool = True
    ) -> tuple[bool, int, int]:
        """
        Check rate limit using sliding window counter.
        
        Returns:
            tuple: (is_allowed, remaining_requests, reset_timestamp)
        """
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Use Redis pipeline for atomic operations
        async with self.redis_client.pipeline() as pipe:
            # Remove expired entries
            await pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            await pipe.zcard(key)
            
            if increment:
                # Add current request
                await pipe.zadd(key, {str(current_time): current_time})
                
            # Set expiration
            await pipe.expire(key, window_seconds)
            
            results = await pipe.execute()
        
        current_count = results[1]
        if increment:
            current_count += 1
            
        is_allowed = current_count <= max_requests
        remaining = max(0, max_requests - current_count)
        reset_time = current_time + window_seconds
        
        return is_allowed, remaining, reset_time


def rate_limit(
    max_requests: int,
    window_seconds: int = 60,
    key_suffix: Optional[str] = None
):
    """
    Decorator to apply rate limiting to specific endpoints.
    
    Args:
        max_requests: Maximum requests allowed in the window
        window_seconds: Time window in seconds
        key_suffix: Optional suffix for the rate limit key
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the request object in args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
                    
            if request:
                # Set rate limit configuration on request state
                request.state.rate_limit_config = {
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                    "key_suffix": key_suffix or func.__name__
                }
                
            return await func(*args, **kwargs)
        return wrapper
    return decorator