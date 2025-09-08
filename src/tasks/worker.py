"""Background worker process for executing tasks."""

import asyncio
import logging
import signal
import sys
from typing import Dict, Any

from src.config import settings
from tasks.queue import task_queue, TaskQueue
from tasks.handlers import register_all_handlers

logger = logging.getLogger(__name__)


class TaskWorker:
    """Background task worker."""

    def __init__(self, num_workers: int = None):
        """
        Initialize task worker.
        
        Args:
            num_workers: Number of worker processes (defaults to CPU count)
        """
        self.num_workers = num_workers or min(4, (asyncio.get_event_loop().get_debug() and 1) or 2)
        self.queue = task_queue
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the worker process."""
        logger.info(f"Starting task worker with {self.num_workers} workers")
        
        # Register signal handlers for graceful shutdown
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._signal_handler)

        try:
            # Connect to Redis
            await self.queue.connect()
            
            # Register all task handlers
            register_all_handlers(self.queue)
            
            # Start workers
            await self.queue.start_workers(self.num_workers)
            
            logger.info("Task worker started successfully")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error starting task worker: {e}")
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the worker process gracefully."""
        logger.info("Shutting down task worker...")
        
        # Stop workers (with error handling)
        try:
            await self.queue.stop_workers()
        except Exception as e:
            logger.error(f"Error stopping workers: {e}")
        
        # Disconnect from Redis (with error handling)
        try:
            await self.queue.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")
        
        logger.info("Task worker shutdown complete")

    def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        logger.info("Received shutdown signal")
        self._shutdown_event.set()

    async def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return await self.queue.get_queue_stats()


async def main():
    """Main entry point for the worker process."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    
    # Create and start worker
    worker = TaskWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())