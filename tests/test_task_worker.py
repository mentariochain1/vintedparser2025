"""Tests for the task worker process."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tasks.worker import TaskWorker
from src.tasks.queue import TaskQueue


@pytest.fixture
def mock_task_queue():
    """Mock TaskQueue instance."""
    mock = AsyncMock(spec=TaskQueue)
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.start_workers = AsyncMock()
    mock.stop_workers = AsyncMock()
    mock.get_queue_stats = AsyncMock(return_value={
        'queue_name': 'test',
        'pending': 0,
        'processing': 0,
        'scheduled': 0,
        'status_counts': {},
        'total_results': 0,
    })
    return mock


class TestTaskWorker:
    """Test cases for TaskWorker."""

    def test_init_default_workers(self):
        """Test worker initialization with default worker count."""
        worker = TaskWorker()
        assert worker.num_workers >= 1
        assert worker.num_workers <= 4

    def test_init_custom_workers(self):
        """Test worker initialization with custom worker count."""
        worker = TaskWorker(num_workers=8)
        assert worker.num_workers == 8

    async def test_get_stats(self, mock_task_queue):
        """Test getting worker statistics."""
        with patch('src.tasks.worker.task_queue', mock_task_queue):
            worker = TaskWorker()
            worker.queue = mock_task_queue
            
            stats = await worker.get_stats()
            
            assert stats['queue_name'] == 'test'
            mock_task_queue.get_queue_stats.assert_called_once()

    async def test_shutdown(self, mock_task_queue):
        """Test worker shutdown."""
        with patch('src.tasks.worker.task_queue', mock_task_queue):
            worker = TaskWorker()
            worker.queue = mock_task_queue
            
            await worker.shutdown()
            
            mock_task_queue.stop_workers.assert_called_once()
            mock_task_queue.disconnect.assert_called_once()

    async def test_signal_handler(self):
        """Test signal handler sets shutdown event."""
        worker = TaskWorker()
        
        # Initially not set
        assert not worker._shutdown_event.is_set()
        
        # Signal handler should set the event
        worker._signal_handler()
        assert worker._shutdown_event.is_set()

    @patch('src.tasks.worker.register_all_handlers')
    async def test_start_and_shutdown_cycle(self, mock_register, mock_task_queue):
        """Test complete start and shutdown cycle."""
        with patch('src.tasks.worker.task_queue', mock_task_queue):
            worker = TaskWorker(num_workers=2)
            
            # Mock the shutdown event to be set immediately
            worker._shutdown_event.set()
            
            # Start should complete quickly due to immediate shutdown
            await worker.start()
            
            # Verify all setup calls were made
            mock_task_queue.connect.assert_called_once()
            mock_register.assert_called_once_with(mock_task_queue)
            mock_task_queue.start_workers.assert_called_once_with(2)
            mock_task_queue.stop_workers.assert_called_once()
            mock_task_queue.disconnect.assert_called_once()

    @patch('src.tasks.worker.register_all_handlers')
    async def test_start_with_exception(self, mock_register, mock_task_queue):
        """Test worker start with exception during setup."""
        mock_task_queue.connect.side_effect = Exception("Connection failed")
        
        with patch('src.tasks.worker.task_queue', mock_task_queue):
            worker = TaskWorker()
            
            with pytest.raises(Exception, match="Connection failed"):
                await worker.start()
            
            # Shutdown should still be called
            mock_task_queue.stop_workers.assert_called_once()
            mock_task_queue.disconnect.assert_called_once()

    @patch('src.tasks.worker.register_all_handlers')
    async def test_start_with_shutdown_exception(self, mock_register, mock_task_queue):
        """Test worker shutdown with exception."""
        mock_task_queue.stop_workers.side_effect = Exception("Shutdown failed")
        
        with patch('src.tasks.worker.task_queue', mock_task_queue):
            worker = TaskWorker()
            worker._shutdown_event.set()  # Immediate shutdown
            
            # Should not raise exception despite shutdown error
            await worker.start()
            
            # Both shutdown methods should be called
            mock_task_queue.stop_workers.assert_called_once()
            mock_task_queue.disconnect.assert_called_once()


class TestWorkerMain:
    """Test cases for worker main function."""

    @patch('src.tasks.worker.TaskWorker')
    @patch('logging.basicConfig')
    async def test_main_success(self, mock_logging, mock_worker_class):
        """Test successful main execution."""
        mock_worker = AsyncMock()
        mock_worker_class.return_value = mock_worker
        
        from src.tasks.worker import main
        
        # Mock the worker to complete immediately
        mock_worker.start = AsyncMock()
        
        await main()
        
        mock_logging.assert_called_once()
        mock_worker_class.assert_called_once()
        mock_worker.start.assert_called_once()

    @patch('src.tasks.worker.TaskWorker')
    @patch('logging.basicConfig')
    async def test_main_with_exception(self, mock_logging, mock_worker_class):
        """Test main execution with exception."""
        mock_worker = AsyncMock()
        mock_worker_class.return_value = mock_worker
        mock_worker.start.side_effect = Exception("Worker failed")
        
        from src.tasks.worker import main
        
        # Should exit with code 1 when worker fails
        with pytest.raises(SystemExit) as exc_info:
            await main()
        
        assert exc_info.value.code == 1

    @patch('src.tasks.worker.TaskWorker')
    @patch('logging.basicConfig')
    async def test_main_keyboard_interrupt(self, mock_logging, mock_worker_class):
        """Test main execution with keyboard interrupt."""
        mock_worker = AsyncMock()
        mock_worker_class.return_value = mock_worker
        mock_worker.start.side_effect = KeyboardInterrupt()
        
        from src.tasks.worker import main
        
        # Should handle KeyboardInterrupt gracefully
        await main()
        
        mock_worker.start.assert_called_once()


@pytest.mark.integration
class TestWorkerIntegration:
    """Integration tests for worker process."""

    @pytest.mark.skip(reason="Requires Redis server")
    async def test_worker_with_real_queue(self):
        """Test worker with real task queue."""
        from src.tasks.queue import TaskQueue
        from src.tasks.handlers import register_test_handlers
        
        # Use test database
        queue = TaskQueue(redis_url="redis://localhost:6379/15", queue_name="test_worker")
        
        try:
            await queue.connect()
            await queue.clear_queue()
            
            register_test_handlers(queue)
            
            # Create worker
            worker = TaskWorker(num_workers=1)
            worker.queue = queue
            
            # Enqueue a test task
            task_id = await queue.enqueue("test_task", "worker_test", delay=0.1)
            
            # Start worker for a short time
            worker_task = asyncio.create_task(worker.start())
            
            # Let it process for a bit
            await asyncio.sleep(0.5)
            
            # Signal shutdown
            worker._signal_handler()
            
            # Wait for worker to complete
            await worker_task
            
            # Check that task was processed
            result = await queue.get_task_result(task_id)
            assert result is not None
            # Task might still be running or completed
            
        finally:
            await queue.clear_queue()
            await queue.disconnect()