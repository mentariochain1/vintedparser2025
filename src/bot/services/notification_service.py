"""Notification service for sending alerts to users."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from db.models import User, SavedSearch, Item
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class NotificationItem:
    """Data class for notification item details."""
    item_id: int
    title: str
    price: str
    brand: Optional[str]
    url: str
    preview_img: Optional[str]


@dataclass
class UserNotification:
    """Data class for user notification with matched items."""
    user_id: int
    tg_id: int
    first_name: Optional[str]
    items: List[NotificationItem]
    search_queries: List[str]


class NotificationService:
    """Service for managing user notifications."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.max_items_per_notification = 5
        self.max_notifications_per_batch = 50
        
    async def find_matching_users(
        self, 
        session: AsyncSession, 
        items: List[Item]
    ) -> List[UserNotification]:
        """
        Find users with saved searches that match new items.
        
        Args:
            session: Database session
            items: List of new items to match against
            
        Returns:
            List of user notifications with matched items
        """
        if not items:
            return []
            
        logger.info(f"Finding matching users for {len(items)} items")
        
        # Get all active users with saved searches and valid subscriptions
        stmt = (
            select(User)
            .options(selectinload(User.saved_searches))
            .where(
                and_(
                    User.saved_searches.any(),
                    or_(
                        User.trial_expires > datetime.utcnow(),
                        and_(
                            User.subscription_expires.is_not(None),
                            User.subscription_expires > datetime.utcnow()
                        )
                    )
                )
            )
        )
        
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        if not users:
            logger.info("No active users with saved searches found")
            return []
            
        logger.info(f"Found {len(users)} active users with saved searches")
        
        user_notifications = []
        
        for user in users:
            matched_items = []
            matched_queries = []
            
            for saved_search in user.saved_searches:
                if not saved_search.notifications_enabled:
                    continue
                    
                # Match items against search query
                matching_items = self._match_items_to_search(items, saved_search)
                
                if matching_items:
                    matched_items.extend(matching_items)
                    matched_queries.append(saved_search.query)
            
            if matched_items:
                # Remove duplicates while preserving order
                seen_ids = set()
                unique_items = []
                for item in matched_items:
                    if item.item_id not in seen_ids:
                        unique_items.append(item)
                        seen_ids.add(item.item_id)
                
                # Limit items per notification
                if len(unique_items) > self.max_items_per_notification:
                    unique_items = unique_items[:self.max_items_per_notification]
                
                user_notification = UserNotification(
                    user_id=user.id,
                    tg_id=user.tg_id,
                    first_name=user.first_name,
                    items=unique_items,
                    search_queries=list(set(matched_queries))  # Remove duplicate queries
                )
                user_notifications.append(user_notification)
        
        logger.info(f"Found {len(user_notifications)} users with matching items")
        return user_notifications
    
    def _match_items_to_search(
        self, 
        items: List[Item], 
        saved_search: SavedSearch
    ) -> List[NotificationItem]:
        """
        Match items against a saved search query.
        
        Args:
            items: List of items to match
            saved_search: Saved search to match against
            
        Returns:
            List of matching notification items
        """
        matching_items = []
        query_lower = saved_search.query.lower()
        query_words = query_lower.split()
        
        for item in items:
            # Check if item matches the search query
            if self._item_matches_query(item, query_words, saved_search.filters):
                notification_item = NotificationItem(
                    item_id=item.id,
                    title=item.title,
                    price=f"{item.price} {item.currency}",
                    brand=item.brand,
                    url=item.url,
                    preview_img=item.preview_img
                )
                matching_items.append(notification_item)
        
        return matching_items
    
    def _item_matches_query(
        self, 
        item: Item, 
        query_words: List[str], 
        filters: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Check if an item matches search query and filters.
        
        Args:
            item: Item to check
            query_words: List of query words to match
            filters: Optional filters to apply
            
        Returns:
            True if item matches, False otherwise
        """
        # Create searchable text from item
        searchable_text = " ".join(filter(None, [
            item.title.lower() if item.title else "",
            item.brand.lower() if item.brand else "",
            item.description.lower() if item.description else ""
        ]))
        
        # Check if all query words are present
        for word in query_words:
            if word not in searchable_text:
                return False
        
        # Apply filters if present
        if filters:
            # Brand filter
            if "brand" in filters and filters["brand"]:
                if not item.brand or item.brand.lower() != filters["brand"].lower():
                    return False
            
            # Price range filter
            if "min_price" in filters and filters["min_price"]:
                if item.price < filters["min_price"]:
                    return False
                    
            if "max_price" in filters and filters["max_price"]:
                if item.price > filters["max_price"]:
                    return False
            
            # Size filter
            if "size" in filters and filters["size"]:
                if not item.size or item.size.lower() != filters["size"].lower():
                    return False
        
        return True
    
    async def send_batch_notifications(
        self, 
        notifications: List[UserNotification]
    ) -> Dict[str, int]:
        """
        Send notifications to users in batches with rate limiting.
        
        Args:
            notifications: List of user notifications to send
            
        Returns:
            Dictionary with success/failure counts
        """
        if not notifications:
            return {"sent": 0, "failed": 0, "blocked": 0}
        
        logger.info(f"Sending batch notifications to {len(notifications)} users")
        
        # Limit batch size
        if len(notifications) > self.max_notifications_per_batch:
            notifications = notifications[:self.max_notifications_per_batch]
            logger.warning(f"Limited batch to {self.max_notifications_per_batch} notifications")
        
        sent_count = 0
        failed_count = 0
        blocked_count = 0
        
        for notification in notifications:
            try:
                await self._send_user_notification(notification)
                sent_count += 1
                
                # Rate limiting - small delay between notifications
                import asyncio
                await asyncio.sleep(0.1)  # 100ms delay
                
            except TelegramForbiddenError:
                # User blocked the bot
                blocked_count += 1
                logger.warning(f"User {notification.tg_id} has blocked the bot")
                
            except TelegramBadRequest as e:
                # Invalid user or other Telegram error
                failed_count += 1
                logger.error(f"Failed to send notification to user {notification.tg_id}: {e}")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Unexpected error sending notification to user {notification.tg_id}: {e}")
        
        result = {
            "sent": sent_count,
            "failed": failed_count,
            "blocked": blocked_count
        }
        
        logger.info(f"Batch notification results: {result}")
        return result
    
    async def _send_user_notification(self, notification: UserNotification) -> None:
        """
        Send notification to a single user.
        
        Args:
            notification: User notification to send
        """
        # Build notification message
        greeting = f"👋 {notification.first_name or 'Hello'}!"
        
        if len(notification.search_queries) == 1:
            header = f"🔍 New items found for your search: <b>{notification.search_queries[0]}</b>"
        else:
            header = f"🔍 New items found for your saved searches"
        
        items_text = []
        for i, item in enumerate(notification.items, 1):
            brand_text = f" by {item.brand}" if item.brand else ""
            item_text = f"{i}. <b>{item.title}</b>{brand_text}\n💰 {item.price}\n🔗 <a href='{item.url}'>View on Vinted</a>"
            items_text.append(item_text)
        
        message = f"{greeting}\n\n{header}\n\n" + "\n\n".join(items_text)
        
        if len(notification.items) == self.max_items_per_notification:
            message += f"\n\n<i>Showing first {self.max_items_per_notification} items. Check your searches for more!</i>"
        
        await self.bot.send_message(
            chat_id=notification.tg_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    
    async def send_subscription_expiry_notifications(
        self, 
        session: AsyncSession
    ) -> Dict[str, int]:
        """
        Send notifications to users whose subscriptions are expiring soon.
        
        Args:
            session: Database session
            
        Returns:
            Dictionary with notification counts
        """
        logger.info("Sending subscription expiry notifications")
        
        # Find users whose trial/subscription expires in 1 day
        tomorrow = datetime.utcnow() + timedelta(days=1)
        day_after = tomorrow + timedelta(days=1)
        
        stmt = select(User).where(
            or_(
                and_(
                    User.trial_expires >= tomorrow,
                    User.trial_expires < day_after,
                    User.subscription_expires.is_(None)  # Trial users only
                ),
                and_(
                    User.subscription_expires >= tomorrow,
                    User.subscription_expires < day_after
                )
            )
        )
        
        result = await session.execute(stmt)
        expiring_users = result.scalars().all()
        
        if not expiring_users:
            logger.info("No users with expiring subscriptions found")
            return {"sent": 0, "failed": 0, "blocked": 0}
        
        logger.info(f"Found {len(expiring_users)} users with expiring subscriptions")
        
        sent_count = 0
        failed_count = 0
        blocked_count = 0
        
        for user in expiring_users:
            try:
                await self._send_expiry_notification(user)
                sent_count += 1
                
                # Rate limiting
                import asyncio
                await asyncio.sleep(0.2)  # 200ms delay for expiry notifications
                
            except TelegramForbiddenError:
                blocked_count += 1
                logger.warning(f"User {user.tg_id} has blocked the bot")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send expiry notification to user {user.tg_id}: {e}")
        
        result = {
            "sent": sent_count,
            "failed": failed_count,
            "blocked": blocked_count
        }
        
        logger.info(f"Expiry notification results: {result}")
        return result
    
    async def _send_expiry_notification(self, user: User) -> None:
        """
        Send subscription expiry notification to a user.
        
        Args:
            user: User to notify
        """
        greeting = f"👋 {user.first_name or 'Hello'}!"
        
        # Determine if it's trial or subscription expiring
        if user.subscription_expires and user.subscription_expires > datetime.utcnow():
            expiry_date = user.subscription_expires
            subscription_type = "premium subscription"
        else:
            expiry_date = user.trial_expires
            subscription_type = "trial period"
        
        message = (
            f"{greeting}\n\n"
            f"⏰ Your {subscription_type} expires tomorrow "
            f"({expiry_date.strftime('%Y-%m-%d')}).\n\n"
            f"💎 Upgrade to premium to continue receiving:\n"
            f"• 🔍 Unlimited searches\n"
            f"• 🔔 New item notifications\n"
            f"• 💾 Saved search alerts\n\n"
            f"Use /pay to upgrade now!"
        )
        
        await self.bot.send_message(
            chat_id=user.tg_id,
            text=message,
            parse_mode="HTML"
        )