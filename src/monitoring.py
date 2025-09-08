"""Monitoring and observability utilities."""

import time
import logging
from typing import Dict, Any, Optional
from collections import defaultdict, Counter
from threading import Lock

import redis.asyncio as redis
from fastapi import Request
from prometheus_client import Counter as PrometheusCounter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from src.db.base import get_db_session
from src.config import settings

# Prometheus metrics
REQUEST_COUNT = PrometheusCounter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

BOT_UPDATES_TOTAL = PrometheusCounter(
    'bot_updates_total',
    'Total bot updates processed',
    ['update_type', 'status']
)

PAYMENT_EVENTS_TOTAL = PrometheusCounter(
    'payment_events_total',
    'Total payment events',
    ['event_type', 'status']
)

SEARCH_REQUESTS_TOTAL = PrometheusCounter(
    'search_requests_total',
    'Total search requests',
    ['status']
)

VINTED_API_REQUESTS_TOTAL = PrometheusCounter(
    'vinted_api_requests_total',
    'Total Vinted API requests',
    ['endpoint', 'status_code']
)

VINTED_API_DURATION = Histogram(
    'vinted_api_request_duration_seconds',
    'Vinted API request duration in seconds',
    ['endpoint']
)

DATABASE_CONNECTIONS = Gauge(
    'database_connections_active',
    'Number of active database connections'
)

REDIS_CONNECTIONS = Gauge(
    'redis_connections_active',
    'Number of active Redis connections'
)

ERROR_COUNT = PrometheusCounter(
    'errors_total',
    'Total errors',
    ['error_type', 'component']
)

RATE_LIMIT_HITS = PrometheusCounter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint', 'client_type']
)

# In-memory metrics for health checks
_metrics_lock = Lock()
_health_metrics = {
    'last_db_check': 0,
    'last_redis_check': 0,
    'db_status': 'unknown',
    'redis_status': 'unknown',
    'error_counts': defaultdict(int),
    'response_times': [],
}


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with structured context."""
        extra = {
            'timestamp': time.time(),
            'environment': settings.environment,
        }
        extra.update(kwargs)
        
        # Format message with context
        if kwargs:
            context_str = ' '.join(f'{k}={v}' for k, v in kwargs.items() if k not in ['request_id', 'user_id'])
            if context_str:
                message = f"{message} {context_str}"
        
        self.logger.log(level, message, extra=extra)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, **kwargs)
        
        # Track error in metrics
        error_type = kwargs.get('error_type', 'unknown')
        component = kwargs.get('component', 'unknown')
        ERROR_COUNT.labels(error_type=error_type, component=component).inc()
        
        with _metrics_lock:
            _health_metrics['error_counts'][f"{component}:{error_type}"] += 1
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance."""
    return StructuredLogger(name)


async def check_database_health() -> Dict[str, Any]:
    """Check database health and update metrics."""
    start_time = time.time()
    
    try:
        async with get_db_session() as session:
            # Simple query to check database connectivity
            result = await session.execute("SELECT 1")
            await result.fetchone()
            
        duration = time.time() - start_time
        status = {
            'status': 'healthy',
            'response_time_ms': round(duration * 1000, 2),
            'timestamp': time.time()
        }
        
        with _metrics_lock:
            _health_metrics['last_db_check'] = time.time()
            _health_metrics['db_status'] = 'healthy'
            
        return status
        
    except Exception as e:
        duration = time.time() - start_time
        status = {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': round(duration * 1000, 2),
            'timestamp': time.time()
        }
        
        with _metrics_lock:
            _health_metrics['last_db_check'] = time.time()
            _health_metrics['db_status'] = 'unhealthy'
            
        return status


async def check_redis_health(redis_client: redis.Redis) -> Dict[str, Any]:
    """Check Redis health and update metrics."""
    start_time = time.time()
    
    try:
        await redis_client.ping()
        
        duration = time.time() - start_time
        status = {
            'status': 'healthy',
            'response_time_ms': round(duration * 1000, 2),
            'timestamp': time.time()
        }
        
        with _metrics_lock:
            _health_metrics['last_redis_check'] = time.time()
            _health_metrics['redis_status'] = 'healthy'
            
        return status
        
    except Exception as e:
        duration = time.time() - start_time
        status = {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': round(duration * 1000, 2),
            'timestamp': time.time()
        }
        
        with _metrics_lock:
            _health_metrics['last_redis_check'] = time.time()
            _health_metrics['redis_status'] = 'unhealthy'
            
        return status


def record_request_metrics(request: Request, response_time: float, status_code: int):
    """Record request metrics for monitoring."""
    method = request.method
    endpoint = request.url.path
    
    # Update Prometheus metrics
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(response_time)
    
    # Update health metrics
    with _metrics_lock:
        _health_metrics['response_times'].append(response_time)
        # Keep only last 1000 response times
        if len(_health_metrics['response_times']) > 1000:
            _health_metrics['response_times'] = _health_metrics['response_times'][-1000:]


def record_bot_update(update_type: str, status: str = 'success'):
    """Record bot update metrics."""
    BOT_UPDATES_TOTAL.labels(update_type=update_type, status=status).inc()


def record_payment_event(event_type: str, status: str = 'success'):
    """Record payment event metrics."""
    PAYMENT_EVENTS_TOTAL.labels(event_type=event_type, status=status).inc()


def record_search_request(status: str = 'success'):
    """Record search request metrics."""
    SEARCH_REQUESTS_TOTAL.labels(status=status).inc()


def record_vinted_api_request(endpoint: str, status_code: int, duration: float):
    """Record Vinted API request metrics."""
    VINTED_API_REQUESTS_TOTAL.labels(endpoint=endpoint, status_code=status_code).inc()
    VINTED_API_DURATION.labels(endpoint=endpoint).observe(duration)


def record_rate_limit_hit(endpoint: str, client_type: str = 'unknown'):
    """Record rate limit hit."""
    RATE_LIMIT_HITS.labels(endpoint=endpoint, client_type=client_type).inc()


def get_health_summary() -> Dict[str, Any]:
    """Get overall health summary."""
    with _metrics_lock:
        current_time = time.time()
        
        # Calculate average response time
        response_times = _health_metrics['response_times']
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Check if health checks are recent (within last 5 minutes)
        db_check_age = current_time - _health_metrics['last_db_check']
        redis_check_age = current_time - _health_metrics['last_redis_check']
        
        db_healthy = _health_metrics['db_status'] == 'healthy' and db_check_age < 300
        redis_healthy = _health_metrics['redis_status'] == 'healthy' and redis_check_age < 300
        
        # Count recent errors (last hour)
        recent_errors = sum(
            count for count in _health_metrics['error_counts'].values()
        )
        
        overall_status = 'healthy' if db_healthy and redis_healthy and recent_errors < 10 else 'degraded'
        if not db_healthy or not redis_healthy:
            overall_status = 'unhealthy'
        
        return {
            'status': overall_status,
            'database': {
                'status': _health_metrics['db_status'],
                'last_check_age_seconds': round(db_check_age, 2)
            },
            'redis': {
                'status': _health_metrics['redis_status'],
                'last_check_age_seconds': round(redis_check_age, 2)
            },
            'performance': {
                'avg_response_time_ms': round(avg_response_time * 1000, 2),
                'recent_errors': recent_errors
            },
            'timestamp': current_time
        }


def get_prometheus_metrics() -> str:
    """Get Prometheus metrics in text format."""
    return generate_latest().decode('utf-8')


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST