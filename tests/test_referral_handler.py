"""Tests for referral command handlers."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from aiogram import types
from aiogram .filters import Command

from src .bot .handlers .referral import invite_handler ,referrals_stats_handler
from src .bot .services .user_service import UserService
from src .db .models import User

@pytest .fixture
def mock_message ():
    """Create a mock message."""
    message =MagicMock (spec =types .Message )
    message .from_user .id =12345
    message .from_user .first_name ="TestUser"
    message .answer =AsyncMock ()

    bot_info =MagicMock ()
    bot_info .username ="test_bot"
    message .bot .get_me =AsyncMock (return_value =bot_info )

    return message

@pytest .fixture
def mock_user ():
    """Create a mock user."""
    user =MagicMock (spec =User )
    user .id =1
    user .tg_id =12345
    user .username ="testuser"
    user .first_name ="TestUser"
    user .trial_expires =datetime .utcnow ()+timedelta (days =5 )
    user .subscription_expires =None
    user .referrals_count =3
    user .referred_by =None
    return user

@pytest .fixture
def mock_premium_user ():
    """Create a mock premium user."""
    user =MagicMock (spec =User )
    user .id =1
    user .tg_id =12345
    user .username ="testuser"
    user .first_name ="TestUser"
    user .trial_expires =datetime .utcnow ()-timedelta (days =1 )
    user .subscription_expires =datetime .utcnow ()+timedelta (days =30 )
    user .referrals_count =5
    user .referred_by =None
    return user

@pytest .fixture
def mock_expired_user ():
    """Create a mock expired user."""
    user =MagicMock (spec =User )
    user .id =1
    user .tg_id =12345
    user .username ="testuser"
    user .first_name ="TestUser"
    user .trial_expires =datetime .utcnow ()-timedelta (days =2 )
    user .subscription_expires =None
    user .referrals_count =1
    user .referred_by =None
    return user

class TestInviteHandler :
    """Test cases for /invite command handler."""

    @pytest .mark .asyncio
    async def test_invite_handler_success_trial_user (self ,mock_message ,mock_user ):
        """Test successful invite handler for trial user."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_user
            mock_service .generate_referral_link .return_value ="https://t.me/test_bot?start=abc123"
            mock_service .get_referral_stats .return_value ={
            'referrals_count':3 ,
            'trial_expires':mock_user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await invite_handler (mock_message )

            mock_service .get_user .assert_called_once ()
            mock_service .generate_referral_link .assert_called_once_with ("test_bot",mock_user .id )
            mock_service .get_referral_stats .assert_called_once ()

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Your Referral Link"in response_text
            assert "https://t.me/test_bot?start=abc123"in response_text
            assert "Referred users: **3**"in response_text
            assert "Trial: 5 days left"in response_text
            assert "3 bonus days"in response_text
            assert "7-day trial"in response_text

    @pytest .mark .asyncio
    async def test_invite_handler_success_premium_user (self ,mock_message ,mock_premium_user ):
        """Test successful invite handler for premium user."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_premium_user
            mock_service .generate_referral_link .return_value ="https://t.me/test_bot?start=xyz789"
            mock_service .get_referral_stats .return_value ={
            'referrals_count':5 ,
            'trial_expires':mock_premium_user .trial_expires ,
            'subscription_expires':mock_premium_user .subscription_expires
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await invite_handler (mock_message )

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Your Referral Link"in response_text
            assert "https://t.me/test_bot?start=xyz789"in response_text
            assert "Referred users: **5**"in response_text
            assert "Premium until"in response_text

    @pytest .mark .asyncio
    async def test_invite_handler_success_expired_user (self ,mock_message ,mock_expired_user ):
        """Test successful invite handler for expired user."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_expired_user
            mock_service .generate_referral_link .return_value ="https://t.me/test_bot?start=def456"
            mock_service .get_referral_stats .return_value ={
            'referrals_count':1 ,
            'trial_expires':mock_expired_user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await invite_handler (mock_message )

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Your Referral Link"in response_text
            assert "https://t.me/test_bot?start=def456"in response_text
            assert "Referred users: **1**"in response_text
            assert "Trial expired on"in response_text

    @pytest .mark .asyncio
    async def test_invite_handler_user_not_found (self ,mock_message ):
        """Test invite handler when user is not found."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =None

            await invite_handler (mock_message )

            mock_message .answer .assert_called_once_with (
            "❌ You need to start the bot first. Use /start to create your account."
            )

    @pytest .mark .asyncio
    async def test_invite_handler_no_first_name (self ,mock_message ,mock_user ):
        """Test invite handler when user has no first name."""
        mock_message .from_user .first_name =None

        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_user
            mock_service .generate_referral_link .return_value ="https://t.me/test_bot?start=abc123"
            mock_service .get_referral_stats .return_value ={
            'referrals_count':3 ,
            'trial_expires':mock_user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await invite_handler (mock_message )

            mock_message .answer .assert_called_once ()

class TestReferralsStatsHandler :
    """Test cases for /referrals command handler."""

    @pytest .mark .asyncio
    async def test_referrals_stats_handler_success_trial_user (self ,mock_message ,mock_user ):
        """Test successful referrals stats handler for trial user."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_user
            mock_service .get_referral_stats .return_value ={
            'referrals_count':3 ,
            'trial_expires':mock_user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await referrals_stats_handler (mock_message )

            mock_service .get_user .assert_called_once ()
            mock_service .get_referral_stats .assert_called_once ()

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Referral Statistics for TestUser"in response_text
            assert "Trial User"in response_text
            assert "Total referrals: **3**"in response_text
            assert "Bonus days earned: **9** days"in response_text
            assert "Bonus per referral: **3** days"in response_text
            assert "7-day trial"in response_text
            assert "3 bonus days"in response_text

    @pytest .mark .asyncio
    async def test_referrals_stats_handler_success_premium_user (self ,mock_message ,mock_premium_user ):
        """Test successful referrals stats handler for premium user."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_premium_user
            mock_service .get_referral_stats .return_value ={
            'referrals_count':5 ,
            'trial_expires':mock_premium_user .trial_expires ,
            'subscription_expires':mock_premium_user .subscription_expires
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await referrals_stats_handler (mock_message )

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Referral Statistics for TestUser"in response_text
            assert "Premium Subscriber"in response_text
            assert "Total referrals: **5**"in response_text
            assert "Bonus days earned: **15** days"in response_text

    @pytest .mark .asyncio
    async def test_referrals_stats_handler_success_expired_user (self ,mock_message ,mock_expired_user ):
        """Test successful referrals stats handler for expired user."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_expired_user
            mock_service .get_referral_stats .return_value ={
            'referrals_count':1 ,
            'trial_expires':mock_expired_user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await referrals_stats_handler (mock_message )

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Referral Statistics for TestUser"in response_text
            assert "Trial Expired"in response_text
            assert "Total referrals: **1**"in response_text
            assert "Bonus days earned: **3** days"in response_text

    @pytest .mark .asyncio
    async def test_referrals_stats_handler_user_not_found (self ,mock_message ):
        """Test referrals stats handler when user is not found."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =None

            await referrals_stats_handler (mock_message )

            mock_message .answer .assert_called_once_with (
            "❌ You need to start the bot first. Use /start to create your account."
            )

    @pytest .mark .asyncio
    async def test_referrals_stats_handler_zero_referrals (self ,mock_message ):
        """Test referrals stats handler with zero referrals."""

        user =MagicMock (spec =User )
        user .id =1
        user .tg_id =12345
        user .username ="testuser"
        user .first_name ="TestUser"
        user .trial_expires =datetime .utcnow ()+timedelta (days =5 )
        user .subscription_expires =None
        user .referrals_count =0
        user .referred_by =None

        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =user
            mock_service .get_referral_stats .return_value ={
            'referrals_count':0 ,
            'trial_expires':user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await referrals_stats_handler (mock_message )

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]

            assert "Total referrals: **0**"in response_text
            assert "Bonus days earned: **0** days"in response_text

class TestReferralLinkGeneration :
    """Test cases for referral link generation functionality."""

    @pytest .mark .asyncio
    async def test_referral_link_format (self ,mock_message ,mock_user ):
        """Test that referral link has correct format."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_user
            mock_service .generate_referral_link .return_value ="https://t.me/test_bot?start=abc123def456"
            mock_service .get_referral_stats .return_value ={
            'referrals_count':0 ,
            'trial_expires':mock_user .trial_expires ,
            'subscription_expires':None
            }
            mock_service .referral_bonus_days =3
            mock_service .default_trial_days =7

            await invite_handler (mock_message )

            mock_service .generate_referral_link .assert_called_once_with ("test_bot",mock_user .id )

            mock_message .answer .assert_called_once ()
            response_text =mock_message .answer .call_args [0 ][0 ]
            assert "https://t.me/test_bot?start=abc123def456"in response_text

    @pytest .mark .asyncio
    async def test_bot_username_retrieval (self ,mock_message ,mock_user ):
        """Test that bot username is correctly retrieved."""
        with patch ('src.bot.handlers.referral.get_db_session')as mock_session ,patch ('src.bot.handlers.referral.user_service')as mock_service :

            mock_session .return_value .__aenter__ .return_value =AsyncMock ()
            mock_service .get_user .return_value =mock_user
            mock_service .generate_referral_link .return_value ="https://t.me/my_awesome_bot?start=token123"
            mock_service .get_referral_stats .return_value ={
            'referrals_count':0 ,
            'trial_expires':mock_user .trial_expires ,
            'subscription_expires':None
            }

            bot_info =MagicMock ()
            bot_info .username ="my_awesome_bot"
            mock_message .bot .get_me =AsyncMock (return_value =bot_info )

            await invite_handler (mock_message )

            mock_message .bot .get_me .assert_called_once ()

            mock_service .generate_referral_link .assert_called_once_with ("my_awesome_bot",mock_user .id )