"""Tests for start command handler."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from aiogram import types
from aiogram .filters import CommandStart

from src .bot .handlers .start import start_handler
from src .bot .services .user_service import UserService
from src .db .models import User

@pytest .fixture
def mock_user_service ():
    """Mock user service."""
    service =MagicMock (spec =UserService )
    service .default_trial_days =7
    service .referral_bonus_days =3
    return service

@pytest .fixture
def mock_session ():
    """Mock database session."""
    session =AsyncMock ()
    return session

@pytest .fixture
def sample_user ():
    """Sample user for testing."""
    return User (
    id =1 ,
    tg_id =12345 ,
    username ="testuser",
    first_name ="Test",
    trial_expires =datetime .utcnow ()+timedelta (days =5 ),
    subscription_expires =None ,
    referred_by =None ,
    referrals_count =2 ,
    joined_at =datetime .utcnow (),
    created_at =datetime .utcnow (),
    updated_at =datetime .utcnow ()
    )

@pytest .fixture
def expired_user ():
    """User with expired trial."""
    return User (
    id =2 ,
    tg_id =67890 ,
    username ="expireduser",
    first_name ="Expired",
    trial_expires =datetime .utcnow ()-timedelta (days =1 ),
    subscription_expires =None ,
    referred_by =None ,
    referrals_count =0 ,
    joined_at =datetime .utcnow ()-timedelta (days =8 ),
    created_at =datetime .utcnow ()-timedelta (days =8 ),
    updated_at =datetime .utcnow ()-timedelta (days =8 )
    )

class TestStartHandler :
    """Test cases for start command handler."""

    @pytest .mark .asyncio
    async def test_new_user_creation_without_referral (self ,mock_user_service ,mock_session ):
        """Test creating a new user without referral."""

        mock_user_service .get_user .return_value =None
        new_user =User (
        id =1 ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        trial_expires =datetime .utcnow ()+timedelta (days =7 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =0 ,
        joined_at =datetime .utcnow (),
        created_at =datetime .utcnow (),
        updated_at =datetime .utcnow ()
        )
        mock_user_service .create_user .return_value =new_user

        message =MagicMock ()
        message .from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        )
        message .answer =AsyncMock ()
        message .bot =MagicMock ()

        command =CommandStart ()

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        mock_user_service .create_user .assert_called_once_with (
        session =mock_session ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        referrer_id =None
        )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Welcome to Vinted Parser Bot, New!"in call_args
        assert "7-day trial period"in call_args

    @pytest .mark .asyncio
    async def test_new_user_with_valid_referral (self ,mock_user_service ,mock_session ):
        """Test creating a new user with valid referral."""

        referrer =User (
        id =2 ,
        tg_id =67890 ,
        username ="referrer",
        first_name ="Referrer",
        trial_expires =datetime .utcnow ()+timedelta (days =5 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =1 ,
        joined_at =datetime .utcnow ()-timedelta (days =2 ),
        created_at =datetime .utcnow ()-timedelta (days =2 ),
        updated_at =datetime .utcnow ()-timedelta (days =2 )
        )

        new_user =User (
        id =1 ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        trial_expires =datetime .utcnow ()+timedelta (days =7 ),
        subscription_expires =None ,
        referred_by =2 ,
        referrals_count =0 ,
        joined_at =datetime .utcnow (),
        created_at =datetime .utcnow (),
        updated_at =datetime .utcnow ()
        )

        mock_user_service .get_user .return_value =None
        mock_user_service .decode_referral_payload .return_value =2
        mock_user_service .get_user_by_id .return_value =referrer
        mock_user_service .create_user .return_value =new_user
        mock_user_service .process_referral .return_value =(True ,"Referral processed successfully")

        message =MagicMock ()
        message .from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        )
        message .answer =AsyncMock ()
        message .bot =MagicMock ()
        message .bot .send_message =AsyncMock ()

        command =CommandStart (args ="referral_payload")

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        mock_user_service .decode_referral_payload .assert_called_once_with ("referral_payload")
        mock_user_service .process_referral .assert_called_once_with (
        session =mock_session ,
        inviter_id =2 ,
        invitee_id =1
        )

        message .bot .send_message .assert_called_once ()

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Welcome! You were referred by a friend"in call_args

    @pytest .mark .asyncio
    async def test_self_referral_prevention (self ,mock_user_service ,mock_session ):
        """Test prevention of self-referral."""
        mock_user_service .get_user .return_value =None
        mock_user_service .decode_referral_payload .return_value =12345

        new_user =User (
        id =1 ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        trial_expires =datetime .utcnow ()+timedelta (days =7 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =0 ,
        joined_at =datetime .utcnow (),
        created_at =datetime .utcnow (),
        updated_at =datetime .utcnow ()
        )
        mock_user_service .create_user .return_value =new_user

        message =MESSAGE .as_object (
        from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        ),
        text ="/start self_referral"
        )
        command =CommandStart (args ="self_referral")

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        mock_user_service .create_user .assert_called_once_with (
        session =mock_session ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        referrer_id =None
        )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "You cannot refer yourself!"in call_args

    @pytest .mark .asyncio
    async def test_existing_user_with_active_trial (self ,mock_user_service ,mock_session ,sample_user ):
        """Test existing user with active trial."""
        mock_user_service .get_user .return_value =sample_user

        message =MESSAGE .as_object (
        from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="Test",
        username ="testuser"
        ),
        text ="/start"
        )
        command =CommandStart ()

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        mock_user_service .create_user .assert_not_called ()

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Welcome back, Test!"in call_args
        assert "Your trial is active"in call_args
        assert "You've referred 2 users"in call_args

    @pytest .mark .asyncio
    async def test_existing_user_with_expired_trial (self ,mock_user_service ,mock_session ,expired_user ):
        """Test existing user with expired trial."""
        mock_user_service .get_user .return_value =expired_user

        message =MESSAGE .as_object (
        from_user =types .User (
        id =67890 ,
        is_bot =False ,
        first_name ="Expired",
        username ="expireduser"
        ),
        text ="/start"
        )
        command =CommandStart ()

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Welcome back, Expired!"in call_args
        assert "Your trial expired"in call_args
        assert "Upgrade to premium"in call_args

    @pytest .mark .asyncio
    async def test_invalid_referral_payload (self ,mock_user_service ,mock_session ):
        """Test handling of invalid referral payload."""
        mock_user_service .get_user .return_value =None
        mock_user_service .decode_referral_payload .return_value =None

        new_user =User (
        id =1 ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        trial_expires =datetime .utcnow ()+timedelta (days =7 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =0 ,
        joined_at =datetime .utcnow (),
        created_at =datetime .utcnow (),
        updated_at =datetime .utcnow ()
        )
        mock_user_service .create_user .return_value =new_user

        message =MESSAGE .as_object (
        from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        ),
        text ="/start invalid_payload"
        )
        command =CommandStart (args ="invalid_payload")

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        mock_user_service .create_user .assert_called_once_with (
        session =mock_session ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        referrer_id =None
        )

        mock_user_service .process_referral .assert_not_called ()

    @pytest .mark .asyncio
    async def test_referral_processing_failure (self ,mock_user_service ,mock_session ):
        """Test handling of referral processing failure."""
        referrer =User (
        id =2 ,
        tg_id =67890 ,
        username ="referrer",
        first_name ="Referrer",
        trial_expires =datetime .utcnow ()+timedelta (days =5 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =1 ,
        joined_at =datetime .utcnow ()-timedelta (days =2 ),
        created_at =datetime .utcnow ()-timedelta (days =2 ),
        updated_at =datetime .utcnow ()-timedelta (days =2 )
        )

        new_user =User (
        id =1 ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        trial_expires =datetime .utcnow ()+timedelta (days =7 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =0 ,
        joined_at =datetime .utcnow (),
        created_at =datetime .utcnow (),
        updated_at =datetime .utcnow ()
        )

        mock_user_service .get_user .return_value =None
        mock_user_service .decode_referral_payload .return_value =2
        mock_user_service .get_user_by_id .return_value =referrer
        mock_user_service .create_user .return_value =new_user
        mock_user_service .process_referral .return_value =(False ,"User was already referred")

        message =MESSAGE .as_object (
        from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        ),
        text ="/start referral_payload"
        )
        command =CommandStart (args ="referral_payload")

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Referral could not be processed: User was already referred"in call_args

    @pytest .mark .asyncio
    async def test_user_creation_error (self ,mock_user_service ,mock_session ):
        """Test handling of user creation error."""
        mock_user_service .get_user .return_value =None
        mock_user_service .create_user .side_effect =Exception ("Database error")

        message =MESSAGE .as_object (
        from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        ),
        text ="/start"
        )
        command =CommandStart ()

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Sorry, there was an error creating your account"in call_args

    @pytest .mark .asyncio
    async def test_referrer_notification_failure (self ,mock_user_service ,mock_session ):
        """Test handling of referrer notification failure."""
        referrer =User (
        id =2 ,
        tg_id =67890 ,
        username ="referrer",
        first_name ="Referrer",
        trial_expires =datetime .utcnow ()+timedelta (days =8 ),
        subscription_expires =None ,
        referred_by =None ,
        referrals_count =2 ,
        joined_at =datetime .utcnow ()-timedelta (days =2 ),
        created_at =datetime .utcnow ()-timedelta (days =2 ),
        updated_at =datetime .utcnow ()
        )

        new_user =User (
        id =1 ,
        tg_id =12345 ,
        username ="newuser",
        first_name ="New",
        trial_expires =datetime .utcnow ()+timedelta (days =7 ),
        subscription_expires =None ,
        referred_by =2 ,
        referrals_count =0 ,
        joined_at =datetime .utcnow (),
        created_at =datetime .utcnow (),
        updated_at =datetime .utcnow ()
        )

        mock_user_service .get_user .return_value =None
        mock_user_service .decode_referral_payload .return_value =2
        mock_user_service .get_user_by_id .return_value =referrer
        mock_user_service .create_user .return_value =new_user
        mock_user_service .process_referral .return_value =(True ,"Referral processed successfully")

        message =MESSAGE .as_object (
        from_user =types .User (
        id =12345 ,
        is_bot =False ,
        first_name ="New",
        username ="newuser"
        ),
        text ="/start referral_payload"
        )
        command =CommandStart (args ="referral_payload")

        message .bot .send_message .side_effect =Exception ("Bot blocked by user")

        with patch ('src.bot.handlers.start.get_session')as mock_get_session ,patch ('src.bot.handlers.start.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =mock_session

            await start_handler (message ,command )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Welcome! You were referred by a friend"in call_args 