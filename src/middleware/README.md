# Middleware Documentation

This package contains custom middleware for the FastAPI application, providing rate limiting, security headers, request logging, and request ID tracking.

## Components

### RateLimitMiddleware

Redis-based rate limiting middleware that implements sliding window rate limiting.

**Features:**
- Sliding window rate limiting using Redis sorted sets
- Per-IP rate limiting with configurable limits
- Automatic rate limit headers in responses
- Graceful fallback when Redis is unavailable
- Support for custom rate limits per endpoint via decorator

**Usage:**
```python
from src.middleware import RateLimitMiddleware, rate_limit

# Add to FastAPI app
app.add_middleware(
    RateLimitMiddleware,
    redis_client=redis_client,
    default_max_requests=60,
    default_window_seconds=60
)

# Use decorator for custom limits
@app.get("/api/endpoint")
@rate_limit(max_requests=10, window_seconds=60)
async def limited_endpoint():
    return {"message": "success"}
```

### SecurityHeadersMiddleware

Adds security headers to all responses to protect against common web vulnerabilities.

**Headers Added:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
- `Strict-Transport-Security` (HTTPS only)

**Usage:**
```python
from src.middleware import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=True)
```

### RequestLoggingMiddleware

Enhanced request logging with structured logging format.

**Features:**
- Structured logging with consistent fields
- Request/response timing
- Client IP extraction from proxy headers
- Optional request body logging
- Error logging with stack traces

**Usage:**
```python
from src.middleware import RequestLoggingMiddleware

app.add_middleware(
    RequestLoggingMiddleware,
    log_body=False,  # Enable for debugging
    max_body_size=1024
)
```

### RequestIDMiddleware

Adds unique request IDs to each request for tracing and debugging.

**Features:**
- Generates UUID4 request IDs
- Accepts existing request IDs from headers
- Adds request ID to response headers
- Stores request ID in request state for access in handlers

**Usage:**
```python
from src.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware, header_name="X-Request-ID")

# Access in handlers
@app.get("/endpoint")
async def handler(request: Request):
    request_id = request.state.request_id
    return {"request_id": request_id}
```

## Middleware Order

Middleware should be added in the following order for optimal functionality:

1. **SecurityHeadersMiddleware** - Applied first to ensure security headers on all responses
2. **TrustedHostMiddleware** - FastAPI built-in for host validation
3. **CORSMiddleware** - FastAPI built-in for CORS handling
4. **RequestIDMiddleware** - Generate request IDs early
5. **RequestLoggingMiddleware** - Log requests with IDs
6. **RateLimitMiddleware** - Apply rate limiting after logging

## Configuration

All middleware can be configured through environment variables or direct parameters:

```python
# Rate limiting
RATE_LIMIT_DEFAULT_REQUESTS=60
RATE_LIMIT_DEFAULT_WINDOW=60

# Security
SECURITY_HSTS_ENABLED=true

# Logging
LOG_REQUEST_BODIES=false
LOG_MAX_BODY_SIZE=1024
```

## Testing

Each middleware component includes comprehensive unit tests:

- `tests/test_middleware_rate_limiting.py`
- `tests/test_middleware_security.py`
- `tests/test_middleware_request_id.py`
- `tests/test_middleware_simple.py`

Run tests with:
```bash
poetry run pytest tests/test_middleware_*.py -v
```

## Error Handling

All middleware components include proper error handling:

- Rate limiting falls back gracefully when Redis is unavailable
- Security headers are applied even during error conditions
- Request logging captures errors with full context
- Request IDs are preserved through error flows

## Performance Considerations

- Rate limiting uses Redis pipelines for atomic operations
- Security headers are added with minimal overhead
- Request logging is optimized for production use
- Request ID generation uses efficient UUID4 implementation

## Security Notes

- Rate limiting keys include client IP to prevent abuse
- Security headers follow OWASP recommendations
- Request logging masks sensitive data
- All middleware respects proxy headers for IP extraction