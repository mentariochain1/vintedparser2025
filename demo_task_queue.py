#!/usr/bin/env python3
"""
Demo script to show the Redis-based async task queue in action.

This script demonstrates:
1. Creating a task queue
2. Registering handlers
3. Enqueueing tasks
4. Starting workers
5. Processing tasks with retry logic
6. Getting queue statistics
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, 'src')

from tasks.queue import TaskQueue, TaskStatus
from tasks.handlers import register_test_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def demo_task_queue():
    """Demonstrate the task queue functionality."""
    logger.info("Starting task queue demo...")
    
    # Create task queue (using in-memory Redis for demo)
    queue = TaskQueue(redis_url="redis://localhost:6379/15", queue_name="demo")
    
    try:
        # Connect to Redis
        await queue.connect()
        logger.info("Connected to Redis")
        
        # Register test handlers
        register_test_handlers(queue)
        logger.info("Registered task handlers")
        
        # Enqueue some test tasks
        task_ids = []
        
        # Regular task
        task_id1 = await queue.enqueue("test_task", "Hello World!", delay=0.5)
        task_ids.append(task_id1)
        logger.info(f"Enqueued task 1: {task_id1}")
        
        # Task with higher priority
        task_id2 = await queue.enqueue("test_task", "Priority task", priority=10)
        task_ids.append(task_id2)
        logger.info(f"Enqueued priority task: {task_id2}")
        
        # Scheduled task (5 seconds from now)
        future_time = datetime.utcnow() + timedelta(seconds=5)
        task_id3 = await queue.enqueue(
            "test_task", 
            "Scheduled task", 
            scheduled_at=future_time
        )
        task_ids.append(task_id3)
        logger.info(f"Enqueued scheduled task: {task_id3}")
        
        # Task that will fail and retry
        task_id4 = await queue.enqueue(
            "failing_task", 
            should_fail=True,
            max_retries=2,
            retry_delay=1.0
        )
        task_ids.append(task_id4)
        logger.info(f"Enqueued failing task: {task_id4}")
        
        # Show initial queue stats
        stats = await queue.get_queue_stats()
        logger.info(f"Initial queue stats: {stats}")
        
        # Start workers
        logger.info("Starting workers...")
        await queue.start_workers(num_workers=2)
        
        # Let tasks process for a while
        logger.info("Processing tasks for 10 seconds...")
        await asyncio.sleep(10)
        
        # Check results
        logger.info("Checking task results...")
        for task_id in task_ids:
            result = await queue.get_task_result(task_id)
            if result:
                logger.info(f"Task {task_id}: {result.status} - {result.result or result.error}")
            else:
                logger.info(f"Task {task_id}: No result found")
        
        # Final queue stats
        final_stats = await queue.get_queue_stats()
        logger.info(f"Final queue stats: {final_stats}")
        
        # Stop workers
        logger.info("Stopping workers...")
        await queue.stop_workers()
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise
    finally:
        # Clean up
        try:
            await queue.clear_queue()
            await queue.disconnect()
            logger.info("Cleaned up and disconnected")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(demo_task_queue())
        logger.info("Demo completed successfully!")
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)