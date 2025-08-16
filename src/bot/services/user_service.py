"""User service for managing users, trials, and referrals."""

import base64
import hashlib
import hmac
import time
from datetime import datetime ,timedelta, timezone
from typing import Optional

from sqlalchemy .ext .asyncio import AsyncSession

from config import settings
from db.crud import ReferralCRUD ,UserCRUD
from db.models import User

def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)

class UserService :
    """Service for user management, trial periods, and referrals."""

    def __init__ (self ):
        self .referral_secret =settings .referral_secret .encode ()
        self .default_trial_days =settings .default_trial_days
        self .referral_bonus_days =settings .referral_bonus_days
        self .referral_ttl_seconds =14 *24 *3600

    async def create_user (
    self ,
    session :AsyncSession ,
    tg_id :int ,
    username :Optional [str ]=None ,
    first_name :Optional [str ]=None ,
    referrer_id :Optional [int ]=None ,
    )->User :
        """Create a new user with trial period."""
        trial_expires =utc_now ()+timedelta (days =self .default_trial_days )

        user =await UserCRUD .create (
        session =session ,
        tg_id =tg_id ,
        username =username ,
        first_name =first_name ,
        trial_expires =trial_expires ,
        referred_by =referrer_id ,
        )

        await session .commit ()
        return user

    async def get_user (self ,session :AsyncSession ,tg_id :int )->Optional [User ]:
        """Get user by Telegram ID."""
        return await UserCRUD .get_by_tg_id (session ,tg_id )

    async def get_user_by_id (self ,session :AsyncSession ,user_id :int )->Optional [User ]:
        """Get user by ID."""
        return await UserCRUD .get_by_id (session ,user_id )

    async def extend_trial (
    self ,
    session :AsyncSession ,
    user_id :int ,
    days :int ,
    )->Optional [User ]:
        """Extend user's trial period by specified days."""
        user =await UserCRUD .get_by_id (session ,user_id )
        if not user :
            return None

        now_utc = utc_now()
        base_date =max (user .trial_expires ,now_utc )
        new_expiry =base_date +timedelta (days =days )

        max_trial =now_utc +timedelta (days =90 )
        new_expiry =min (new_expiry ,max_trial )

        user =await UserCRUD .update_trial_expires (session ,user_id ,new_expiry )
        await session .commit ()
        return user

    async def is_premium_active (self ,session :AsyncSession ,user_id :int )->bool :
        """Check if user has active premium access (trial or subscription)."""
        user =await UserCRUD .get_by_id (session ,user_id )
        if not user :
            return False

        now =utc_now ()

        if user .trial_expires >now :
            return True

        if user .subscription_expires and user .subscription_expires >now :
            return True

        return False

    async def process_referral (
    self ,
    session :AsyncSession ,
    inviter_id :int ,
    invitee_id :int ,
    )->tuple [bool ,str ]:
        """
        Process a referral between users.

        Returns:
            tuple[bool, str]: (success, message)
        """

        inviter =await UserCRUD .get_by_id (session ,inviter_id )
        invitee =await UserCRUD .get_by_id (session ,invitee_id )

        if not inviter :
            return False ,"Inviter not found"

        if not invitee :
            return False ,"Invitee not found"

        if inviter_id ==invitee_id :
            return False ,"Cannot refer yourself"

        existing_referral =await ReferralCRUD .get_by_invitee (session ,invitee_id )
        if existing_referral :
            return False ,"User was already referred"

        if invitee .referred_by is not None :
            return False ,"User already has a referrer"

        try :

            await ReferralCRUD .create (
            session =session ,
            inviter_id =inviter_id ,
            invitee_id =invitee_id ,
            bonus_awarded =True ,
            )

            invitee .referred_by =inviter_id

            await UserCRUD .increment_referrals_count (session ,inviter_id )

            await self .extend_trial (session ,inviter_id ,self .referral_bonus_days )

            await session .commit ()
            return True ,f"Referral processed successfully. {self .referral_bonus_days } days added to inviter's trial."

        except Exception as e :
            await session .rollback ()
            return False ,f"Failed to process referral: {str (e )}"

    def encode_referral_payload (self ,inviter_id :int )->str :
        """Encode referral payload with HMAC signature and timestamp."""
        timestamp =int (time .time ())
        body =f"{inviter_id }:{timestamp }".encode ()
        signature =hmac .new (self .referral_secret ,body ,hashlib .sha256 ).digest ()[:9 ]

        payload =body +b":"+signature

        return base64 .urlsafe_b64encode (payload ).decode ().rstrip ("=")

    def decode_referral_payload (self ,token :str )->Optional [int ]:
        """
        Decode referral payload and verify signature and timestamp.

        Returns:
            Optional[int]: inviter_id if valid, None if invalid or expired
        """
        try :

            padding ="="*(-len (token )%4 )
            payload =base64 .urlsafe_b64decode (token +padding )

            parts =payload .rsplit (b":",1 )
            if len (parts )!=2 :
                return None

            body ,signature =parts

            expected_signature =hmac .new (self .referral_secret ,body ,hashlib .sha256 ).digest ()[:9 ]
            if not hmac .compare_digest (signature ,expected_signature ):
                return None

            body_str =body .decode ()
            inviter_str ,timestamp_str =body_str .split (":",1 )

            timestamp =int (timestamp_str )
            if time .time ()-timestamp >self .referral_ttl_seconds :
                return None

            return int (inviter_str )

        except (ValueError ,TypeError ,UnicodeDecodeError ):
            return None

    def generate_referral_link (self ,bot_username :str ,inviter_id :int )->str :
        """Generate a referral deep link for the inviter."""
        payload =self .encode_referral_payload (inviter_id )
        return f"https://t.me/{bot_username }?start={payload }"

    async def get_referral_stats (self ,session :AsyncSession ,user_id :int )->dict :
        """Get referral statistics for a user."""
        user =await UserCRUD .get_by_id (session ,user_id )
        if not user :
            return {
            "referrals_count":0 ,
            "trial_expires":None ,
            "subscription_expires":None ,
            }

        return {
        "referrals_count":user .referrals_count ,
        "trial_expires":user .trial_expires ,
        "subscription_expires":user .subscription_expires ,
        }