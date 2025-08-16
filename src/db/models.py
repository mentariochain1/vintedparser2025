"""SQLAlchemy models for the Vinted Parser Bot."""

from datetime import datetime
from decimal import Decimal
from typing import List ,Optional

from sqlalchemy import (
BigInteger ,
Boolean ,
DateTime ,
ForeignKey ,
Index ,
Integer ,
Numeric ,
String ,
Text ,
UniqueConstraint ,
func ,
)
from sqlalchemy .dialects .postgresql import JSONB
from sqlalchemy .ext .declarative import declarative_base
from sqlalchemy .orm import Mapped ,mapped_column ,relationship

Base =declarative_base ()

class TimestampMixin :
    """Mixin for created_at and updated_at timestamps."""

    created_at :Mapped [datetime ]=mapped_column (
    DateTime (timezone =True ),
    server_default =func .now (),
    nullable =False ,
    index =True
    )
    updated_at :Mapped [datetime ]=mapped_column (
    DateTime (timezone =True ),
    server_default =func .now (),
    onupdate =func .now (),
    nullable =False
    )

class User (Base ,TimestampMixin ):
    """User model for Telegram users."""

    __tablename__ ="users"

    id :Mapped [int ]=mapped_column (BigInteger ,primary_key =True )
    tg_id :Mapped [int ]=mapped_column (BigInteger ,unique =True ,nullable =False ,index =True )
    username :Mapped [Optional [str ]]=mapped_column (String (255 ),nullable =True )
    first_name :Mapped [Optional [str ]]=mapped_column (String (255 ),nullable =True )
    joined_at :Mapped [datetime ]=mapped_column (
    DateTime (timezone =True ),
    server_default =func .now (),
    nullable =False
    )
    trial_expires :Mapped [datetime ]=mapped_column (DateTime (timezone =True ),nullable =False )
    subscription_expires :Mapped [Optional [datetime ]]=mapped_column (
    DateTime (timezone =True ),
    nullable =True
    )
    referred_by :Mapped [Optional [int ]]=mapped_column (
    BigInteger ,
    ForeignKey ("users.id",ondelete ="SET NULL"),
    nullable =True ,
    index =True
    )
    referrals_count :Mapped [int ]=mapped_column (Integer ,default =0 ,nullable =False )

    referrer :Mapped [Optional ["User"]]=relationship (
    "User",
    remote_side =[id ],
    back_populates ="referrals"
    )
    referrals :Mapped [List ["User"]]=relationship (
    "User",
    remote_side =[referred_by ],
    back_populates ="referrer"
    )
    saved_searches :Mapped [List ["SavedSearch"]]=relationship (
    "SavedSearch",
    back_populates ="user",
    cascade ="all, delete-orphan"
    )
    payments :Mapped [List ["Payment"]]=relationship (
    "Payment",
    back_populates ="user",
    cascade ="all, delete-orphan"
    )
    referral_invites :Mapped [List ["Referral"]]=relationship (
    "Referral",
    foreign_keys ="Referral.inviter_id",
    back_populates ="inviter",
    cascade ="all, delete-orphan"
    )
    referral_invitees :Mapped [List ["Referral"]]=relationship (
    "Referral",
    foreign_keys ="Referral.invitee_id",
    back_populates ="invitee",
    cascade ="all, delete-orphan"
    )

    def __repr__ (self )->str :
        return f"<User(id={self .id }, tg_id={self .tg_id }, username={self .username })>"

class Item (Base ,TimestampMixin ):
    """Vinted item model."""

    __tablename__ ="items"

    id :Mapped [int ]=mapped_column (BigInteger ,primary_key =True )
    title :Mapped [str ]=mapped_column (String (500 ),nullable =False )
    price :Mapped [Decimal ]=mapped_column (Numeric (10 ,2 ),nullable =False )
    currency :Mapped [str ]=mapped_column (String (3 ),default ="EUR",nullable =False )
    brand :Mapped [Optional [str ]]=mapped_column (String (255 ),nullable =True ,index =True )
    size :Mapped [Optional [str ]]=mapped_column (String (100 ),nullable =True )
    condition :Mapped [Optional [str ]]=mapped_column (String (100 ),nullable =True )
    description :Mapped [Optional [str ]]=mapped_column (Text ,nullable =True )
    seller_id :Mapped [Optional [int ]]=mapped_column (BigInteger ,nullable =True ,index =True )
    url :Mapped [str ]=mapped_column (String (500 ),nullable =False )
    preview_img :Mapped [Optional [str ]]=mapped_column (String (500 ),nullable =True )
    ships_to_at :Mapped [bool ]=mapped_column (Boolean ,default =True ,nullable =False ,index =True )

    photos :Mapped [List ["Photo"]]=relationship (
    "Photo",
    back_populates ="item",
    cascade ="all, delete-orphan",
    order_by ="Photo.order_no"
    )

    __table_args__ =(
    Index ("ix_items_brand_price","brand","price"),
    Index ("ix_items_seller_created","seller_id","created_at"),
    Index ("ix_items_ships_to_at_created","ships_to_at","created_at"),
    )

    def __repr__ (self )->str :
        return f"<Item(id={self .id }, title={self .title [:50 ]}, price={self .price })>"

class Photo (Base ,TimestampMixin ):
    """Photo model for item images."""

    __tablename__ ="photos"

    id :Mapped [int ]=mapped_column (BigInteger ,primary_key =True )
    item_id :Mapped [int ]=mapped_column (
    BigInteger ,
    ForeignKey ("items.id",ondelete ="CASCADE"),
    nullable =False ,
    index =True
    )
    url :Mapped [str ]=mapped_column (String (500 ),nullable =False )
    order_no :Mapped [int ]=mapped_column (Integer ,default =0 ,nullable =False )

    item :Mapped ["Item"]=relationship ("Item",back_populates ="photos")

    __table_args__ =(
    Index ("ix_photos_item_order","item_id","order_no"),
    )

    def __repr__ (self )->str :
        return f"<Photo(id={self .id }, item_id={self .item_id }, order_no={self .order_no })>"

class SavedSearch (Base ,TimestampMixin ):
    """Saved search model for user search preferences."""

    __tablename__ ="saved_searches"

    id :Mapped [int ]=mapped_column (BigInteger ,primary_key =True )
    user_id :Mapped [int ]=mapped_column (
    BigInteger ,
    ForeignKey ("users.id",ondelete ="CASCADE"),
    nullable =False ,
    index =True
    )
    query :Mapped [str ]=mapped_column (String (255 ),nullable =False )
    filters :Mapped [Optional [dict ]]=mapped_column (JSONB ,nullable =True )
    notifications_enabled :Mapped [bool ]=mapped_column (Boolean ,default =True ,nullable =False )

    user :Mapped ["User"]=relationship ("User",back_populates ="saved_searches")

    def __repr__ (self )->str :
        return f"<SavedSearch(id={self .id }, user_id={self .user_id }, query={self .query })>"

class Referral (Base ,TimestampMixin ):
    """Referral model for tracking user referrals."""

    __tablename__ ="referrals"

    id :Mapped [int ]=mapped_column (BigInteger ,primary_key =True )
    inviter_id :Mapped [int ]=mapped_column (
    BigInteger ,
    ForeignKey ("users.id",ondelete ="CASCADE"),
    nullable =False ,
    index =True
    )
    invitee_id :Mapped [int ]=mapped_column (
    BigInteger ,
    ForeignKey ("users.id",ondelete ="CASCADE"),
    nullable =False ,
    index =True
    )
    bonus_awarded :Mapped [bool ]=mapped_column (Boolean ,default =False ,nullable =False )

    inviter :Mapped ["User"]=relationship (
    "User",
    foreign_keys =[inviter_id ],
    back_populates ="referral_invites"
    )
    invitee :Mapped ["User"]=relationship (
    "User",
    foreign_keys =[invitee_id ],
    back_populates ="referral_invitees"
    )

    __table_args__ =(
    UniqueConstraint ("invitee_id",name ="uq_referrals_invitee_id"),
    Index ("ix_referrals_inviter_created","inviter_id","created_at"),
    )

    def __repr__ (self )->str :
        return f"<Referral(id={self .id }, inviter_id={self .inviter_id }, invitee_id={self .invitee_id })>"

class Payment (Base ,TimestampMixin ):
    """Payment model for YooKassa payments."""

    __tablename__ ="payments"

    id :Mapped [int ]=mapped_column (BigInteger ,primary_key =True )
    user_id :Mapped [int ]=mapped_column (
    BigInteger ,
    ForeignKey ("users.id",ondelete ="CASCADE"),
    nullable =False ,
    index =True
    )
    yookassa_id :Mapped [str ]=mapped_column (String (255 ),unique =True ,nullable =False ,index =True )
    amount :Mapped [Decimal ]=mapped_column (Numeric (10 ,2 ),nullable =False )
    currency :Mapped [str ]=mapped_column (String (3 ),default ="RUB",nullable =False )
    status :Mapped [str ]=mapped_column (String (50 ),nullable =False ,index =True )

    user :Mapped ["User"]=relationship ("User",back_populates ="payments")

    __table_args__ =(
    Index ("ix_payments_user_status","user_id","status"),
    Index ("ix_payments_status_created","status","created_at"),
    )

    def __repr__ (self )->str :
        return f"<Payment(id={self .id }, user_id={self .user_id }, yookassa_id={self .yookassa_id }, status={self .status })>"