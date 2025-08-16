"""Tests for task handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tasks.handlers import (
    register_all_handlers,
    register_test_handlers,
    example_test_task,
    failing_task,
)
from src.tasks.queue import TaskQueue


@pytest.fixture
def mock_queue():
    """Mock TaskQueue instance."""
    mock = MagicMock(spec=TaskQueue)
    mock.register_handler = MagicMock()
    return mock


class TestTaskHandlers:
    """Test cases for task handlers."""

    async def test_test_task_success(self):
        """Test successful test task execution."""
        result = await example_test_task("hello world", delay=0)
        
        assert result == "Processed: hello world"

    async def test_test_task_with_delay(self):
        """Test test task with delay."""
        import time
        
        start_time = time.time()
        result = await example_test_task("delayed", delay=0.1)
        end_time = time.time()
        
        assert result == "Processed: delayed"
        assert end_time - start_time >= 0.1

    async def test_failing_task_success(self):
        """Test failing task when it should succeed."""
        result = await failing_task(should_fail=False)
        
        assert result == "Task succeeded"

    async def test_failing_task_failure(self):
        """Test failing task when it should fail."""
        with pytest.raises(RuntimeError, match="Task intentionally failed"):
            await failing_task(should_fail=True)

    async def test_failing_task_default_behavior(self):
        """Test failing task with default behavior (should fail)."""
        with pytest.raises(RuntimeError, match="Task intentionally failed"):
            await failing_task()

    def test_register_test_handlers(self, mock_queue):
        """Test registering test handlers."""
        register_test_handlers(mock_queue)
        
        # Should register both test handlers
        assert mock_queue.register_handler.call_count == 2
        
        # Check that correct handlers were registered
        calls = mock_queue.register_handler.call_args_list
        handler_names = [call[0][0] for call in calls]
        
        assert "test_task" in handler_names
        assert "failing_task" in handler_names

    async def test_register_all_handlers(self, mock_queue):
        """Test registering all handlers."""
        from unittest.mock import patch
        
        with patch('src.tasks.handlers.register_crawl_handlers') as mock_crawl:
            with patch('src.tasks.handlers.register_notification_handlers') as mock_notif:
                register_all_handlers(mock_queue)
                
                mock_crawl.assert_called_once_with(mock_queue)
                mock_notif.assert_called_once_with(mock_queue)


class TestHandlerRegistration:
    """Test cases for handler registration functions."""

    def test_crawl_handlers_placeholder(self, mock_queue):
        """Test crawl handlers registration placeholder."""
        from src.tasks.crawl_handlers import register_crawl_handlers
        
        # Should not raise exception (placeholder implementation)
        register_crawl_handlers(mock_queue)

    def test_notification_handlers_placeholder(self, mock_queue):
        """Test notification handlers registration placeholder."""
        from src.tasks.notification_handlers import register_notification_handlers
        
        # Should not raise exception (placeholder implementation)
        register_notification_handlers(mock_queue)


class TestHandlerExecution:
    """Test cases for handler execution scenarios."""

    async def test_handler_with_various_args(self):
        """Test handler with different argument types."""
        # Test with string
        result1 = await example_test_task("string_arg")
        assert "string_arg" in result1
        
        # Test with number (converted to string)
        result2 = await example_test_task(123)
        assert "123" in result2
        
        # Test with complex object
        result3 = await example_test_task({"key": "value"})
        assert "key" in result3

    async def test_handler_error_propagation(self):
        """Test that handler errors are properly propagated."""
        # Test that exceptions bubble up correctly
        with pytest.raises(RuntimeError):
            await failing_task(should_fail=True)

    async def test_handler_async_behavior(self):
        """Test that handlers are properly async."""
        import asyncio
        
        # Test concurrent execution
        tasks = [
            example_test_task(f"task_{i}", delay=0.05)
            for i in range(3)
        ]
        
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        # Should complete in roughly the delay time (concurrent execution)
        # rather than 3x the delay time (sequential execution)
        assert end_time - start_time < 0.2  # Much less than 3 * 0.05 + overhead
        
        # All tasks should complete
        assert len(results) == 3
        for i, result in enumerate(results):
            assert f"task_{i}" in result


@pytest.mark.integration
class TestHandlerIntegration:
    """Integration tests for handlers with task queue."""

    @pytest.mark.skip(reason="Requires Redis server")
    async def test_handlers_with_real_queue(self):
        """Test handlers with real task queue."""
        from src.tasks.queue import TaskQueue
        
        queue = TaskQueue(redis_url="redis://localhost:6379/15", queue_name="test_handlers")
        
        try:
            await queue.connect()
            await queue.clear_queue()
            
            # Register test handlers
            register_test_handlers(queue)
            
            # Start workers
            await queue.start_workers(num_workers=1)
            
            # Enqueue test tasks
            task_id1 = await queue.enqueue("test_task", "integration_test")
            task_id2 = await queue.enqueue("failing_task", should_fail=False)
            
            # Wait for processing
            import asyncio
            await asyncio.sleep(1)
            
            # Check results
            result1 = await queue.get_task_result(task_id1)
            result2 = await queue.get_task_result(task_id2)
            
            assert result1 is not None
            assert result2 is not None
            
            # Stop workers
            await queue.stop_workers()
            
        finally:
            await queue.clear_queue()
            await queue.disconnect()