"""Tests for monitoring and observability functionality."""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from fastapi.testclient import TestClient

from src.monitoring import (
    StructuredLogger,
    get_logger,
    check_database_health,
    check_redis_health,
    record_request_metrics,
    record_bot_update,
    record_payment_event,
    record_search_request,
    record_vinted_api_request,
    record_rate_limit_hit,
    get_health_summary,
    get_prometheus_metrics,
    get_metrics_content_type
)
from src.middleware.monitoring import MonitoringMiddleware


class TestStructuredLogger:
    """Test structured logging functionality."""
    
    def test_logger_creation(self):
        """Test logger creation."""
        logger = get_logger("test")
        assert isinstance(logger, StructuredLogger)
        assert logger.logger.name == "test"
    
    @patch('src.monitoring.logging.getLogger')
    def test_info_logging(self, mock_get_logger):
        """Test info logging with context."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        logger = StructuredLogger("test")
        logger.info("Test message", request_id="123", user_id="456")
        
        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        
        assert args[0] == 20  # INFO level
        assert "Test message" in args[1]
        assert "request_id" in kwargs["extra"]
        assert "user_id" in kwargs["extra"]
        assert kwargs["extra"]["request_id"] == "123"
        assert kwargs["extra"]["user_id"] == "456"
    
    @patch('src.monitoring.logging.getLogger')
    def test_error_logging_with_metrics(self, mock_get_logger):
        """Test error logging records metrics."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        logger = StructuredLogger("test")
        
        with patch('src.monitoring.ERROR_COUNT') as mock_counter:
            mock_labels = Mock()
            mock_counter.labels.return_value = mock_labels
            
            logger.error("Test error", error_type="TestError", component="test_component")
            
            mock_counter.labels.assert_called_once_with(
                error_type="TestError", 
                component="test_component"
            )
            mock_labels.inc.assert_called_once()


class TestHealthChecks:
    """Test health check functionality."""
    
    @pytest.mark.asyncio
    async def test_database_health_check_success(self):
        """Test successful database health check."""
        with patch('src.monitoring.get_db_session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_context
            
            mock_result = AsyncMock()
            mock_session_instance.execute.return_value = mock_result
            mock_result.fetchone.return_value = (1,)
            
            result = await check_database_health()
            
            assert result["status"] == "healthy"
            assert "response_time_ms" in result
            assert "timestamp" in result
            assert result["response_time_ms"] >= 0
    
    @pytest.mark.asyncio
    async def test_database_health_check_failure(self):
        """Test failed database health check."""
        with patch('src.monitoring.get_db_session') as mock_session:
            # Mock the context manager to raise an exception
            mock_context = AsyncMock()
            mock_context.__aenter__.side_effect = Exception("Database connection failed")
            mock_session.return_value = mock_context
            
            result = await check_database_health()
            
            assert result["status"] == "unhealthy"
            assert "error" in result
            assert "response_time_ms" in result
            assert result["error"] == "Database connection failed"
    
    @pytest.mark.asyncio
    async def test_redis_health_check_success(self):
        """Test successful Redis health check."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        
        result = await check_redis_health(mock_redis)
        
        assert result["status"] == "healthy"
        assert "response_time_ms" in result
        assert "timestamp" in result
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_health_check_failure(self):
        """Test failed Redis health check."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis connection failed")
        
        result = await check_redis_health(mock_redis)
        
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert result["error"] == "Redis connection failed"


class TestMetricsRecording:
    """Test metrics recording functionality."""
    
    def test_record_request_metrics(self):
        """Test request metrics recording."""
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        
        with patch('src.monitoring.REQUEST_COUNT') as mock_counter, \
             patch('src.monitoring.REQUEST_DURATION') as mock_histogram:
            
            mock_counter_labels = Mock()
            mock_counter.labels.return_value = mock_counter_labels
            
            mock_histogram_labels = Mock()
            mock_histogram.labels.return_value = mock_histogram_labels
            
            record_request_metrics(mock_request, 0.5, 200)
            
            mock_counter.labels.assert_called_once_with(
                method="GET", endpoint="/test", status_code=200
            )
            mock_counter_labels.inc.assert_called_once()
            
            mock_histogram.labels.assert_called_once_with(
                method="GET", endpoint="/test"
            )
            mock_histogram_labels.observe.assert_called_once_with(0.5)
    
    def test_record_bot_update(self):
        """Test bot update metrics recording."""
        with patch('src.monitoring.BOT_UPDATES_TOTAL') as mock_counter:
            mock_labels = Mock()
            mock_counter.labels.return_value = mock_labels
            
            record_bot_update("message", "success")
            
            mock_counter.labels.assert_called_once_with(
                update_type="message", status="success"
            )
            mock_labels.inc.assert_called_once()
    
    def test_record_payment_event(self):
        """Test payment event metrics recording."""
        with patch('src.monitoring.PAYMENT_EVENTS_TOTAL') as mock_counter:
            mock_labels = Mock()
            mock_counter.labels.return_value = mock_labels
            
            record_payment_event("webhook_processed", "success")
            
            mock_counter.labels.assert_called_once_with(
                event_type="webhook_processed", status="success"
            )
            mock_labels.inc.assert_called_once()
    
    def test_record_search_request(self):
        """Test search request metrics recording."""
        with patch('src.monitoring.SEARCH_REQUESTS_TOTAL') as mock_counter:
            mock_labels = Mock()
            mock_counter.labels.return_value = mock_labels
            
            record_search_request("success")
            
            mock_counter.labels.assert_called_once_with(status="success")
            mock_labels.inc.assert_called_once()
    
    def test_record_vinted_api_request(self):
        """Test Vinted API request metrics recording."""
        with patch('src.monitoring.VINTED_API_REQUESTS_TOTAL') as mock_counter, \
             patch('src.monitoring.VINTED_API_DURATION') as mock_histogram:
            
            mock_counter_labels = Mock()
            mock_counter.labels.return_value = mock_counter_labels
            
            mock_histogram_labels = Mock()
            mock_histogram.labels.return_value = mock_histogram_labels
            
            record_vinted_api_request("/search", 200, 1.5)
            
            mock_counter.labels.assert_called_once_with(
                endpoint="/search", status_code=200
            )
            mock_counter_labels.inc.assert_called_once()
            
            mock_histogram.labels.assert_called_once_with(endpoint="/search")
            mock_histogram_labels.observe.assert_called_once_with(1.5)
    
    def test_record_rate_limit_hit(self):
        """Test rate limit hit metrics recording."""
        with patch('src.monitoring.RATE_LIMIT_HITS') as mock_counter:
            mock_labels = Mock()
            mock_counter.labels.return_value = mock_labels
            
            record_rate_limit_hit("/api/search", "user")
            
            mock_counter.labels.assert_called_once_with(
                endpoint="/api/search", client_type="user"
            )
            mock_labels.inc.assert_called_once()


class TestHealthSummary:
    """Test health summary functionality."""
    
    @patch('src.monitoring._metrics_lock')
    @patch('src.monitoring._health_metrics')
    def test_get_health_summary_healthy(self, mock_metrics, mock_lock):
        """Test health summary when all services are healthy."""
        current_time = time.time()
        mock_metrics.__getitem__.side_effect = lambda key: {
            'last_db_check': current_time - 60,  # 1 minute ago
            'last_redis_check': current_time - 30,  # 30 seconds ago
            'db_status': 'healthy',
            'redis_status': 'healthy',
            'error_counts': {},
            'response_times': [0.1, 0.2, 0.15]
        }[key]
        
        summary = get_health_summary()
        
        assert summary['status'] == 'healthy'
        assert summary['database']['status'] == 'healthy'
        assert summary['redis']['status'] == 'healthy'
        assert summary['performance']['avg_response_time_ms'] == 150.0  # (0.1+0.2+0.15)/3 * 1000
        assert summary['performance']['recent_errors'] == 0
    
    @patch('src.monitoring._metrics_lock')
    @patch('src.monitoring._health_metrics')
    def test_get_health_summary_unhealthy(self, mock_metrics, mock_lock):
        """Test health summary when services are unhealthy."""
        current_time = time.time()
        mock_metrics.__getitem__.side_effect = lambda key: {
            'last_db_check': current_time - 400,  # 6+ minutes ago (stale)
            'last_redis_check': current_time - 60,
            'db_status': 'unhealthy',
            'redis_status': 'healthy',
            'error_counts': {'api:error': 5, 'db:timeout': 3},
            'response_times': [0.5, 1.0, 0.8]
        }[key]
        
        summary = get_health_summary()
        
        assert summary['status'] == 'unhealthy'
        assert summary['database']['status'] == 'unhealthy'
        assert summary['performance']['recent_errors'] == 8


class TestPrometheusMetrics:
    """Test Prometheus metrics functionality."""
    
    @patch('src.monitoring.generate_latest')
    def test_get_prometheus_metrics(self, mock_generate):
        """Test Prometheus metrics generation."""
        mock_generate.return_value = b"# HELP test_metric Test metric\ntest_metric 1.0\n"
        
        result = get_prometheus_metrics()
        
        assert result == "# HELP test_metric Test metric\ntest_metric 1.0\n"
        mock_generate.assert_called_once()
    
    def test_get_metrics_content_type(self):
        """Test metrics content type."""
        content_type = get_metrics_content_type()
        assert "text/plain" in content_type


class TestMonitoringMiddleware:
    """Test monitoring middleware functionality."""
    
    @pytest.mark.asyncio
    async def test_monitoring_middleware_success(self):
        """Test monitoring middleware with successful request."""
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-agent"}
        mock_request.state = Mock()
        mock_request.state.request_id = "test-123"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "100"}
        
        async def mock_call_next(request):
            return mock_response
        
        middleware = MonitoringMiddleware(app=None)
        
        with patch('src.middleware.monitoring.record_request_metrics') as mock_record, \
             patch('src.middleware.monitoring.logger') as mock_logger:
            
            result = await middleware.dispatch(mock_request, mock_call_next)
            
            assert result == mock_response
            mock_record.assert_called_once()
            
            # Check that info was called twice (start and completion)
            assert mock_logger.info.call_count == 2
    
    @pytest.mark.asyncio
    async def test_monitoring_middleware_error(self):
        """Test monitoring middleware with request error."""
        mock_request = Mock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/error"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-agent"}
        mock_request.state = Mock()
        mock_request.state.request_id = "test-456"
        
        async def mock_call_next(request):
            raise ValueError("Test error")
        
        middleware = MonitoringMiddleware(app=None)
        
        with patch('src.middleware.monitoring.record_request_metrics') as mock_record, \
             patch('src.middleware.monitoring.logger') as mock_logger:
            
            with pytest.raises(ValueError):
                await middleware.dispatch(mock_request, mock_call_next)
            
            # Should record metrics even for failed requests
            mock_record.assert_called_once()
            
            # Should log error
            mock_logger.error.assert_called_once()


class TestMonitoringEndpoints:
    """Test monitoring endpoints integration."""
    
    def test_prometheus_metrics_function(self):
        """Test Prometheus metrics function directly."""
        with patch('src.monitoring.generate_latest') as mock_generate:
            mock_generate.return_value = b"test_metric 1.0"
            
            result = get_prometheus_metrics()
            
            assert result == "test_metric 1.0"
            mock_generate.assert_called_once()
    
    def test_health_summary_function(self):
        """Test health summary function directly."""
        with patch('src.monitoring._metrics_lock'), \
             patch('src.monitoring._health_metrics') as mock_metrics:
            
            current_time = time.time()
            mock_metrics.__getitem__.side_effect = lambda key: {
                'last_db_check': current_time - 60,
                'last_redis_check': current_time - 30,
                'db_status': 'healthy',
                'redis_status': 'healthy',
                'error_counts': {},
                'response_times': [0.1, 0.2]
            }[key]
            
            summary = get_health_summary()
            
            assert summary['status'] == 'healthy'
            assert 'database' in summary
            assert 'redis' in summary
            assert 'performance' in summary