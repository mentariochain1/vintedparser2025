"""Unit tests for payment functionality."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from src .bot .services .payment_service import PaymentService

class TestPaymentService :
    """Test payment service functionality."""

    def test_calculate_subscription_price_monthly (self ):
        """Test monthly subscription pricing."""
        payment_service =PaymentService ()

        pricing =payment_service .calculate_subscription_price (30 )

        assert pricing ['days']==30
        assert pricing ['discount']==0.0
        assert pricing ['currency']=='RUB'
        assert pricing ['final_price']==299.0

    def test_calculate_subscription_price_quarterly (self ):
        """Test quarterly subscription pricing with discount."""
        payment_service =PaymentService ()

        pricing =payment_service .calculate_subscription_price (90 )

        assert pricing ['days']==90
        assert pricing ['discount']==0.10
        assert pricing ['currency']=='RUB'

        assert pricing ['final_price']<pricing ['base_price']

    def test_calculate_subscription_price_yearly (self ):
        """Test yearly subscription pricing with bigger discount."""
        payment_service =PaymentService ()

        pricing =payment_service .calculate_subscription_price (365 )

        assert pricing ['days']==365
        assert pricing ['discount']==0.20
        assert pricing ['currency']=='RUB'

        assert pricing ['final_price']<pricing ['base_price']

    @pytest .mark .asyncio
    async def test_health_check (self ):
        """Test payment service health check."""
        payment_service =PaymentService ()

        health =await payment_service .health_check ()
        assert isinstance (health ,bool )

    @pytest .mark .asyncio
    async def test_create_payment_success (self ):
        """Test successful payment creation."""
        payment_service =PaymentService ()

        mock_session =AsyncMock ()

        with patch ('yookassa.Payment.create')as mock_create ,patch ('src.bot.services.payment_service.PaymentCRUD')as mock_crud :

            mock_payment =MagicMock ()
            mock_payment .id ="test_payment_123"
            mock_payment .status ="pending"
            mock_payment .confirmation .confirmation_url ="https://yookassa.ru/checkout/test"
            mock_create .return_value =mock_payment

            mock_crud .create .return_value =None

            result =await payment_service .create_payment (
            session =mock_session ,
            user_id =1 ,
            amount =299.0 ,
            currency ="RUB",
            description ="Test payment"
            )

            assert result ["payment_id"]=="test_payment_123"
            assert result ["status"]=="pending"
            assert "yookassa.ru"in result ["confirmation_url"]

            mock_create .assert_called_once ()

            mock_crud .create .assert_called_once ()

    @pytest .mark .asyncio
    async def test_get_payment_status_success (self ):
        """Test getting payment status."""
        payment_service =PaymentService ()

        with patch ('yookassa.Payment.find_one')as mock_find :

            mock_payment =MagicMock ()
            mock_payment .id ="test_payment_123"
            mock_payment .status ="succeeded"
            mock_payment .amount .value ="299.00"
            mock_payment .amount .currency ="RUB"
            mock_payment .created_at ="2025-01-01T00:00:00Z"
            mock_payment .metadata ={"user_id":"123"}
            mock_find .return_value =mock_payment

            result =await payment_service .get_payment_status ("test_payment_123")

            assert result ["payment_id"]=="test_payment_123"
            assert result ["status"]=="succeeded"
            assert result ["amount"]=="299.00"
            assert result ["currency"]=="RUB"
            assert result ["metadata"]["user_id"]=="123"

    @pytest .mark .asyncio
    async def test_get_payment_status_not_found (self ):
        """Test getting status for non-existent payment."""
        payment_service =PaymentService ()

        with patch ('yookassa.Payment.find_one')as mock_find :
            mock_find .return_value =None

            result =await payment_service .get_payment_status ("nonexistent")

            assert result is None

    def test_verify_webhook_signature_valid (self ):
        """Test webhook signature verification with valid signature."""
        payment_service =PaymentService ()

        payload =b'{"event": "payment.succeeded"}'
        timestamp ="1640995200"

        import hmac
        import hashlib
        message =payload +timestamp .encode ()
        expected_signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        result =payment_service .verify_webhook_signature (
        payload ,expected_signature ,timestamp
        )

        assert result is True

    def test_verify_webhook_signature_invalid (self ):
        """Test webhook signature verification with invalid signature."""
        payment_service =PaymentService ()

        payload =b'{"event": "payment.succeeded"}'
        timestamp ="1640995200"
        invalid_signature ="invalid_signature"

        result =payment_service .verify_webhook_signature (
        payload ,invalid_signature ,timestamp
        )

        assert result is False

    def test_verify_webhook_signature_old_timestamp (self ):
        """Test webhook signature verification with old timestamp."""
        payment_service =PaymentService ()

        payload =b'{"event": "payment.succeeded"}'
        old_timestamp ="1640995200"

        import hmac
        import hashlib
        message =payload +old_timestamp .encode ()
        signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        result =payment_service .verify_webhook_signature (
        payload ,signature ,old_timestamp ,max_age =300
        )

        assert result is False

    @pytest .mark .asyncio
    async def test_process_webhook_success (self ):
        """Test successful webhook processing."""
        payment_service =PaymentService ()

        mock_session =AsyncMock ()
        payload =b'{"event": "payment.succeeded", "object": {"id": "test_123", "status": "succeeded"}}'
        signature ="valid_signature"
        timestamp =str (int (datetime .utcnow ().timestamp ()))

        with patch .object (payment_service ,'verify_webhook_signature',return_value =True ),patch ('src.bot.services.payment_service.PaymentCRUD')as mock_crud ,patch .object (payment_service ,'_process_successful_payment',return_value =True ):

            mock_payment =MagicMock ()
            mock_payment .user_id =1
            mock_crud .update_status .return_value =mock_payment

            success ,message =await payment_service .process_webhook (
            session =mock_session ,
            payload =payload ,
            signature =signature ,
            timestamp =timestamp
            )

            assert success is True
            assert "successfully"in message

    @pytest .mark .asyncio
    async def test_process_webhook_invalid_signature (self ):
        """Test webhook processing with invalid signature."""
        payment_service =PaymentService ()

        mock_session =AsyncMock ()
        payload =b'{"event": "payment.succeeded"}'
        signature ="invalid_signature"
        timestamp =str (int (datetime .utcnow ().timestamp ()))

        with patch .object (payment_service ,'verify_webhook_signature',return_value =False ):
            success ,message =await payment_service .process_webhook (
            session =mock_session ,
            payload =payload ,
            signature =signature ,
            timestamp =timestamp
            )

            assert success is False
            assert "Invalid signature"in message

    @pytest .mark .asyncio
    async def test_process_successful_payment (self ):
        """Test processing successful payment."""
        payment_service =PaymentService ()

        mock_session =AsyncMock ()
        mock_payment =MagicMock ()
        mock_payment .user_id =1

        with patch ('src.bot.services.payment_service.UserCRUD')as mock_user_crud :
            mock_user =MagicMock ()
            mock_user .id =1
            mock_user .subscription_expires =None
            mock_user_crud .get_by_id .return_value =mock_user

            result =await payment_service ._process_successful_payment (
            session =mock_session ,
            payment =mock_payment
            )

            assert result is True

            assert mock_user .subscription_expires is not None

    @pytest .mark .asyncio
    async def test_process_successful_payment_user_not_found (self ):
        """Test processing successful payment for non-existent user."""
        payment_service =PaymentService ()

        mock_session =AsyncMock ()
        mock_payment =MagicMock ()
        mock_payment .user_id =999

        with patch ('src.bot.services.payment_service.UserCRUD')as mock_user_crud :
            mock_user_crud .get_by_id .return_value =None

            result =await payment_service ._process_successful_payment (
            session =mock_session ,
            payment =mock_payment
            )

            assert result is False

    @pytest .mark .asyncio
    async def test_cancel_payment_success (self ):
        """Test successful payment cancellation."""
        payment_service =PaymentService ()

        with patch ('yookassa.Payment.cancel')as mock_cancel :
            mock_payment =MagicMock ()
            mock_payment .status ="canceled"
            mock_cancel .return_value =mock_payment

            success ,message =await payment_service .cancel_payment ("test_payment_123")

            assert success is True
            assert "cancelled"in message
            mock_cancel .assert_called_once ()

    @pytest .mark .asyncio
    async def test_cancel_payment_failure (self ):
        """Test payment cancellation failure."""
        payment_service =PaymentService ()

        with patch ('yookassa.Payment.cancel')as mock_cancel :
            mock_cancel .side_effect =Exception ("Payment cannot be cancelled")

            success ,message =await payment_service .cancel_payment ("test_payment_123")

            assert success is False
            assert "Failed to cancel payment"in message 