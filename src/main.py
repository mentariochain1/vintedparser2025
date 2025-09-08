"""Main application entry point for Vinted Parser Bot."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Final

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from aiogram.types import Update
import redis.asyncio as redis

from .config import settings
from .db import close_database, init_database
from .bot.bot import create_bot, create_dispatcher, setup_bot_webhook, remove_bot_webhook, close_bot
from .middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RequestIDMiddleware,
    MonitoringMiddleware,
    rate_limit
)
from .monitoring import (
    get_prometheus_metrics,
    get_metrics_content_type,
    check_database_health,
    check_redis_health,
    get_health_summary,
    get_logger
)
from .error_handlers import error_handler
from .exceptions import (
    VintedBotError, WebhookError, InvalidWebhookSignatureError,
    PaymentError, ConfigurationError, CircuitBreakerError,
    ServiceUnavailableError, RateLimitError, ValidationError
)
from .security.session_manager import webhook_validator, input_sanitizer

# Constants
DEFAULT_TIMEOUT: Final[int] = 30
MAX_REQUEST_SIZE: Final[int] = 1024 * 1024  # 1MB
HEALTH_CHECK_TIMEOUT: Final[int] = 10

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8") if settings.is_production else logging.NullHandler(),
    ]
)

# Configure SQLAlchemy logging to avoid request_id formatting errors
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.setLevel(logging.WARNING)  # Reduce SQLAlchemy logging noise
logger = get_logger(__name__)

# Global Redis connection pool (lazy initialization)
_redis_client: redis.Redis | None = None


class CustomHTTPException(HTTPException):
    """Custom HTTP exception with additional context."""

    def __init__(self, status_code: int, detail: str, request_id: str | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.request_id = request_id


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client with connection pooling."""
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_size,
                retry_on_timeout=True,
                socket_timeout=DEFAULT_TIMEOUT,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
            await _redis_client.ping()
            logger.info("Redis connection pool established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client

    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        finally:
            _redis_client = None




@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager with proper resource management."""

    logger.info(f"Starting Vinted Parser Bot in {settings.environment} mode")

    # Initialize Redis with connection pooling
    redis_client = None
    try:
        redis_client = await get_redis_client()
        app.state.redis = redis_client
        logger.info("Redis connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        if settings.is_production:
            raise  # Fail fast in production
        logger.warning("Continuing without Redis (development mode)")

    # Initialize database with proper error handling
    db_initialized = False
    try:
        await init_database()
        db_initialized = True
        app.state.db_available = True
        app.state.use_asyncpg = False
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Primary database initialization failed: {e}")

        # Try fallback database adapter
        if not settings.is_production:
            try:
                from src.db.asyncpg_adapter import init_asyncpg_database
                await init_asyncpg_database()
                db_initialized = True
                app.state.db_available = True
                app.state.use_asyncpg = True
                logger.info("Fallback database adapter initialized")
            except Exception as fallback_error:
                logger.error(f"Fallback database initialization also failed: {fallback_error}")
                app.state.db_available = False
                app.state.use_asyncpg = False
        else:
            app.state.db_available = False
            app.state.use_asyncpg = False

    if not db_initialized:
        if settings.is_production:
            raise RuntimeError("Database initialization failed in production")
        logger.warning("Running in degraded mode without database")

    # Initialize Telegram bot with proper error handling
    bot = None
    dp = None
    try:
        bot = create_bot()
        dp = create_dispatcher(use_fallback=not db_initialized)
        app.state.bot = bot
        app.state.dp = dp

        # Setup webhook with retry logic
        await setup_bot_webhook(bot)
        logger.info("Bot webhook configured successfully")

    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        if settings.is_production:
            raise
        logger.warning("Bot initialization failed, continuing in limited mode")

    # Store application state for health checks
    app.state.startup_time = time.time()
    app.state.version = "0.1.0"

    logger.info("Application startup completed")

    try:
        yield
    finally:
        logger.info("Initiating graceful shutdown")

        # Shutdown bot first (most critical)
        if bot:
            try:
                await remove_bot_webhook(bot)
                await close_bot(bot)
                logger.info("Bot shutdown completed")
            except Exception as e:
                logger.error(f"Error during bot shutdown: {e}")

        # Close Redis connections
        if redis_client:
            try:
                await close_redis_client()
            except Exception as e:
                logger.error(f"Error during Redis shutdown: {e}")

        # Close database connections
        try:
            if hasattr(app.state, 'use_asyncpg') and app.state.use_asyncpg:
                from src.db.asyncpg_adapter import close_asyncpg_database
                await close_asyncpg_database()

            await close_database()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error during database shutdown: {e}")

        logger.info("Application shutdown completed")

def create_app() -> FastAPI:
    """Create and configure FastAPI application with security hardening."""

    # Configure OpenAPI documentation access
    docs_url = "/docs" if settings.is_development else None
    redoc_url = "/redoc" if settings.is_development else None
    openapi_url = "/openapi.json" if settings.is_development else None

    app = FastAPI(
        title="Vinted Parser Bot",
        description="Telegram bot for parsing Vinted listings that ship to Austria",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.is_development,  # Only debug in development
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Security: Configure trusted hosts
    if settings.is_production:
        allowed_hosts = [settings.webhook_domain.replace("https://", "").replace("http://", "")]
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    else:
        # Allow all hosts in development, but still use middleware for consistency
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

    # Security: Add security headers
    if settings.enable_security_headers:
        app.add_middleware(
            SecurityHeadersMiddleware,
            strict_transport_security=settings.is_production
        )

    # CORS configuration with security
    if settings.enable_cors:
        cors_origins = ["*"] if settings.is_development else [settings.webhook_domain]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-Requested-With",
                "X-Telegram-Bot-Api-Secret-Token",
                "X-Yookassa-Signature",
                "X-Yookassa-Timestamp"
            ],
            expose_headers=[
                "X-Request-ID",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset"
            ],
            max_age=86400,  # 24 hours
        )

    # Request processing middleware (order matters)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware,
                      log_body=settings.is_development,
                      max_body_size=MAX_REQUEST_SIZE)

    # Monitoring (must be after request ID for proper correlation)
    if settings.enable_prometheus:
        app.add_middleware(MonitoringMiddleware)

    # Rate limiting middleware (async configuration)
    @app.middleware("http")
    async def rate_limiting_middleware(request: Request, call_next):
        """Configure rate limiting with Redis when available."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz", "/metrics"]:
            return await call_next(request)

        # Apply rate limiting if Redis is available
        if hasattr(app.state, 'redis') and app.state.redis:
            try:
                rate_limiter = RateLimitMiddleware(
                    redis_client=app.state.redis,
                    default_max_requests=settings.rate_limit_requests,
                    default_window_seconds=settings.rate_limit_window
                )
                return await rate_limiter.dispatch(request, call_next)
            except Exception as e:
                logger.warning(f"Rate limiting failed, proceeding without: {e}")
                return await call_next(request)
        else:
            # No Redis available, skip rate limiting
            return await call_next(request)

    # Global exception handlers
    @app.exception_handler(VintedBotError)
    async def vinted_bot_exception_handler(request: Request, exc: VintedBotError):
        """Handle custom VintedBotError exceptions."""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Log the error with context
        error_handler.log_error(exc, {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        })
        
        return error_handler.create_error_response(
            exc, 
            request_id=request_id,
            include_details=settings.debug
        )

    @app.exception_handler(CustomHTTPException)
    async def custom_http_exception_handler(request: Request, exc: CustomHTTPException):
        request_id = getattr(request.state, 'request_id', 'unknown')
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "request_id": request_id,
                "timestamp": str(time.time())
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, 'request_id', 'unknown')
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "request_id": request_id,
                "timestamp": str(time.time())
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Log the error with context
        error_handler.log_error(exc, {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        })
        
        # Return user-friendly error message
        user_message = error_handler.get_user_friendly_message(exc)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": user_message,
                "error_type": type(exc).__name__,
                "request_id": request_id,
                "timestamp": str(time.time())
            }
        )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "environment": settings.environment,
            "timestamp": str(time.time())
        }

    @app.get("/healthz")
    async def detailed_health_check(request: Request) -> dict[str, str | dict]:
        """Detailed health check endpoint including database and Redis status."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        # Check database
        if hasattr(app.state, 'use_asyncpg') and app.state.use_asyncpg:
            try:
                from src.db.asyncpg_adapter import db_adapter
                db_status = await db_adapter.health_check()
            except Exception as e:
                db_status = {"status": "unhealthy", "error": str(e)}
        else:
            try:
                # Ensure database is initialized before health check
                if not hasattr(app.state, 'db_available') or not app.state.db_available:
                    # Try to initialize database if not already done
                    from src.db.base import init_database
                    await init_database()
                    app.state.db_available = True

                db_status = await check_database_health()
            except Exception as e:
                db_status = {"status": "unhealthy", "error": str(e)}
        
        # Check Redis
        redis_status = {"status": "unknown"}
        try:
            if hasattr(app.state, 'redis') and app.state.redis:
                redis_status = await check_redis_health(app.state.redis)
            else:
                redis_status = {"status": "unhealthy", "error": "Redis client not initialized"}
        except Exception as e:
            redis_status = {"status": "unhealthy", "error": str(e)}
        
        # Check payment service
        payment_status = {"status": "unknown"}
        try:
            from src.bot.services.payment_service import PaymentService
            payment_service = PaymentService()
            is_healthy = await payment_service.health_check()
            payment_status = {"status": "healthy" if is_healthy else "unhealthy"}
        except Exception as e:
            payment_status = {"status": "unhealthy", "error": str(e)}

        overall_status = "healthy" if all(
            service["status"] == "healthy" 
            for service in [db_status, redis_status, payment_status]
        ) else "unhealthy"

        return {
            "status": overall_status,
            "environment": settings.environment,
            "database": db_status,
            "redis": redis_status,
            "payment_service": payment_status,
            "version": "0.1.0",
            "request_id": request_id,
            "timestamp": str(time.time())
        }

    @app.get("/metrics")
    async def prometheus_metrics():
        """Prometheus metrics endpoint."""
        from fastapi import Response
        
        metrics_data = get_prometheus_metrics()
        return Response(
            content=metrics_data,
            media_type=get_metrics_content_type()
        )

    @app.get("/health/summary")
    async def health_summary(request: Request) -> dict[str, str | dict]:
        """Get overall health summary with performance metrics."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        summary = get_health_summary()
        summary['request_id'] = request_id
        summary['environment'] = settings.environment
        summary['version'] = "0.1.0"
        
        return summary

    @app.get("/health/search")
    async def search_health_check(request: Request) -> dict[str, str | dict]:
        """Comprehensive health check for search functionality."""
        from src.bot.services.search_debugger import search_debugger
        from src.bot.services.search_metrics import search_metrics
        from src.bot.services.vinted_service import VintedService
        
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        health_status = {
            "status": "healthy",
            "request_id": request_id,
            "timestamp": str(time.time()),
            "checks": {}
        }
        
        # Check search debugger health
        try:
            debugger_health = await search_debugger.health_check_search_flow()
            health_status["checks"]["search_debugger"] = debugger_health
        except Exception as e:
            health_status["checks"]["search_debugger"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check search metrics
        try:
            metrics_summary = search_metrics.get_performance_summary()
            health_status["checks"]["search_metrics"] = metrics_summary
        except Exception as e:
            health_status["checks"]["search_metrics"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check Vinted service
        try:
            vinted_service = VintedService()
            vinted_healthy = await vinted_service.health_check()
            health_status["checks"]["vinted_service"] = {
                "status": "healthy" if vinted_healthy else "unhealthy",
                "service_available": vinted_healthy
            }
        except Exception as e:
            health_status["checks"]["vinted_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Determine overall status
        check_statuses = []
        for check in health_status["checks"].values():
            if isinstance(check, dict) and "status" in check:
                check_statuses.append(check["status"])
        
        if "unhealthy" in check_statuses:
            health_status["status"] = "unhealthy"
        elif "warning" in check_statuses or "degraded" in check_statuses:
            health_status["status"] = "degraded"
        
        return health_status

    @app.get("/health/search/metrics")
    async def search_metrics_endpoint(request: Request) -> dict[str, str | dict]:
        """Get detailed search metrics and statistics."""
        from src.bot.services.search_metrics import search_metrics
        
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        try:
            performance_summary = search_metrics.get_performance_summary()
            hourly_stats = search_metrics.get_hourly_statistics(hours=24)
            
            return {
                "request_id": request_id,
                "timestamp": str(time.time()),
                "performance_summary": performance_summary,
                "hourly_statistics": hourly_stats
            }
        except Exception as e:
            logger.error(f"Error getting search metrics: {e}", request_id=request_id)
            return {
                "request_id": request_id,
                "timestamp": str(time.time()),
                "error": str(e),
                "status": "error"
            }

    @app.get("/health/search/debug/{correlation_id}")
    async def search_debug_info(correlation_id: str, request: Request) -> dict[str, str | dict]:
        """Get debug information for a specific search operation."""
        from src.bot.services.search_debugger import search_debugger
        from src.bot.services.search_metrics import search_metrics
        
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        try:
            debug_data = search_debugger.export_search_debug_data(correlation_id)
            metrics_data = search_metrics.get_search_metrics(correlation_id)
            
            if not debug_data and not metrics_data:
                raise CustomHTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Search operation {correlation_id} not found",
                    request_id=request_id
                )
            
            return {
                "request_id": request_id,
                "timestamp": str(time.time()),
                "correlation_id": correlation_id,
                "debug_data": debug_data,
                "metrics_data": metrics_data
            }
        except CustomHTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting search debug info: {e}", 
                        request_id=request_id, correlation_id=correlation_id)
            raise CustomHTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve debug information",
                request_id=request_id
            )

    @app.post(settings.webhook_path)
    async def telegram_webhook_handler(request: Request) -> dict[str, str]:
        """Handle incoming webhook updates from Telegram with security validation."""
        request_id = getattr(request.state, 'request_id', 'unknown')

        # Security: Validate request size
        content_length = request.headers.get("content-length", "0")
        try:
            if int(content_length) > MAX_REQUEST_SIZE:
                logger.warning(
                    "Request too large",
                    request_id=request_id,
                    content_length=content_length
                )
                raise CustomHTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request payload too large",
                    request_id=request_id
                )
        except ValueError:
            pass  # Invalid content-length header, continue

        # Security: Webhook signature validation (always enabled in production)
        if settings.is_production or not settings.is_development:
            secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if not secret_token:
                client_ip = request.client.host if request.client else 'unknown'
                logger.warning(
                    "Missing webhook secret token",
                    request_id=request_id,
                    client_ip=client_ip
                )
                raise InvalidWebhookSignatureError("Missing secret token")

            # Get raw body for signature verification
            try:
                body = await request.body()
            except Exception as e:
                logger.error(
                    "Failed to read request body",
                    request_id=request_id,
                    error=str(e)
                )
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request body",
                    request_id=request_id
                )

            if not webhook_validator.validate_telegram_webhook(body, secret_token):
                client_ip = request.client.host if request.client else 'unknown'
                logger.warning(
                    "Invalid webhook signature",
                    request_id=request_id,
                    client_ip=client_ip
                )
                raise InvalidWebhookSignatureError("Invalid webhook signature")

            # Reset body for JSON parsing
            request._body = body

        # Parse and validate update data
        try:
            update_data = await request.json()
        except Exception as e:
            logger.warning(
                "Invalid JSON in webhook request",
                request_id=request_id,
                error=str(e)
            )
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
                request_id=request_id
            )

        # Security: Validate Telegram update structure
        from .validation import validate_telegram_update

        try:
            validated_update = validate_telegram_update(update_data)
        except ValidationError as ve:
            logger.warning(
                "Invalid Telegram update structure",
                request_id=request_id,
                error=str(ve)
            )
            raise CustomHTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid update structure",
                request_id=request_id
            )

        # Process the update
        try:
            update = Update(**update_data)

            # Extract user information for monitoring
            user_id = None
            chat_id = None
            update_type = "unknown"

            if update.message:
                update_type = "message"
                if update.message.from_user:
                    user_id = update.message.from_user.id
                chat_id = update.message.chat.id
            elif update.callback_query:
                update_type = "callback_query"
                if update.callback_query.from_user:
                    user_id = update.callback_query.from_user.id
                if update.callback_query.message:
                    chat_id = update.callback_query.message.chat.id
            elif update.inline_query:
                update_type = "inline_query"
                if update.inline_query.from_user:
                    user_id = update.inline_query.from_user.id

            # Store user context for monitoring
            request.state.user_id = user_id
            request.state.chat_id = chat_id
            request.state.update_type = update_type

            # Log update processing (without sensitive data)
            logger.info(
                "Processing Telegram update",
                request_id=request_id,
                user_id=user_id,
                chat_id=chat_id,
                update_id=update.update_id,
                update_type=update_type
            )

            # Process update through bot dispatcher
            if hasattr(app.state, 'dp') and app.state.dp:
                await app.state.dp.feed_update(app.state.bot, update)

                # Record successful processing
                from .monitoring import record_bot_update
                record_bot_update(update_type, "success")

                return {"status": "ok", "request_id": request_id}
            else:
                logger.error("Bot dispatcher not available", request_id=request_id)
                raise CustomHTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Bot service temporarily unavailable",
                    request_id=request_id
                )

        except CustomHTTPException:
            raise
        except Exception as e:
            # Record failed bot update
            from .monitoring import record_bot_update
            record_bot_update(update_type, "error")

            # Log error with context
            logger.error(
                "Error processing webhook update",
                request_id=request_id,
                user_id=user_id,
                update_type=update_type,
                error_type=type(e).__name__,
                error=str(e)
            )

            raise CustomHTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process update",
                request_id=request_id
            )

    @app.post("/payment/webhook")
    @rate_limit(max_requests=30, window_seconds=60, key_suffix="payment_webhook")
    async def yookassa_webhook_handler(request: Request) -> dict[str, str]:
        """Handle YooKassa payment webhook notifications."""
        from .bot.services.payment_service import PaymentService
        from .db.base import get_db_session
        
        request_id = getattr(request.state, 'request_id', 'unknown')

        try:
            # Extract webhook data
            signature = request.headers.get("Yookassa-Signature", "")
            timestamp = request.headers.get("Yookassa-Timestamp", "")
            payload = await request.body()

            if not signature or not timestamp:
                logger.warning(
                    "Missing required headers in YooKassa webhook",
                    request_id=request_id
                )
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required headers",
                    request_id=request_id
                )

            logger.info(
                "Processing YooKassa webhook",
                request_id=request_id,
                timestamp=timestamp,
                payload_size=len(payload)
            )

            payment_service = PaymentService()

            async with get_db_session() as session:
                success, message = await payment_service.process_webhook(
                    session=session,
                    payload=payload,
                    signature=signature,
                    timestamp=timestamp
                )

                if success:
                    # Record successful payment event
                    from .monitoring import record_payment_event
                    record_payment_event("webhook_processed", "success")
                    
                    logger.info(
                        f"YooKassa webhook processed successfully: {message}",
                        request_id=request_id
                    )
                    return {"status": "ok", "message": message, "request_id": request_id}
                else:
                    # Record failed payment event
                    from .monitoring import record_payment_event
                    record_payment_event("webhook_processed", "failed")
                    
                    logger.warning(
                        f"YooKassa webhook processing failed: {message}",
                        request_id=request_id
                    )
                    raise CustomHTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=message,
                        request_id=request_id
                    )

        except CustomHTTPException:
            raise
        except Exception as e:
            # Record error payment event
            from .monitoring import record_payment_event
            record_payment_event("webhook_processed", "error")
            
            logger.error(
                f"Error processing YooKassa webhook: {e}",
                request_id=request_id,
                error_type=type(e).__name__,
                component="payment_webhook"
            )
            raise CustomHTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process webhook",
                request_id=request_id
            )

    @app.get("/payment/success")
    async def payment_success_page(request: Request) -> dict[str, str]:
        """Payment success redirect page."""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.info(
            "Payment success page accessed",
            request_id=request_id
        )
        
        return {
            "status": "success",
            "message": "Payment completed successfully! You can close this page and return to Telegram.",
            "request_id": request_id,
            "timestamp": str(time.time())
        }

    return app

app =create_app ()

def main ()->None :
    """Main entry point for CLI."""
    import uvicorn

    uvicorn .run (
    "src.main:app",
    host ="0.0.0.0",
    port =8000 ,
    reload =not settings .is_production ,
    log_level =settings .log_level .lower (),
    )

if __name__ =="__main__":
    main ()