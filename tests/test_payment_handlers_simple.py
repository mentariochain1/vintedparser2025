"""Simple tests for payment handlers."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from aiogram import types

from src .bot .handlers .payment import payment_command ,subscription_status_command
from src .db .models import User

@pytest .fixture
def mock_user ():
    """Mock user with active trial."""
    return User (
    id =1 ,
    tg_id =123456789 ,
    username ="testuser",
    first_name ="Test",
    trial_expires =datetime .utcnow ()+timedelta (days =5 ),
    subscription_expires =None ,
    referred_by =None ,
    referrals_count =0 ,
    joined_at =datetime .utcnow (),
    created_at =datetime .utcnow (),
    updated_at =datetime .utcnow ()
    )

@pytest .fixture
def mock_expired_user ():
    """Mock user with expired trial."""
    return User (
    id =1 ,
    tg_id =123456789 ,
    username ="testuser",
    first_name ="Test",
    trial_expires =datetime .utcnow ()-timedelta (days =1 ),
    subscription_expires =None ,
    referred_by =None ,
    referrals_count =0 ,
    joined_at =datetime .utcnow ()-timedelta (days =8 ),
    created_at =datetime .utcnow ()-timedelta (days =8 ),
    updated_at =datetime .utcnow ()-timedelta (days =8 )
    )

@pytest .fixture
def mock_premium_user ():
    """Mock user with active premium subscription."""
    return User (
    id =1 ,
    tg_id =123456789 ,
    username ="testuser",
    first_name ="Test",
    trial_expires =datetime .utcnow ()-timedelta (days =1 ),
    subscription_expires =datetime .utcnow ()+timedelta (days =30 ),
    referred_by =None ,
    referrals_count =2 ,
    joined_at =datetime .utcnow ()-timedelta (days =8 ),
    created_at =datetime .utcnow ()-timedelta (days =8 ),
    updated_at =datetime .utcnow ()
    )

class TestPaymentCommand :
    """Test /pay command handler."""

    @pytest .mark .asyncio
    async def test_pay_command_trial_user (self ,mock_user ):
        """Test /pay command for user with active trial."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =mock_user

            await payment_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Trial Active"in call_args
        assert "Upgrade to Premium"in call_args

    @pytest .mark .asyncio
    async def test_pay_command_expired_user (self ,mock_expired_user ):
        """Test /pay command for user with expired trial."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =mock_expired_user

            await payment_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Expired"in call_args
        assert "Subscribe to Premium"in call_args

    @pytest .mark .asyncio
    async def test_pay_command_premium_user (self ,mock_premium_user ):
        """Test /pay command for user with active premium subscription."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =mock_premium_user

            await payment_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Premium Active"in call_args
        assert "extend your subscription"in call_args

    @pytest .mark .asyncio
    async def test_pay_command_no_user ():
        """Test /pay command for non-existent user."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =None

            await payment_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Please start the bot first"in call_args

class TestSubscriptionCommand :
    """Test /subscription command handler."""

    @pytest .mark .asyncio
    async def test_subscription_command_trial_user (self ,mock_user ):
        """Test /subscription command for user with active trial."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =mock_user

            await subscription_status_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Trial Period"in call_args
        assert "Active"in call_args
        assert "Days Left"in call_args

    @pytest .mark .asyncio
    async def test_subscription_command_premium_user (self ,mock_premium_user ):
        """Test /subscription command for premium user."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =mock_premium_user

            await subscription_status_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Premium Subscription"in call_args
        assert "Active"in call_args
        assert "full access"in call_args

    @pytest .mark .asyncio
    async def test_subscription_command_expired_user (self ,mock_expired_user ):
        """Test /subscription command for expired user."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =mock_expired_user

            await subscription_status_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Access Expired"in call_args
        assert "Expired"in call_args
        assert "/pay to subscribe"in call_args

    @pytest .mark .asyncio
    async def test_subscription_command_no_user ():
        """Test /subscription command for non-existent user."""

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service')as mock_user_service :

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()
            mock_user_service .get_user .return_value =None

            await subscription_status_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Please start the bot first"in call_args

class TestPaymentService :
    """Test payment service integration."""

    @pytest .mark .asyncio
    async def test_payment_service_pricing ():
        """Test payment service pricing calculation."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        monthly =payment_service .calculate_subscription_price (30 )
        assert monthly ['days']==30
        assert monthly ['discount']==0.0
        assert monthly ['currency']=='RUB'

        quarterly =payment_service .calculate_subscription_price (90 )
        assert quarterly ['days']==90
        assert quarterly ['discount']==0.10

        yearly =payment_service .calculate_subscription_price (365 )
        assert yearly ['days']==365
        assert yearly ['discount']==0.20

    @pytest .mark .asyncio
    async def test_payment_service_health_check ():
        """Test payment service health check."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        health =await payment_service .health_check ()
        assert isinstance (health ,bool )