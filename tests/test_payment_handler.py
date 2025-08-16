"""Tests for payment handlers."""

import json
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

import pytest
from aiogram import types
from aiogram .filters import Command

from src .bot .handlers .payment import payment_command ,handle_payment_callback ,handle_payment_confirmation ,handle_payment_status_check ,subscription_status_command
from src .bot .services .payment_service import PaymentService
from src .bot .services .user_service import UserService

@pytest .fixture
def mock_user ():
    """Mock user for testing."""
    user =MagicMock ()
    user .id =1
    user .tg_id =123456789
    user .username ="testuser"
    user .first_name ="Test"
    user .trial_expires =datetime .utcnow ()+timedelta (days =5 )
    user .subscription_expires =None
    user .referrals_count =0
    return user

@pytest .fixture
def mock_expired_user ():
    """Mock expired user for testing."""
    user =MagicMock ()
    user .id =1
    user .tg_id =123456789
    user .username ="testuser"
    user .first_name ="Test"
    user .trial_expires =datetime .utcnow ()-timedelta (days =1 )
    user .subscription_expires =None
    user .referrals_count =0
    return user

@pytest .fixture
def mock_premium_user ():
    """Mock premium user for testing."""
    user =MagicMock ()
    user .id =1
    user .tg_id =123456789
    user .username ="testuser"
    user .first_name ="Test"
    user .trial_expires =datetime .utcnow ()-timedelta (days =1 )
    user .subscription_expires =datetime .utcnow ()+timedelta (days =30 )
    user .referrals_count =2
    return user

@pytest .fixture
def mock_payment_service ():
    """Mock payment service."""
    with patch ('src.bot.handlers.payment.payment_service')as mock :
        mock .calculate_subscription_price .return_value ={
        'days':30 ,
        'base_price':299.0 ,
        'discount':0.0 ,
        'final_price':299.0 ,
        'currency':'RUB',
        'price_per_day':9.97
        }
        mock .create_payment .return_value ={
        'payment_id':'test_payment_123',
        'confirmation_url':'https://yookassa.ru/checkout/test_payment_123',
        'status':'pending'
        }
        mock .get_payment_status .return_value ={
        'payment_id':'test_payment_123',
        'status':'succeeded',
        'amount':'299.00',
        'currency':'RUB',
        'created_at':'2025-01-01T00:00:00Z',
        'metadata':{'user_id':'123456789'}
        }
        yield mock

@pytest .fixture
def mock_user_service ():
    """Mock user service."""
    with patch ('src.bot.handlers.payment.user_service')as mock :
        yield mock

class TestPaymentCommand :
    """Test /pay command handler."""

    @pytest .mark .asyncio
    async def test_pay_command_trial_user (self ,mock_user ,mock_user_service ):
        """Test /pay command for user with active trial."""
        mock_user_service .get_user .return_value =mock_user

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()

            await payment_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Trial Active"in call_args
        assert "Upgrade to Premium"in call_args

    @pytest .mark .asyncio
    async def test_pay_command_expired_user (self ,mock_expired_user ,mock_user_service ):
        """Test /pay command for user with expired trial."""
        mock_user_service .get_user .return_value =mock_expired_user

        message =MagicMock ()
        message .from_user =types .User (
        id =123456789 ,
        is_bot =False ,
        first_name ="Test"
        )
        message .answer =AsyncMock ()

        with patch ('src.bot.handlers.payment.get_db_session')as mock_get_session ,patch ('src.bot.handlers.payment.user_service',mock_user_service ):

            mock_get_session .return_value .__aenter__ .return_value =MagicMock ()

            await payment_command (message )

        message .answer .assert_called_once ()
        call_args =message .answer .call_args [0 ][0 ]
        assert "Expired"in call_args
        assert "Subscribe to Premium"in call_args

    @pytest .mark .asyncio
    async def test_pay_command_premium_user (self ,mock_premium_user ,mock_user_service ):
        """Test /pay command for user with active premium subscription."""
        mock_user_service .get_user .return_value =mock_premium_user

        bot =MockedBot (router )
        request =MessageHandler (router )

        calls =await bot .query (
        request ,
        message =MESSAGE .as_object (text ="/pay",from_user =User (id =123456789 ,is_bot =False ,first_name ="Test"))
        )

        answer =calls .send_message .fetchone ()
        assert "Premium Active"in answer .text
        assert "extend your subscription"in answer .text
        assert answer .reply_markup is not None

    @pytest .mark .asyncio
    async def test_pay_command_no_user (self ,mock_user_service ):
        """Test /pay command for non-existent user."""
        mock_user_service .get_user .return_value =None

        bot =MockedBot (router )
        request =MessageHandler (router )

        calls =await bot .query (
        request ,
        message =MESSAGE .as_object (text ="/pay",from_user =User (id =123456789 ,is_bot =False ,first_name ="Test"))
        )

        answer =calls .send_message .fetchone ()
        assert "Please start the bot first"in answer .text

class TestPaymentCallbacks :
    """Test payment callback handlers."""

    @pytest .mark .asyncio
    async def test_payment_option_callback (self ,mock_payment_service ):
        """Test payment option selection callback."""
        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_monthly",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Confirmation"in edit .text
        assert "Monthly Premium Subscription"in edit .text
        assert "299 RUB"in edit .text

    @pytest .mark .asyncio
    async def test_quarterly_payment_callback (self ,mock_payment_service ):
        """Test quarterly payment option callback."""
        mock_payment_service .calculate_subscription_price .return_value ={
        'days':90 ,
        'base_price':897.0 ,
        'discount':0.10 ,
        'final_price':807.3 ,
        'currency':'RUB',
        'price_per_day':9.97
        }

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_quarterly",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Confirmation"in edit .text
        assert "Quarterly Premium Subscription"in edit .text
        assert "807 RUB"in edit .text
        assert "Discount"in edit .text

    @pytest .mark .asyncio
    async def test_yearly_payment_callback (self ,mock_payment_service ):
        """Test yearly payment option callback."""
        mock_payment_service .calculate_subscription_price .return_value ={
        'days':365 ,
        'base_price':3638.3 ,
        'discount':0.20 ,
        'final_price':2910.6 ,
        'currency':'RUB',
        'price_per_day':9.97
        }

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_yearly",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Confirmation"in edit .text
        assert "Yearly Premium Subscription"in edit .text
        assert "2911 RUB"in edit .text
        assert "Discount"in edit .text

    @pytest .mark .asyncio
    async def test_cancel_payment_callback (self ):
        """Test payment cancellation callback."""
        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_cancel",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment cancelled"in edit .text

class TestPaymentConfirmation :
    """Test payment confirmation handlers."""

    @pytest .mark .asyncio
    async def test_payment_confirmation_success (self ,mock_user ,mock_user_service ,mock_payment_service ):
        """Test successful payment confirmation."""
        mock_user_service .get_user .return_value =mock_user

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="confirm_pay_30",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Created Successfully"in edit .text
        assert "test_payment_123"in edit .text
        assert edit .reply_markup is not None

        mock_payment_service .create_payment .assert_called_once ()

    @pytest .mark .asyncio
    async def test_payment_confirmation_no_user (self ,mock_user_service ,mock_payment_service ):
        """Test payment confirmation for non-existent user."""
        mock_user_service .get_user .return_value =None

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="confirm_pay_30",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "User not found"in edit .text

        mock_payment_service .create_payment .assert_not_called ()

    @pytest .mark .asyncio
    async def test_payment_confirmation_service_error (self ,mock_user ,mock_user_service ,mock_payment_service ):
        """Test payment confirmation with service error."""
        mock_user_service .get_user .return_value =mock_user
        mock_payment_service .create_payment .side_effect =Exception ("Payment service error")

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="confirm_pay_30",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Failed to create payment"in edit .text

class TestPaymentStatusCheck :
    """Test payment status check handlers."""

    @pytest .mark .asyncio
    async def test_check_payment_status_success (self ,mock_payment_service ):
        """Test checking successful payment status."""
        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="check_payment_test_payment_123",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Successful"in edit .text
        assert "test_payment_123"in edit .text
        assert "subscription has been activated"in edit .text

    @pytest .mark .asyncio
    async def test_check_payment_status_pending (self ,mock_payment_service ):
        """Test checking pending payment status."""
        mock_payment_service .get_payment_status .return_value ={
        'payment_id':'test_payment_123',
        'status':'pending',
        'amount':'299.00',
        'currency':'RUB',
        'created_at':'2025-01-01T00:00:00Z',
        'metadata':{'user_id':'123456789'}
        }

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="check_payment_test_payment_123",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Pending"in edit .text
        assert "being processed"in edit .text
        assert "Refresh Status"in edit .text

    @pytest .mark .asyncio
    async def test_check_payment_status_cancelled (self ,mock_payment_service ):
        """Test checking cancelled payment status."""
        mock_payment_service .get_payment_status .return_value ={
        'payment_id':'test_payment_123',
        'status':'canceled',
        'amount':'299.00',
        'currency':'RUB',
        'created_at':'2025-01-01T00:00:00Z',
        'metadata':{'user_id':'123456789'}
        }

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="check_payment_test_payment_123",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Payment Cancelled"in edit .text
        assert "was cancelled"in edit .text

    @pytest .mark .asyncio
    async def test_check_payment_status_not_found (self ,mock_payment_service ):
        """Test checking status for non-existent payment."""
        mock_payment_service .get_payment_status .return_value =None

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="check_payment_test_payment_123",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called

        answer =calls .answer_callback_query .fetchone ()
        assert answer .show_alert is True
        assert "Payment not found"in answer .text

    @pytest .mark .asyncio
    async def test_check_payment_status_wrong_user (self ,mock_payment_service ):
        """Test checking payment status for wrong user."""
        mock_payment_service .get_payment_status .return_value ={
        'payment_id':'test_payment_123',
        'status':'succeeded',
        'amount':'299.00',
        'currency':'RUB',
        'created_at':'2025-01-01T00:00:00Z',
        'metadata':{'user_id':'987654321'}
        }

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="check_payment_test_payment_123",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called

        answer =calls .answer_callback_query .fetchone ()
        assert answer .show_alert is True
        assert "Payment not found"in answer .text

class TestSubscriptionCommand :
    """Test /subscription command handler."""

    @pytest .mark .asyncio
    async def test_subscription_command_trial_user (self ,mock_user ,mock_user_service ):
        """Test /subscription command for user with active trial."""
        mock_user_service .get_user .return_value =mock_user

        bot =MockedBot (router )
        request =MessageHandler (router )

        calls =await bot .query (
        request ,
        message =MESSAGE .as_object (text ="/subscription",from_user =User (id =123456789 ,is_bot =False ,first_name ="Test"))
        )

        answer =calls .send_message .fetchone ()
        assert "Trial Period"in answer .text
        assert "Active"in answer .text
        assert "Days Left"in answer .text
        assert "/pay to upgrade"in answer .text

    @pytest .mark .asyncio
    async def test_subscription_command_premium_user (self ,mock_premium_user ,mock_user_service ):
        """Test /subscription command for premium user."""
        mock_user_service .get_user .return_value =mock_premium_user

        bot =MockedBot (router )
        request =MessageHandler (router )

        calls =await bot .query (
        request ,
        message =MESSAGE .as_object (text ="/subscription",from_user =User (id =123456789 ,is_bot =False ,first_name ="Test"))
        )

        answer =calls .send_message .fetchone ()
        assert "Premium Subscription"in answer .text
        assert "Active"in answer .text
        assert "full access"in answer .text

    @pytest .mark .asyncio
    async def test_subscription_command_expired_user (self ,mock_expired_user ,mock_user_service ):
        """Test /subscription command for expired user."""
        mock_user_service .get_user .return_value =mock_expired_user

        bot =MockedBot (router )
        request =MessageHandler (router )

        calls =await bot .query (
        request ,
        message =MESSAGE .as_object (text ="/subscription",from_user =User (id =123456789 ,is_bot =False ,first_name ="Test"))
        )

        answer =calls .send_message .fetchone ()
        assert "Access Expired"in answer .text
        assert "Expired"in answer .text
        assert "/pay to subscribe"in answer .text

    @pytest .mark .asyncio
    async def test_subscription_command_no_user (self ,mock_user_service ):
        """Test /subscription command for non-existent user."""
        mock_user_service .get_user .return_value =None

        bot =MockedBot (router )
        request =MessageHandler (router )

        calls =await bot .query (
        request ,
        message =MESSAGE .as_object (text ="/subscription",from_user =User (id =123456789 ,is_bot =False ,first_name ="Test"))
        )

        answer =calls .send_message .fetchone ()
        assert "Please start the bot first"in answer .text

class TestPaymentStatusCallback :
    """Test payment status callback handler."""

    @pytest .mark .asyncio
    async def test_payment_status_callback_trial_user (self ,mock_user ,mock_user_service ):
        """Test payment status callback for trial user."""
        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_status",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Trial Period Active"in edit .text
        assert "Upgrade to Premium"in edit .text

    @pytest .mark .asyncio
    async def test_payment_status_callback_premium_user (self ,mock_premium_user ,mock_user_service ):
        """Test payment status callback for premium user."""
        mock_user_service .get_user .return_value =mock_premium_user

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_status",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Premium Subscription Active"in edit .text
        assert "full access"in edit .text

    @pytest .mark .asyncio
    async def test_payment_status_callback_expired_user (self ,mock_expired_user ,mock_user_service ):
        """Test payment status callback for expired user."""
        mock_user_service .get_user .return_value =mock_expired_user

        bot =MockedBot (router )
        request =CallbackQueryHandler (router )

        callback =CALLBACK_QUERY .as_object (
        data ="pay_status",
        from_user =User (id =123456789 ,is_bot =False ,first_name ="Test")
        )

        calls =await bot .query (request ,callback_query =callback )

        assert calls .answer_callback_query .called
        edit =calls .edit_message_text .fetchone ()
        assert "Access Expired"in edit .text
        assert "Subscribe to Premium"in edit .text 