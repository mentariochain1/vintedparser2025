"""Redis-based async task queue implementation."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
import redis.asyncio as redis

from config import settings

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Task execution result."""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class Task:
    """Task definition."""
    id: str
    name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    priority: int = 0  # Higher number = higher priority


class TaskQueue:
    """Redis-based async task queue."""

    def __init__(self, redis_url: str = None, queue_name: str = "default"):
        """
        Initialize task queue.
        
        Args:
            redis_url: Redis connection URL
            queue_name: Name of the task queue
        """
        self.redis_url = redis_url or settings.redis_url
        self.queue_name = queue_name
        self.redis: Optional[redis.Redis] = None
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        
        # Redis keys
        self.queue_key = f"queue:{queue_name}"
        self.processing_key = f"processing:{queue_name}"
        self.results_key = f"results:{queue_name}"
        self.scheduled_key = f"scheduled:{queue_name}"

    async def connect(self) -> None:
        """Connect to Redis."""
        if self.redis is None:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
            )
            # Test connection
            await self.redis.ping()
            logger.info(f"Connected to Redis for queue '{self.queue_name}'")

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info(f"Disconnected from Redis for queue '{self.queue_name}'")

    async def enqueue(
        self,
        task_name: str,
        *args,
        task_id: str = None,
        scheduled_at: datetime = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = None,
        priority: int = 0,
        **kwargs
    ) -> str:
        """
        Enqueue a task for execution.
        
        Args:
            task_name: Name of the task to execute
            *args: Positional arguments for the task
            task_id: Optional task ID (generated if not provided)
            scheduled_at: Optional scheduled execution time
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Task timeout in seconds
            priority: Task priority (higher = more important)
            **kwargs: Keyword arguments for the task
            
        Returns:
            Task ID
        """
        if not self.redis:
            await self.connect()

        task_id = task_id or str(uuid.uuid4())
        
        # Check for duplicate task
        if await self._is_duplicate_task(task_name, args, kwargs):
            logger.info(f"Duplicate task {task_name} detected, skipping")
            return task_id

        task = Task(
            id=task_id,
            name=task_name,
            args=list(args),
            kwargs=kwargs,
            created_at=datetime.utcnow(),
            scheduled_at=scheduled_at,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            priority=priority,
        )

        task_data = json.dumps(asdict(task), default=str)

        if scheduled_at and scheduled_at > datetime.utcnow():
            # Schedule for later execution
            score = scheduled_at.timestamp()
            await self.redis.zadd(self.scheduled_key, {task_data: score})
            logger.info(f"Scheduled task {task_id} ({task_name}) for {scheduled_at}")
        else:
            # Add to priority queue (higher priority first)
            await self.redis.zadd(self.queue_key, {task_data: -priority})
            logger.info(f"Enqueued task {task_id} ({task_name}) with priority {priority}")

        # Store initial result
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )
        await self._store_result(result)

        return task_id

    async def _is_duplicate_task(
        self, 
        task_name: str, 
        args: List[Any], 
        kwargs: Dict[str, Any]
    ) -> bool:
        """Check if a similar task is already queued or processing."""
        # Create a simple hash of the task parameters
        task_hash = f"{task_name}:{hash(str(args) + str(sorted(kwargs.items())))}"
        
        # Use Redis SETNX with short TTL for deduplication
        key = f"dedup:{self.queue_name}:{task_hash}"
        result = await self.redis.set(key, "1", nx=True, ex=120)  # 2 minute TTL
        
        return not result  # True if key already existed (duplicate)

    def register_handler(self, task_name: str, handler: Callable) -> None:
        """
        Register a task handler.
        
        Args:
            task_name: Name of the task
            handler: Async function to handle the task
        """
        self._handlers[task_name] = handler
        logger.info(f"Registered handler for task '{task_name}'")

    async def start_workers(self, num_workers: int = 1) -> None:
        """
        Start worker processes.
        
        Args:
            num_workers: Number of worker processes to start
        """
        if self._running:
            logger.warning("Workers already running")
            return

        if not self.redis:
            await self.connect()

        self._running = True
        
        # Start scheduled task processor
        scheduled_task = asyncio.create_task(self._process_scheduled_tasks())
        self._worker_tasks.append(scheduled_task)
        
        # Start worker tasks
        for i in range(num_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(worker_task)

        logger.info(f"Started {num_workers} workers for queue '{self.queue_name}'")

    async def stop_workers(self) -> None:
        """Stop all worker processes."""
        if not self._running:
            return

        self._running = False

        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        self._worker_tasks.clear()
        logger.info(f"Stopped workers for queue '{self.queue_name}'")

    async def _process_scheduled_tasks(self) -> None:
        """Process scheduled tasks and move them to the main queue."""
        while self._running:
            try:
                now = time.time()
                
                # Get tasks scheduled for now or earlier
                tasks = await self.redis.zrangebyscore(
                    self.scheduled_key, 
                    0, 
                    now, 
                    withscores=True
                )
                
                for task_data, score in tasks:
                    # Move to main queue
                    task = json.loads(task_data)
                    priority = task.get('priority', 0)
                    await self.redis.zadd(self.queue_key, {task_data: -priority})
                    
                    # Remove from scheduled queue
                    await self.redis.zrem(self.scheduled_key, task_data)
                    
                    logger.info(f"Moved scheduled task {task['id']} to main queue")

                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing scheduled tasks: {e}")
                await asyncio.sleep(5)

    async def _worker(self, worker_id: str) -> None:
        """Worker process to execute tasks."""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get next task from queue (blocking pop with timeout)
                result = await self.redis.bzpopmin(self.queue_key, timeout=1)
                
                if not result:
                    continue  # Timeout, try again
                
                queue_name, task_data, priority = result
                task_dict = json.loads(task_data)
                
                # Convert back to Task object
                task = Task(**task_dict)
                task.created_at = datetime.fromisoformat(task.created_at)
                if task.scheduled_at:
                    task.scheduled_at = datetime.fromisoformat(task.scheduled_at)

                # Move to processing queue
                await self.redis.hset(
                    self.processing_key, 
                    task.id, 
                    json.dumps(asdict(task), default=str)
                )

                # Execute task
                await self._execute_task(task, worker_id)

                # Remove from processing queue
                await self.redis.hdel(self.processing_key, task.id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Worker {worker_id} stopped")

    async def _execute_task(self, task: Task, worker_id: str) -> None:
        """Execute a single task."""
        logger.info(f"Worker {worker_id} executing task {task.id} ({task.name})")
        
        # Update task status
        result = TaskResult(
            task_id=task.id,
            status=TaskStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        await self._store_result(result)

        try:
            # Get handler
            handler = self._handlers.get(task.name)
            if not handler:
                raise ValueError(f"No handler registered for task '{task.name}'")

            # Execute with timeout
            if task.timeout:
                task_result = await asyncio.wait_for(
                    handler(*task.args, **task.kwargs),
                    timeout=task.timeout
                )
            else:
                task_result = await handler(*task.args, **task.kwargs)

            # Task completed successfully
            result.status = TaskStatus.COMPLETED
            result.result = task_result
            result.completed_at = datetime.utcnow()
            
            logger.info(f"Task {task.id} completed successfully")

        except asyncio.TimeoutError:
            error_msg = f"Task {task.id} timed out after {task.timeout}s"
            logger.error(error_msg)
            
            result.status = TaskStatus.FAILED
            result.error = error_msg
            result.completed_at = datetime.utcnow()

        except Exception as e:
            error_msg = f"Task {task.id} failed: {str(e)}"
            logger.error(error_msg)
            
            # Check if we should retry
            current_result = await self.get_task_result(task.id)
            retry_count = current_result.retry_count if current_result else 0
            
            if retry_count < task.max_retries:
                # Schedule retry
                retry_count += 1
                delay = task.retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                scheduled_at = datetime.utcnow() + timedelta(seconds=delay)
                
                await self.enqueue(
                    task.name,
                    *task.args,
                    task_id=task.id,
                    scheduled_at=scheduled_at,
                    max_retries=task.max_retries,
                    retry_delay=task.retry_delay,
                    timeout=task.timeout,
                    priority=task.priority,
                    **task.kwargs
                )
                
                result.status = TaskStatus.RETRYING
                result.retry_count = retry_count
                result.error = error_msg
                
                logger.info(f"Scheduled retry {retry_count}/{task.max_retries} for task {task.id} in {delay}s")
            else:
                result.status = TaskStatus.FAILED
                result.error = error_msg
                result.completed_at = datetime.utcnow()

        await self._store_result(result)

    async def _store_result(self, result: TaskResult) -> None:
        """Store task result in Redis."""
        result_data = json.dumps(asdict(result), default=str)
        await self.redis.hset(self.results_key, result.task_id, result_data)
        
        # Set expiration for completed/failed tasks (24 hours)
        if result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            await self.redis.expire(f"{self.results_key}:{result.task_id}", 86400)

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get task result by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskResult or None if not found
        """
        if not self.redis:
            await self.connect()

        result_data = await self.redis.hget(self.results_key, task_id)
        if not result_data:
            return None

        result_dict = json.loads(result_data)
        result = TaskResult(**result_dict)
        
        # Convert datetime strings back to datetime objects
        if result.started_at:
            result.started_at = datetime.fromisoformat(result.started_at)
        if result.completed_at:
            result.completed_at = datetime.fromisoformat(result.completed_at)

        return result

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled, False if not found or already running
        """
        if not self.redis:
            await self.connect()

        # Check if task is in processing queue
        processing_task = await self.redis.hget(self.processing_key, task_id)
        if processing_task:
            return False  # Cannot cancel running task

        # Remove from main queue
        queue_tasks = await self.redis.zrange(self.queue_key, 0, -1)
        for task_data in queue_tasks:
            task = json.loads(task_data)
            if task['id'] == task_id:
                await self.redis.zrem(self.queue_key, task_data)
                
                # Update result
                result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                    completed_at=datetime.utcnow(),
                )
                await self._store_result(result)
                
                logger.info(f"Cancelled task {task_id}")
                return True

        # Remove from scheduled queue
        scheduled_tasks = await self.redis.zrange(self.scheduled_key, 0, -1)
        for task_data in scheduled_tasks:
            task = json.loads(task_data)
            if task['id'] == task_id:
                await self.redis.zrem(self.scheduled_key, task_data)
                
                # Update result
                result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                    completed_at=datetime.utcnow(),
                )
                await self._store_result(result)
                
                logger.info(f"Cancelled scheduled task {task_id}")
                return True

        return False

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self.redis:
            await self.connect()

        pending_count = await self.redis.zcard(self.queue_key)
        processing_count = await self.redis.hlen(self.processing_key)
        scheduled_count = await self.redis.zcard(self.scheduled_key)
        
        # Count results by status
        results = await self.redis.hgetall(self.results_key)
        status_counts = {}
        
        for result_data in results.values():
            result = json.loads(result_data)
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            'queue_name': self.queue_name,
            'pending': pending_count,
            'processing': processing_count,
            'scheduled': scheduled_count,
            'status_counts': status_counts,
            'total_results': len(results),
        }

    async def clear_queue(self) -> None:
        """Clear all tasks from the queue (use with caution)."""
        if not self.redis:
            await self.connect()

        await self.redis.delete(
            self.queue_key,
            self.processing_key,
            self.results_key,
            self.scheduled_key,
        )
        
        logger.warning(f"Cleared all tasks from queue '{self.queue_name}'")


# Global task queue instance
task_queue = TaskQueue(queue_name="vinted_bot")