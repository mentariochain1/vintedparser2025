"""CRUD operations for database models."""

from datetime import datetime
from typing import Optional ,Sequence

from sqlalchemy import select
from sqlalchemy .ext .asyncio import AsyncSession
from sqlalchemy .orm import selectinload

from .models import Item, Payment, Photo, Referral, SavedSearch, User

class UserCRUD :
    """CRUD operations for User model."""

    @staticmethod
    async def get_by_tg_id (session :AsyncSession ,tg_id :int )->Optional [User ]:
        """Get user by Telegram ID."""
        result =await session .execute (
        select (User ).where (User .tg_id ==tg_id )
        )
        return result .scalar_one_or_none ()

    @staticmethod
    async def get_by_id (session :AsyncSession ,user_id :int )->Optional [User ]:
        """Get user by ID."""
        result =await session .execute (
        select (User ).where (User .id ==user_id )
        )
        return result .scalar_one_or_none ()

    @staticmethod
    async def create (
    session :AsyncSession ,
    tg_id :int ,
    username :Optional [str ]=None ,
    first_name :Optional [str ]=None ,
    trial_expires :Optional [datetime ]=None ,
    referred_by :Optional [int ]=None ,
    )->User :
        """Create a new user."""
        user =User (
        tg_id =tg_id ,
        username =username ,
        first_name =first_name ,
        trial_expires =trial_expires or datetime .utcnow (),
        referred_by =referred_by ,
        )
        session .add (user )
        await session .flush ()
        await session .refresh (user )
        return user

    @staticmethod
    async def update_trial_expires (
    session :AsyncSession ,
    user_id :int ,
    trial_expires :datetime ,
    )->Optional [User ]:
        """Update user's trial expiration date."""
        user =await UserCRUD .get_by_id (session ,user_id )
        if user :
            user .trial_expires =trial_expires
            await session .flush ()
            await session .refresh (user )
        return user

    @staticmethod
    async def increment_referrals_count (
    session :AsyncSession ,
    user_id :int ,
    )->Optional [User ]:
        """Increment user's referrals count."""
        user =await UserCRUD .get_by_id (session ,user_id )
        if user :
            user .referrals_count +=1
            await session .flush ()
            await session .refresh (user )
        return user

class ItemCRUD :
    """CRUD operations for Item model."""

    @staticmethod
    async def get_by_id (session :AsyncSession ,item_id :int )->Optional [Item ]:
        """Get item by ID with photos."""
        result =await session .execute (
        select (Item )
        .options (selectinload (Item .photos ))
        .where (Item .id ==item_id )
        )
        return result .scalar_one_or_none ()

    @staticmethod
    async def create (
    session :AsyncSession ,
    id :int ,
    title :str ,
    price :float ,
    currency :str ="EUR",
    brand :Optional [str ]=None ,
    size :Optional [str ]=None ,
    condition :Optional [str ]=None ,
    description :Optional [str ]=None ,
    seller_id :Optional [int ]=None ,
    url :str ="",
    preview_img :Optional [str ]=None ,
    ships_to_at :bool =True ,
    **kwargs
    )->Item :
        """Create a new item."""
        item =Item (
        id =id ,
        title =title ,
        price =price ,
        currency =currency ,
        brand =brand ,
        size =size ,
        condition =condition ,
        description =description ,
        seller_id =seller_id ,
        url =url ,
        preview_img =preview_img ,
        ships_to_at =ships_to_at ,
        )
        session .add (item )
        await session .flush ()
        await session .refresh (item )
        return item

    @staticmethod
    async def update (
    session :AsyncSession ,
    item_id :int ,
    **kwargs
    )->Optional [Item ]:
        """Update an existing item."""
        item =await ItemCRUD .get_by_id (session ,item_id )
        if item :
            for key ,value in kwargs .items ():
                if hasattr (item ,key ):
                    setattr (item ,key ,value )
            await session .flush ()
            await session .refresh (item )
        return item

    @staticmethod
    async def get_recent (
    session :AsyncSession ,
    limit :int =50 ,
    offset :int =0 ,
    ships_to_at :bool =True ,
    )->Sequence [Item ]:
        """Get recent items that ship to Austria."""
        result =await session .execute (
        select (Item )
        .where (Item .ships_to_at ==ships_to_at )
        .order_by (Item .created_at .desc ())
        .offset (offset )
        .limit (limit )
        )
        return result .scalars ().all ()

    @staticmethod
    async def get_recent_items (
    session :AsyncSession ,
    limit :int =50 ,
    ships_to_at :bool =True ,
    )->Sequence [Item ]:
        """Get recent items that ship to Austria."""
        return await ItemCRUD .get_recent (session ,limit ,0 ,ships_to_at )

class SavedSearchCRUD :
    """CRUD operations for SavedSearch model."""

    @staticmethod
    async def get_user_searches (
    session :AsyncSession ,
    user_id :int ,
    )->Sequence [SavedSearch ]:
        """Get all saved searches for a user."""
        result =await session .execute (
        select (SavedSearch )
        .where (SavedSearch .user_id ==user_id )
        .order_by (SavedSearch .created_at .desc ())
        )
        return result .scalars ().all ()

    @staticmethod
    async def create (
    session :AsyncSession ,
    user_id :int ,
    query :str ,
    filters :Optional [dict ]=None ,
    notifications_enabled :bool =True ,
    )->SavedSearch :
        """Create a new saved search."""
        saved_search =SavedSearch (
        user_id =user_id ,
        query =query ,
        filters =filters ,
        notifications_enabled =notifications_enabled ,
        )
        session .add (saved_search )
        await session .flush ()
        await session .refresh (saved_search )
        return saved_search

class ReferralCRUD :
    """CRUD operations for Referral model."""

    @staticmethod
    async def create (
    session :AsyncSession ,
    inviter_id :int ,
    invitee_id :int ,
    bonus_awarded :bool =False ,
    )->Referral :
        """Create a new referral."""
        referral =Referral (
        inviter_id =inviter_id ,
        invitee_id =invitee_id ,
        bonus_awarded =bonus_awarded ,
        )
        session .add (referral )
        await session .flush ()
        await session .refresh (referral )
        return referral

    @staticmethod
    async def get_by_invitee (
    session :AsyncSession ,
    invitee_id :int ,
    )->Optional [Referral ]:
        """Get referral by invitee ID."""
        result =await session .execute (
        select (Referral ).where (Referral .invitee_id ==invitee_id )
        )
        return result .scalar_one_or_none ()

class PaymentCRUD :
    """CRUD operations for Payment model."""

    @staticmethod
    async def create (
    session :AsyncSession ,
    user_id :int ,
    yookassa_id :str ,
    amount :float ,
    currency :str ="RUB",
    status :str ="pending",
    )->Payment :
        """Create a new payment."""
        payment =Payment (
        user_id =user_id ,
        yookassa_id =yookassa_id ,
        amount =amount ,
        currency =currency ,
        status =status ,
        )
        session .add (payment )
        await session .flush ()
        await session .refresh (payment )
        return payment

    @staticmethod
    async def get_by_yookassa_id (
    session :AsyncSession ,
    yookassa_id :str ,
    )->Optional [Payment ]:
        """Get payment by YooKassa ID."""
        result =await session .execute (
        select (Payment ).where (Payment .yookassa_id ==yookassa_id )
        )
        return result .scalar_one_or_none ()

    @staticmethod
    async def update_status (
    session :AsyncSession ,
    yookassa_id :str ,
    status :str ,
    )->Optional [Payment ]:
        """Update payment status."""
        payment =await PaymentCRUD .get_by_yookassa_id (session ,yookassa_id )
        if payment :
            payment .status =status
            await session .flush ()
            await session .refresh (payment )
        return payment

class PhotoCRUD :
    """CRUD operations for Photo model."""

    @staticmethod
    async def create (
    session :AsyncSession ,
    item_id :int ,
    url :str ,
    order_no :int =0 ,
    )->Photo :
        """Create a new photo."""
        photo =Photo (
        item_id =item_id ,
        url =url ,
        order_no =order_no ,
        )
        session .add (photo )
        await session .flush ()
        await session .refresh (photo )
        return photo

    @staticmethod
    async def get_by_item_id (
    session :AsyncSession ,
    item_id :int ,
    )->Sequence [Photo ]:
        """Get all photos for an item."""
        result =await session .execute (
        select (Photo )
        .where (Photo .item_id ==item_id )
        .order_by (Photo .order_no )
        )
        return result .scalars ().all ()

    @staticmethod
    async def delete_by_item_id (
    session :AsyncSession ,
    item_id :int ,
    )->None :
        """Delete all photos for an item."""
        photos =await PhotoCRUD .get_by_item_id (session ,item_id )
        for photo in photos :
            await session .delete (photo )