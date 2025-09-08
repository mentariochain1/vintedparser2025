"""User service using direct asyncpg for database operations."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import asyncpg

from src.db.asyncpg_adapter import db_adapter
from src.bot.services.user_service import UserService

logger = logging.getLogger(__name__)

def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)

class UserServiceAsyncpg(UserService):
    """User service using direct asyncpg for database operations."""
    
    async def create_user_asyncpg(
        self,
        tg_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        referrer_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new user with trial period using asyncpg."""
        trial_expires = utc_now() + timedelta(days=self.default_trial_days)
        
        query = """
        INSERT INTO users (tg_id, username, first_name, trial_expires, referred_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        RETURNING id, tg_id, username, first_name, trial_expires, referred_by, referrals_count, created_at, updated_at
        """
        
        async with db_adapter.get_connection() as conn:
            row = await conn.fetchrow(
                query, 
                tg_id, 
                username, 
                first_name, 
                trial_expires, 
                referrer_id
            )
            
            if row:
                return dict(row)
            else:
                raise Exception("Failed to create user")
    
    async def get_user_asyncpg(self, tg_id: int) -> Optional[Dict[str, Any]]:
        """Get user by Telegram ID using asyncpg."""
        query = """
        SELECT id, tg_id, username, first_name, trial_expires, subscription_expires, 
               referred_by, referrals_count, created_at, updated_at
        FROM users 
        WHERE tg_id = $1
        """
        
        async with db_adapter.get_connection() as conn:
            row = await conn.fetchrow(query, tg_id)
            return dict(row) if row else None
    
    async def get_user_by_id_asyncpg(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID using asyncpg."""
        query = """
        SELECT id, tg_id, username, first_name, trial_expires, subscription_expires, 
               referred_by, referrals_count, created_at, updated_at
        FROM users 
        WHERE id = $1
        """
        
        async with db_adapter.get_connection() as conn:
            row = await conn.fetchrow(query, user_id)
            return dict(row) if row else None
    
    async def is_premium_active_asyncpg(self, tg_id: int) -> bool:
        """Check if user has active premium access using asyncpg."""
        user = await self.get_user_asyncpg(tg_id)
        if not user:
            return False
        
        now = utc_now()
        
        # Check trial
        if user['trial_expires'] and user['trial_expires'] > now:
            return True
        
        # Check subscription
        if user['subscription_expires'] and user['subscription_expires'] > now:
            return True
        
        return False
    
    async def extend_trial_asyncpg(
        self,
        user_id: int,
        days: int,
    ) -> Optional[Dict[str, Any]]:
        """Extend user's trial period by specified days using asyncpg."""
        user = await self.get_user_by_id_asyncpg(user_id)
        if not user:
            return None
        
        now_utc = utc_now()
        base_date = max(user['trial_expires'], now_utc)
        new_expiry = base_date + timedelta(days=days)
        
        # Cap at 90 days
        max_trial = now_utc + timedelta(days=90)
        new_expiry = min(new_expiry, max_trial)
        
        query = """
        UPDATE users 
        SET trial_expires = $1, updated_at = NOW()
        WHERE id = $2
        RETURNING id, tg_id, username, first_name, trial_expires, subscription_expires, 
                  referred_by, referrals_count, created_at, updated_at
        """
        
        async with db_adapter.get_connection() as conn:
            row = await conn.fetchrow(query, new_expiry, user_id)
            return dict(row) if row else None
    
    async def process_referral_asyncpg(
        self,
        inviter_id: int,
        invitee_id: int,
    ) -> tuple[bool, str]:
        """Process a referral between users using asyncpg."""
        
        async with db_adapter.get_connection() as conn:
            async with conn.transaction():
                # Check if referral already exists
                existing = await conn.fetchrow(
                    "SELECT id FROM referrals WHERE invitee_id = $1", 
                    invitee_id
                )
                if existing:
                    return False, "User was already referred"
                
                # Check if invitee already has a referrer
                invitee = await conn.fetchrow(
                    "SELECT referred_by FROM users WHERE id = $1", 
                    invitee_id
                )
                if not invitee:
                    return False, "Invitee not found"
                
                if invitee['referred_by'] is not None:
                    return False, "User already has a referrer"
                
                # Create referral record
                await conn.execute(
                    """
                    INSERT INTO referrals (inviter_id, invitee_id, bonus_awarded, created_at, updated_at)
                    VALUES ($1, $2, true, NOW(), NOW())
                    """,
                    inviter_id, invitee_id
                )
                
                # Update invitee's referred_by
                await conn.execute(
                    "UPDATE users SET referred_by = $1, updated_at = NOW() WHERE id = $2",
                    inviter_id, invitee_id
                )
                
                # Increment inviter's referrals count
                await conn.execute(
                    "UPDATE users SET referrals_count = referrals_count + 1, updated_at = NOW() WHERE id = $1",
                    inviter_id
                )
                
                # Extend inviter's trial
                inviter = await conn.fetchrow(
                    "SELECT trial_expires FROM users WHERE id = $1",
                    inviter_id
                )
                
                if inviter:
                    now_utc = utc_now()
                    base_date = max(inviter['trial_expires'], now_utc)
                    new_expiry = base_date + timedelta(days=self.referral_bonus_days)
                    max_trial = now_utc + timedelta(days=90)
                    new_expiry = min(new_expiry, max_trial)
                    
                    await conn.execute(
                        "UPDATE users SET trial_expires = $1, updated_at = NOW() WHERE id = $2",
                        new_expiry, inviter_id
                    )
                
                return True, f"Referral processed successfully. {self.referral_bonus_days} days added to inviter's trial."

# Global instance
user_service_asyncpg = UserServiceAsyncpg()