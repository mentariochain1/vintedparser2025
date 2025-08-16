"""Main application entry point."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from aiogram.types import Update
import redis.asyncio as redis

from config import settings
from db import close_database, health_check as db_health_check, init_database
from bot.bot import create_bot, create_dispatcher, setup_bot_webhook, remove_bot_webhook, close_bot
from middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RequestIDMiddleware,
    MonitoringMiddleware,
    rate_limit
)
from monitoring import (
    get_prometheus_metrics,
    get_metrics_content_type,
    check_database_health,
    check_redis_health,
    get_health_summary,
    get_logger
)
from error_handlers import error_handler, GracefulDegradation
from exceptions import (
    VintedBotError, WebhookError, InvalidWebhookSignatureError,
    PaymentError, ConfigurationError, CircuitBreakerError,
    ServiceUnavailableError, RateLimitError
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = get_logger(__name__)

# Global Redis connection for rate limiting
redis_client: redis.Redis = None


class CustomHTTPException(HTTPException):
    """Custom HTTP exception with additional context."""
    
    def __init__(self, status_code: int, detail: str, request_id: str = None):
        super().__init__(status_code=status_code, detail=detail)
        self.request_id = request_id




@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    global redis_client
    
    logger.info(f"Starting Vinted Parser Bot in {settings.environment} mode")

    # Initialize Redis connection
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    # Initialize database (PostgreSQL only)
    db_initialized = False
    sqlalchemy_initialized = False

    try:
        await init_database()
        logger.info("Database initialized successfully")
        db_initialized = True
        sqlalchemy_initialized = True
        app.state.use_asyncpg = False
        app.state.use_rest_api = False
    except Exception as e:
        logger.warning(f"SQLAlchemy database initialization failed: {e}")
        # Fallback to direct asyncpg pool only
        try:
            from db.asyncpg_adapter import init_asyncpg_database
            await init_asyncpg_database()
            logger.info("Asyncpg database adapter initialized successfully")
            db_initialized = True
            app.state.use_asyncpg = True
            app.state.use_rest_api = False
        except Exception as asyncpg_error:
            logger.warning(f"Asyncpg database initialization failed: {asyncpg_error}")
            app.state.use_asyncpg = False
            logger.warning("Database unavailable, continuing without database")
    
    app.state.db_available = db_initialized

    # Check database availability
    if not db_initialized:
        logger.warning("Database unavailable, using fallback mode")
    
    # Initialize bot
    bot = create_bot()
    # Use full handlers; DB is now plain PostgreSQL
    dp = create_dispatcher(use_fallback=False)

    app.state.bot = bot
    app.state.dp = dp
    app.state.redis = redis_client

    try:
        await setup_bot_webhook(bot)
        logger.info("Bot webhook configured successfully")
    except Exception as e:
        logger.error(f"Failed to configure bot webhook: {e}")
        raise

    yield

    logger.info("Shutting down Vinted Parser Bot")

    # Shutdown bot
    try:
        await remove_bot_webhook(bot)
        await close_bot(bot)
        logger.info("Bot shutdown completed")
    except Exception as e:
        logger.error(f"Error shutting down bot: {e}")

    # Close Redis connection
    try:
        await redis_client.close()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")

    # Close database
    try:
        if hasattr(app.state, 'use_asyncpg') and app.state.use_asyncpg:
            from db.asyncpg_adapter import close_asyncpg_database
            await close_asyncpg_database()
        
        # Always try to close SQLAlchemy if it was initialized
        try:
            await close_database()
        except Exception as sqlalchemy_error:
            logger.debug(f"SQLAlchemy close error (expected if not initialized): {sqlalchemy_error}")
            
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Vinted Parser Bot",
        description="Telegram bot for parsing Vinted listings that ship to Austria",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Add security middleware first
    app.add_middleware(SecurityHeadersMiddleware, strict_transport_security=settings.is_production)
    
    # Add trusted host middleware
    allowed_hosts = ["*"] if settings.debug else [
        settings.webhook_domain.replace("https://", "").replace("http://", "")
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [settings.webhook_domain],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
    )

    # Add request ID middleware
    app.add_middleware(RequestIDMiddleware)
    
    # Add monitoring middleware
    app.add_middleware(MonitoringMiddleware)
    
    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware, log_body=settings.debug, max_body_size=1024)
    
    # Add rate limiting middleware (will be configured after Redis is available)
    @app.middleware("http")
    async def add_rate_limiting(request: Request, call_next):
        """Add rate limiting middleware after Redis is available."""
        if hasattr(app.state, 'redis') and app.state.redis:
            # Create rate limit middleware instance
            rate_limiter = RateLimitMiddleware(
                app=None,  # Not used in direct call
                redis_client=app.state.redis,
                default_max_requests=60,
                default_window_seconds=60
            )
            return await rate_limiter.dispatch(request, call_next)
        else:
            # Skip rate limiting if Redis is not available
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
                from db.asyncpg_adapter import db_adapter
                db_status = await db_adapter.health_check()
            except Exception as e:
                db_status = {"status": "unhealthy", "error": str(e)}
        else:
            db_status = await check_database_health()
        
        # Check Redis
        redis_status = {"status": "unknown"}
        try:
            if redis_client:
                redis_status = await check_redis_health(redis_client)
            else:
                redis_status = {"status": "unhealthy", "error": "Redis client not initialized"}
        except Exception as e:
            redis_status = {"status": "unhealthy", "error": str(e)}
        
        # Check payment service
        payment_status = {"status": "unknown"}
        try:
            from bot.services.payment_service import PaymentService
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
        from bot.services.search_debugger import search_debugger
        from bot.services.search_metrics import search_metrics
        from bot.services.vinted_service import VintedService
        
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
        from bot.services.search_metrics import search_metrics
        
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
        from bot.services.search_debugger import search_debugger
        from bot.services.search_metrics import search_metrics
        
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
    @rate_limit(max_requests=60, window_seconds=60, key_suffix="telegram_webhook")
    async def webhook_handler(request: Request) -> dict[str, str]:
        """Handle incoming webhook updates from Telegram."""
        request_id = getattr(request.state, 'request_id', 'unknown')

        # Skip webhook signature validation in development mode
        if settings.debug:
            logger.info("Skipping webhook signature validation in debug mode")
        else:
            # Verify webhook secret using secure validation
            from security.session_manager import webhook_validator
            from exceptions import InvalidWebhookSignatureError
            
            secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if not secret_token:
                client_ip = request.client.host if request.client else 'unknown'
                logger.warning(
                    f"Missing webhook secret token from {client_ip}",
                    request_id=request_id,
                    client_ip=client_ip
                )
                raise InvalidWebhookSignatureError("Missing secret token")
            
            # Get raw body for signature verification
            body = await request.body()
            
            if not webhook_validator.validate_telegram_webhook(body, secret_token):
                client_ip = request.client.host if request.client else 'unknown'
                logger.warning(
                    f"Invalid webhook signature from {client_ip}",
                    request_id=request_id,
                    client_ip=client_ip
                )
                raise InvalidWebhookSignatureError("Invalid webhook signature")

        try:
            # Parse update data
            update_data = await request.json()
            
            # Validate Telegram update structure
            from validation import validate_telegram_update
            from exceptions import ValidationError
            
            try:
                validated_update = validate_telegram_update(update_data)
            except ValidationError as ve:
                logger.warning(
                    f"Invalid Telegram update structure: {ve}",
                    request_id=request_id,
                    error_type=type(ve).__name__
                )
                raise CustomHTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid update structure",
                    request_id=request_id
                )
            
        except Exception as e:
            logger.warning(
                f"Invalid JSON in webhook request: {e}",
                request_id=request_id,
                error_type=type(e).__name__
            )
            raise CustomHTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON payload",
                request_id=request_id
            )

        # Debug: Log raw update data in a compact, safe way
        try:
            keys = list(update_data.keys())
            logger.info(f"DEBUG: Raw update data keys: {keys}")
            if 'callback_query' in update_data:
                cq = update_data['callback_query']
                logger.info(
                    "DEBUG: Raw callback_query detected",
                    callback_data=cq.get('data'),
                    from_id=cq.get('from', {}).get('id'),
                    message_id=((cq.get('message') or {}).get('message_id'))
                )
        except Exception:
            pass

        try:
            update = Update(**update_data)

            # Extract user_id if available
            user_id = None
            if update.message and update.message.from_user:
                user_id = update.message.from_user.id
            elif update.callback_query and update.callback_query.from_user:
                user_id = update.callback_query.from_user.id
            
            # Store user_id in request state for monitoring
            if user_id:
                request.state.user_id = user_id

            # Log update processing
            update_type = "unknown"
            if update.message:
                update_type = "message"
            elif update.callback_query:
                update_type = "callback_query"
                logger.info(f"DEBUG: Callback query detected - data: {update.callback_query.data}")
            elif update.inline_query:
                update_type = "inline_query"
            
            logger.info(
                "Processing Telegram update",
                request_id=request_id,
                user_id=user_id,
                update_id=update.update_id,
                update_type=update_type
            )

            # Process update
            await app.state.dp.feed_update(app.state.bot, update)
            
            # Record successful bot update
            from monitoring import record_bot_update
            record_bot_update(update_type, "success")

            return {"status": "ok", "request_id": request_id}

        except Exception as e:
            # Record failed bot update
            from monitoring import record_bot_update
            record_bot_update(update_type if 'update_type' in locals() else "unknown", "error")
            
            # Add more detailed error logging
            import traceback
            logger.error(
                f"Error processing webhook update: {e}",
                request_id=request_id,
                error_type=type(e).__name__,
                component="webhook_handler",
                traceback=traceback.format_exc()
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
        from bot.services.payment_service import PaymentService
        from db.base import get_db_session
        
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
                    from monitoring import record_payment_event
                    record_payment_event("webhook_processed", "success")
                    
                    logger.info(
                        f"YooKassa webhook processed successfully: {message}",
                        request_id=request_id
                    )
                    return {"status": "ok", "message": message, "request_id": request_id}
                else:
                    # Record failed payment event
                    from monitoring import record_payment_event
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
            from monitoring import record_payment_event
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