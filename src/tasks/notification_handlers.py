"""Task handlers for notification operations."""

import logging
from typing import Dict, Any, List
from datetime import datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from tasks.queue import TaskQueue
from db.base import get_db_session as get_async_session
from db.models import Item
from bot.services.notification_service import NotificationService
from config import settings

logger = logging.getLogger(__name__)


async def process_new_item_notifications(item_ids: List[int]) -> Dict[str, Any]:
    """
    Process notifications for new items.
    
    Args:
        item_ids: List of new item IDs to process
        
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Processing notifications for {len(item_ids)} new items")
    
    if not item_ids:
        return {"processed": 0, "notifications_sent": 0}
    
    try:
        # Create bot instance
        bot = Bot(token=settings.bot_token, parse_mode="HTML")
        notification_service = NotificationService(bot)
        
        async with get_async_session() as session:
            # Fetch the new items
            from sqlalchemy import select
            stmt = select(Item).where(Item.id.in_(item_ids))
            result = await session.execute(stmt)
            items = result.scalars().all()
            
            if not items:
                logger.warning(f"No items found for IDs: {item_ids}")
                return {"processed": 0, "notifications_sent": 0}
            
            # Find users with matching saved searches
            user_notifications = await notification_service.find_matching_users(
                session, items
            )
            
            if not user_notifications:
                logger.info("No users with matching saved searches found")
                return {"processed": len(items), "notifications_sent": 0}
            
            # Send batch notifications
            results = await notification_service.send_batch_notifications(
                user_notifications
            )
            
            logger.info(
                f"Processed {len(items)} items, sent {results['sent']} notifications"
            )
            
            return {
                "processed": len(items),
                "notifications_sent": results["sent"],
                "failed": results["failed"],
                "blocked": results["blocked"]
            }
            
    except Exception as e:
        logger.error(f"Error processing new item notifications: {e}")
        raise
    finally:
        await bot.session.close()


async def send_subscription_expiry_notifications() -> Dict[str, Any]:
    """
    Send notifications to users with expiring subscriptions.
    
    Returns:
        Dictionary with processing results
    """
    logger.info("Processing subscription expiry notifications")
    
    try:
        # Create bot instance
        bot = Bot(token=settings.bot_token, parse_mode="HTML")
        notification_service = NotificationService(bot)
        
        async with get_async_session() as session:
            results = await notification_service.send_subscription_expiry_notifications(
                session
            )
            
            logger.info(f"Sent {results['sent']} expiry notifications")
            
            return {
                "notifications_sent": results["sent"],
                "failed": results["failed"],
                "blocked": results["blocked"]
            }
            
    except Exception as e:
        logger.error(f"Error sending expiry notifications: {e}")
        raise
    finally:
        await bot.session.close()


async def batch_notification_processor(
    notification_batches: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Process multiple notification batches with rate limiting.
    
    Args:
        notification_batches: List of notification batch data
        
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Processing {len(notification_batches)} notification batches")
    
    total_sent = 0
    total_failed = 0
    total_blocked = 0
    
    try:
        bot = Bot(token=settings.bot_token, parse_mode="HTML")
        notification_service = NotificationService(bot)
        
        for batch_data in notification_batches:
            item_ids = batch_data.get("item_ids", [])
            
            if not item_ids:
                continue
                
            # Process this batch
            batch_results = await process_new_item_notifications(item_ids)
            
            total_sent += batch_results.get("notifications_sent", 0)
            total_failed += batch_results.get("failed", 0)
            total_blocked += batch_results.get("blocked", 0)
            
            # Rate limiting between batches
            import asyncio
            await asyncio.sleep(1.0)  # 1 second delay between batches
        
        return {
            "batches_processed": len(notification_batches),
            "total_sent": total_sent,
            "total_failed": total_failed,
            "total_blocked": total_blocked
        }
        
    except Exception as e:
        logger.error(f"Error processing notification batches: {e}")
        raise
    finally:
        await bot.session.close()


def register_notification_handlers(queue: TaskQueue) -> None:
    """
    Register notification task handlers.
    
    Args:
        queue: TaskQueue instance to register handlers with
    """
    logger.info("Registering notification handlers...")
    
    # Register individual notification handlers
    queue.register_handler("process_new_item_notifications", process_new_item_notifications)
    queue.register_handler("send_subscription_expiry_notifications", send_subscription_expiry_notifications)
    queue.register_handler("batch_notification_processor", batch_notification_processor)
    
    logger.info("Notification handlers registered successfully")