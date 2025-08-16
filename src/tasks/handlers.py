"""Task handlers for background processing."""

import logging
from typing import Dict, Any, List

from tasks.queue import TaskQueue
from tasks.crawl_handlers import register_crawl_handlers
from tasks.notification_handlers import register_notification_handlers

logger = logging.getLogger(__name__)


def register_all_handlers(queue: TaskQueue) -> None:
    """
    Register all task handlers with the queue.
    
    Args:
        queue: TaskQueue instance to register handlers with
    """
    logger.info("Registering task handlers...")
    
    # Register crawling handlers
    register_crawl_handlers(queue)
    
    # Register notification handlers  
    register_notification_handlers(queue)
    
    logger.info("All task handlers registered successfully")


# Example task handlers for testing
async def example_test_task(message: str, delay: float = 0) -> str:
    """
    Test task for queue functionality.
    
    Args:
        message: Test message
        delay: Optional delay in seconds
        
    Returns:
        Processed message
    """
    import asyncio
    
    logger.info(f"Processing test task: {message}")
    
    if delay > 0:
        await asyncio.sleep(delay)
    
    result = f"Processed: {message}"
    logger.info(f"Test task completed: {result}")
    
    return result


async def failing_task(should_fail: bool = True) -> str:
    """
    Task that fails for testing retry logic.
    
    Args:
        should_fail: Whether the task should fail
        
    Returns:
        Success message
        
    Raises:
        RuntimeError: If should_fail is True
    """
    logger.info(f"Running failing task (should_fail={should_fail})")
    
    if should_fail:
        raise RuntimeError("Task intentionally failed for testing")
    
    return "Task succeeded"


def register_test_handlers(queue: TaskQueue) -> None:
    """Register test handlers for development and testing."""
    queue.register_handler("test_task", example_test_task)
    queue.register_handler("failing_task", failing_task)
    
    logger.info("Test handlers registered")