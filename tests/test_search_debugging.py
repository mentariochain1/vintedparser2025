"""Tests for search debugging and metrics infrastructure."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from bot.services.search_debugger import (
    SearchDebugger, SearchStage, SearchErrorType, SearchContext, SearchError
)
from bot.services.search_metrics import SearchMetrics, SearchMetric


class TestSearchDebugger:
    """Test search debugging functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.debugger = SearchDebugger()

    def test_create_correlation_id(self):
        """Test correlation ID generation."""
        correlation_id = self.debugger.create_correlation_id()
        
        assert isinstance(correlation_id, str)
        assert len(correlation_id) == 12
        
        # Should generate unique IDs
        another_id = self.debugger.create_correlation_id()
        assert correlation_id != another_id

    def test_start_search_debug(self):
        """Test starting search debug tracking."""
        correlation_id = self.debugger.start_search_debug(
            user_id=12345,
            query="test query",
            item_count=10,
            chat_id=67890,
            message_id=111
        )
        
        assert correlation_id in self.debugger._active_searches
        
        context = self.debugger._active_searches[correlation_id]
        assert context.user_id == 12345
        assert context.query == "test query"
        assert context.item_count == 10
        assert context.chat_id == 67890
        assert context.message_id == 111
        assert context.current_stage == SearchStage.INITIATED

    def test_log_stage_completion(self):
        """Test logging stage completion."""
        correlation_id = self.debugger.start_search_debug(
            user_id=12345,
            query="test",
            item_count=5,
            chat_id=67890
        )
        
        self.debugger.log_stage_completion(
            correlation_id=correlation_id,
            stage=SearchStage.VALIDATED,
            duration_ms=150.5,
            details={"validation_result": "success"}
        )
        
        context = self.debugger._active_searches[correlation_id]
        assert context.current_stage == SearchStage.VALIDATED
        assert SearchStage.VALIDATED.value in context.stages_completed
        assert context.metrics["validated_duration_ms"] == 150.5

    def test_log_api_call(self):
        """Test logging API calls."""
        correlation_id = self.debugger.start_search_debug(
            user_id=12345,
            query="test",
            item_count=5,
            chat_id=67890
        )
        
        self.debugger.log_api_call(
            correlation_id=correlation_id,
            service="vinted",
            endpoint="/search",
            method="GET",
            params={"query": "test"},
            response_status=200,
            response_time=0.5
        )
        
        context = self.debugger._active_searches[correlation_id]
        assert len(context.api_calls) == 1
        
        api_call = context.api_calls[0]
        assert api_call["service"] == "vinted"
        assert api_call["endpoint"] == "/search"
        assert api_call["response_status"] == 200

    def test_log_search_error(self):
        """Test logging search errors."""
        correlation_id = self.debugger.start_search_debug(
            user_id=12345,
            query="test",
            item_count=5,
            chat_id=67890
        )
        
        test_exception = ValueError("Test error")
        
        self.debugger.log_search_error(
            correlation_id=correlation_id,
            error_type=SearchErrorType.VALIDATION_ERROR,
            message="Test validation error",
            stage=SearchStage.VALIDATED,
            details={"field": "query"},
            exception=test_exception
        )
        
        context = self.debugger._active_searches[correlation_id]
        assert len(context.errors) == 1
        
        error = context.errors[0]
        assert error["error_type"] == SearchErrorType.VALIDATION_ERROR.value
        assert error["message"] == "Test validation error"
        assert error["stage"] == SearchStage.VALIDATED.value

    def test_complete_search_debug(self):
        """Test completing search debug tracking."""
        correlation_id = self.debugger.start_search_debug(
            user_id=12345,
            query="test",
            item_count=5,
            chat_id=67890
        )
        
        # Simulate some processing time
        import time
        time.sleep(0.01)
        
        context = self.debugger.complete_search_debug(
            correlation_id=correlation_id,
            success=True,
            final_stage=SearchStage.COMPLETED,
            results_count=3
        )
        
        assert context is not None
        assert context.current_stage == SearchStage.COMPLETED
        assert context.completed_at is not None
        assert context.metrics["results_count"] == 3
        assert "total_duration_ms" in context.metrics
        
        # Should be moved to history
        assert correlation_id not in self.debugger._active_searches
        assert len(self.debugger._search_history) == 1

    def test_get_search_statistics(self):
        """Test getting search statistics."""
        # Create some test searches
        for i in range(5):
            correlation_id = self.debugger.start_search_debug(
                user_id=12345 + i,
                query=f"test {i}",
                item_count=5,
                chat_id=67890
            )
            
            if i < 3:  # 3 successful
                self.debugger.complete_search_debug(
                    correlation_id=correlation_id,
                    success=True,
                    final_stage=SearchStage.COMPLETED
                )
            else:  # 2 failed
                self.debugger.log_search_error(
                    correlation_id=correlation_id,
                    error_type=SearchErrorType.VINTED_API_ERROR,
                    message="API error",
                    stage=SearchStage.VINTED_SEARCH
                )
                self.debugger.complete_search_debug(
                    correlation_id=correlation_id,
                    success=False,
                    final_stage=SearchStage.FAILED
                )
        
        stats = self.debugger.get_search_statistics()
        
        assert stats["active_searches"] == 0
        assert stats["total_history"] == 5
        assert stats["recent_successes"] == 3
        assert stats["recent_errors"] == 2
        assert stats["recent_success_rate"] == 60.0

    @pytest.mark.asyncio
    async def test_health_check_search_flow(self):
        """Test search flow health check."""
        health = await self.debugger.health_check_search_flow()
        
        assert "status" in health
        assert "checks" in health
        assert "active_searches" in health["checks"]
        assert "stuck_searches" in health["checks"]
        assert "error_rate" in health["checks"]


class TestSearchMetrics:
    """Test search metrics functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = SearchMetrics()

    def test_start_search_operation(self):
        """Test starting search operation tracking."""
        correlation_id = "test123"
        
        self.metrics.start_search_operation(
            correlation_id=correlation_id,
            user_id=12345,
            query="test query",
            item_count=10,
            user_type="premium"
        )
        
        assert correlation_id in self.metrics._active_searches
        
        metric = self.metrics._active_searches[correlation_id]
        assert metric.user_id == 12345
        assert metric.query == "test query"
        assert metric.item_count == 10
        assert metric.user_type == "premium"
        assert metric.status == "active"

    def test_record_stage_operations(self):
        """Test recording stage start and completion."""
        correlation_id = "test123"
        
        self.metrics.start_search_operation(
            correlation_id=correlation_id,
            user_id=12345,
            query="test",
            item_count=5
        )
        
        # Start stage
        self.metrics.record_stage_start(
            correlation_id=correlation_id,
            stage_name="validation",
            details={"input_length": 4}
        )
        
        assert len(self.metrics._stage_metrics[correlation_id]) == 1
        stage_metric = self.metrics._stage_metrics[correlation_id][0]
        assert stage_metric.stage_name == "validation"
        assert stage_metric.status == "active"
        
        # Complete stage
        self.metrics.record_stage_completion(
            correlation_id=correlation_id,
            stage_name="validation",
            status="success"
        )
        
        assert stage_metric.status == "success"
        assert stage_metric.completed_at is not None
        assert stage_metric.duration_ms is not None

    def test_record_api_call(self):
        """Test recording API calls."""
        correlation_id = "test123"
        
        self.metrics.start_search_operation(
            correlation_id=correlation_id,
            user_id=12345,
            query="test",
            item_count=5
        )
        
        self.metrics.record_api_call(
            correlation_id=correlation_id,
            service="vinted",
            endpoint="/search",
            status="success"
        )
        
        metric = self.metrics._active_searches[correlation_id]
        assert metric.api_calls_count == 1

    def test_record_search_error(self):
        """Test recording search errors."""
        correlation_id = "test123"
        
        self.metrics.start_search_operation(
            correlation_id=correlation_id,
            user_id=12345,
            query="test",
            item_count=5
        )
        
        self.metrics.record_search_error(
            correlation_id=correlation_id,
            error_type="validation_error",
            stage="validation"
        )
        
        metric = self.metrics._active_searches[correlation_id]
        assert metric.errors_count == 1

    def test_complete_search_operation(self):
        """Test completing search operation."""
        correlation_id = "test123"
        
        self.metrics.start_search_operation(
            correlation_id=correlation_id,
            user_id=12345,
            query="test",
            item_count=5
        )
        
        # Simulate some processing time
        import time
        time.sleep(0.01)
        
        completed_metric = self.metrics.complete_search_operation(
            correlation_id=correlation_id,
            status="success",
            results_count=3
        )
        
        assert completed_metric is not None
        assert completed_metric.status == "success"
        assert completed_metric.results_count == 3
        assert completed_metric.duration_ms is not None
        assert completed_metric.completed_at is not None
        
        # Should be moved to recent searches
        assert correlation_id not in self.metrics._active_searches
        assert len(self.metrics._recent_searches) == 1

    def test_get_performance_summary(self):
        """Test getting performance summary."""
        # Create some test operations
        for i in range(10):
            correlation_id = f"test{i}"
            self.metrics.start_search_operation(
                correlation_id=correlation_id,
                user_id=12345 + i,
                query=f"test {i}",
                item_count=5
            )
            
            # Complete with different statuses
            status = "success" if i < 8 else "error"
            self.metrics.complete_search_operation(
                correlation_id=correlation_id,
                status=status,
                results_count=3 if status == "success" else None
            )
        
        summary = self.metrics.get_performance_summary()
        
        assert summary["status"] in ["healthy", "degraded", "unhealthy"]
        assert summary["recent_searches_analyzed"] == 10
        assert summary["success_rate_percent"] == 80.0
        assert "average_duration_ms" in summary
        assert "searches_with_errors" in summary

    def test_get_search_metrics(self):
        """Test getting metrics for specific search."""
        correlation_id = "test123"
        
        self.metrics.start_search_operation(
            correlation_id=correlation_id,
            user_id=12345,
            query="test query",
            item_count=5
        )
        
        self.metrics.record_stage_start(correlation_id, "validation")
        self.metrics.record_stage_completion(correlation_id, "validation", "success")
        
        metrics_data = self.metrics.get_search_metrics(correlation_id)
        
        assert metrics_data is not None
        assert metrics_data["correlation_id"] == correlation_id
        assert metrics_data["user_id"] == 12345
        assert metrics_data["query"] == "test query"
        assert len(metrics_data["stages"]) == 1
        assert metrics_data["stages"][0]["stage_name"] == "validation"

    def test_cleanup_old_data(self):
        """Test cleaning up old data."""
        # Add some old user sessions
        old_time = datetime.utcnow() - timedelta(hours=25)
        self.metrics._user_sessions[12345] = old_time
        self.metrics._user_sessions[12346] = datetime.utcnow()
        
        assert len(self.metrics._user_sessions) == 2
        
        self.metrics.cleanup_old_data(max_age_hours=24)
        
        # Should remove old session but keep recent one
        assert len(self.metrics._user_sessions) == 1
        assert 12346 in self.metrics._user_sessions
        assert 12345 not in self.metrics._user_sessions


@pytest.mark.asyncio
async def test_integration_debugger_and_metrics():
    """Test integration between debugger and metrics."""
    debugger = SearchDebugger()
    metrics = SearchMetrics()
    
    # Start tracking in both systems
    correlation_id = debugger.start_search_debug(
        user_id=12345,
        query="integration test",
        item_count=10,
        chat_id=67890
    )
    
    metrics.start_search_operation(
        correlation_id=correlation_id,
        user_id=12345,
        query="integration test",
        item_count=10
    )
    
    # Log some operations
    debugger.log_stage_completion(correlation_id, SearchStage.VALIDATED)
    metrics.record_stage_start(correlation_id, "validation")
    metrics.record_stage_completion(correlation_id, "validation", "success")
    
    debugger.log_api_call(
        correlation_id=correlation_id,
        service="vinted",
        endpoint="/search",
        response_status=200
    )
    metrics.record_api_call(correlation_id, "vinted", "/search", "success")
    
    # Complete both
    debugger_context = debugger.complete_search_debug(
        correlation_id=correlation_id,
        success=True,
        results_count=5
    )
    
    metrics_result = metrics.complete_search_operation(
        correlation_id=correlation_id,
        status="success",
        results_count=5
    )
    
    # Verify both systems tracked the operation
    assert debugger_context is not None
    assert metrics_result is not None
    assert debugger_context.correlation_id == correlation_id
    assert metrics_result.correlation_id == correlation_id
    
    # Verify data consistency
    assert debugger_context.metrics["results_count"] == 5
    assert metrics_result.results_count == 5