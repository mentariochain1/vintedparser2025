"""Comprehensive tests for PaymentService."""

import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.services.payment_service import PaymentService
from src.db.models import Payment, User

class MockYooKassaPayment :
    """Mock YooKassa payment for testing."""

    def __init__ (self ,payment_id :str ="test_payment_id",status :str ="pending"):
        self .id =payment_id
        self .status =status
        self .amount =MagicMock ()
        self .amount .value ="299.00"
        self .amount .currency ="RUB"
        self .created_at =datetime .utcnow ().isoformat ()
        self .confirmation =MagicMock ()
        self .confirmation .confirmation_url =f"https://yookassa.ru/checkout/{payment_id }"
        self .metadata ={"user_id":"123"}

class TestPaymentService:
    """Comprehensive test cases for PaymentService."""

    @pytest.fixture
    def payment_service(self):
        """Create PaymentService instance for testing."""
        with patch("src.bot.services.payment_service.Configuration.configure"):
            return PaymentService()

    @pytest .mark .asyncio
    async def test_create_payment_success (self ,payment_service ,mock_session ):
        """Test successful payment creation."""
        mock_payment =MockYooKassaPayment ()

        with patch ("src.bot.services.payment_service.Payment.create")as mock_create ,patch ("src.bot.services.payment_service.PaymentCRUD.create")as mock_crud_create :

            mock_create .return_value =mock_payment
            mock_crud_create .return_value =MagicMock ()

            result =await payment_service .create_payment (
            session =mock_session ,
            user_id =123 ,
            amount =299.0 ,
            description ="Test payment"
            )

            assert result ["payment_id"]=="test_payment_id"
            assert result ["status"]=="pending"
            assert "confirmation_url"in result

            mock_create .assert_called_once ()
            mock_crud_create .assert_called_once ()
            mock_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_create_payment_failure (self ,payment_service ,mock_session ):
        """Test payment creation failure."""
        with patch ("src.bot.services.payment_service.Payment.create")as mock_create :
            mock_create .side_effect =Exception ("YooKassa error")

            with pytest .raises (Exception ,match ="YooKassa error"):
                await payment_service .create_payment (
                session =mock_session ,
                user_id =123 ,
                amount =299.0
                )

            mock_session .rollback .assert_called_once ()

    @pytest .mark .asyncio
    async def test_get_payment_status_success (self ,payment_service ):
        """Test successful payment status retrieval."""
        mock_payment =MockYooKassaPayment (status ="succeeded")

        with patch ("src.bot.services.payment_service.Payment.find_one")as mock_find :
            mock_find .return_value =mock_payment

            result =await payment_service .get_payment_status ("test_payment_id")

            assert result is not None
            assert result ["payment_id"]=="test_payment_id"
            assert result ["status"]=="succeeded"
            assert result ["amount"]=="299.00"
            assert result ["currency"]=="RUB"

    @pytest .mark .asyncio
    async def test_get_payment_status_not_found (self ,payment_service ):
        """Test payment status retrieval when payment not found."""
        with patch ("src.bot.services.payment_service.Payment.find_one")as mock_find :
            mock_find .return_value =None

            result =await payment_service .get_payment_status ("nonexistent_id")

            assert result is None

    @pytest .mark .asyncio
    async def test_get_payment_status_error (self ,payment_service ):
        """Test payment status retrieval with error."""
        with patch ("src.bot.services.payment_service.Payment.find_one")as mock_find :
            mock_find .side_effect =Exception ("API error")

            result =await payment_service .get_payment_status ("test_payment_id")

            assert result is None

    def test_verify_webhook_signature_valid (self ,payment_service ):
        """Test valid webhook signature verification."""
        payload =b'{"event": "payment.succeeded"}'
        timestamp =str (int (time .time ()))

        import hmac
        import hashlib
        message =payload +timestamp .encode ()
        signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        result =payment_service .verify_webhook_signature (payload ,signature ,timestamp )

        assert result is True

    def test_verify_webhook_signature_invalid (self ,payment_service ):
        """Test invalid webhook signature verification."""
        payload =b'{"event": "payment.succeeded"}'
        timestamp =str (int (time .time ()))
        invalid_signature ="invalid_signature"

        result =payment_service .verify_webhook_signature (payload ,invalid_signature ,timestamp )

        assert result is False

    def test_verify_webhook_signature_expired (self ,payment_service ):
        """Test expired webhook signature verification."""
        payload =b'{"event": "payment.succeeded"}'
        old_timestamp =str (int (time .time ())-600 )

        import hmac
        import hashlib
        message =payload +old_timestamp .encode ()
        signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        result =payment_service .verify_webhook_signature (payload ,signature ,old_timestamp )

        assert result is False

    @pytest .mark .asyncio
    async def test_process_webhook_success_payment (self ,payment_service ,mock_session ,sample_payment ,sample_user ):
        """Test processing successful payment webhook."""
        webhook_data ={
        "event":"payment.succeeded",
        "object":{
        "id":"test_payment_id",
        "status":"succeeded",
        "amount":{"value":"299.00","currency":"RUB"},
        "metadata":{"user_id":"1"}
        }
        }

        payload =json .dumps (webhook_data ).encode ()
        timestamp =str (int (time .time ()))

        import hmac
        import hashlib
        message =payload +timestamp .encode ()
        signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        with patch ("src.bot.services.payment_service.PaymentCRUD.update_status")as mock_update ,patch ("src.bot.services.payment_service.UserCRUD.get_by_id")as mock_get_user :

            mock_update .return_value =sample_payment
            mock_get_user .return_value =sample_user

            success ,message =await payment_service .process_webhook (
            session =mock_session ,
            payload =payload ,
            signature =signature ,
            timestamp =timestamp
            )

            assert success is True
            assert "successfully"in message
            mock_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_process_webhook_invalid_signature (self ,payment_service ,mock_session ):
        """Test processing webhook with invalid signature."""
        payload =b'{"event": "payment.succeeded"}'
        timestamp =str (int (time .time ()))
        invalid_signature ="invalid"

        success ,message =await payment_service .process_webhook (
        session =mock_session ,
        payload =payload ,
        signature =invalid_signature ,
        timestamp =timestamp
        )

        assert success is False
        assert "Invalid signature"in message

    @pytest .mark .asyncio
    async def test_process_webhook_payment_not_found (self ,payment_service ,mock_session ):
        """Test processing webhook when payment not found in database."""
        webhook_data ={
        "event":"payment.succeeded",
        "object":{
        "id":"nonexistent_payment",
        "status":"succeeded"
        }
        }

        payload =json .dumps (webhook_data ).encode ()
        timestamp =str (int (time .time ()))

        import hmac
        import hashlib
        message =payload +timestamp .encode ()
        signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        with patch ("src.bot.services.payment_service.PaymentCRUD.update_status")as mock_update :
            mock_update .return_value =None

            success ,message =await payment_service .process_webhook (
            session =mock_session ,
            payload =payload ,
            signature =signature ,
            timestamp =timestamp
            )

            assert success is False
            assert "Payment not found"in message

    @pytest .mark .asyncio
    async def test_process_webhook_cancelled_payment (self ,payment_service ,mock_session ,sample_payment ):
        """Test processing cancelled payment webhook."""
        webhook_data ={
        "event":"payment.canceled",
        "object":{
        "id":"test_payment_id",
        "status":"canceled"
        }
        }

        payload =json .dumps (webhook_data ).encode ()
        timestamp =str (int (time .time ()))

        import hmac
        import hashlib
        message =payload +timestamp .encode ()
        signature =hmac .new (
        payment_service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        with patch ("src.bot.services.payment_service.PaymentCRUD.update_status")as mock_update :
            mock_update .return_value =sample_payment

            success ,message =await payment_service .process_webhook (
            session =mock_session ,
            payload =payload ,
            signature =signature ,
            timestamp =timestamp
            )

            assert success is True
            assert "cancelled"in message
            mock_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_process_successful_payment (self ,payment_service ,mock_session ,sample_payment ,sample_user ):
        """Test processing successful payment."""
        with patch ("src.bot.services.payment_service.UserCRUD.get_by_id")as mock_get_user :
            mock_get_user .return_value =sample_user

            success =await payment_service ._process_successful_payment (mock_session ,sample_payment )

            assert success is True
            assert sample_user .subscription_expires is not None
            assert sample_user .subscription_expires >datetime .utcnow ()

    @pytest .mark .asyncio
    async def test_process_successful_payment_user_not_found (self ,payment_service ,mock_session ,sample_payment ):
        """Test processing successful payment when user not found."""
        with patch ("src.bot.services.payment_service.UserCRUD.get_by_id")as mock_get_user :
            mock_get_user .return_value =None

            success =await payment_service ._process_successful_payment (mock_session ,sample_payment )

            assert success is False

    @pytest .mark .asyncio
    async def test_process_successful_payment_extend_existing_subscription (self ,payment_service ,mock_session ,sample_payment ,sample_user ):
        """Test extending existing subscription."""

        sample_user .subscription_expires =datetime .utcnow ()+timedelta (days =15 )
        original_expiry =sample_user .subscription_expires

        with patch ("src.bot.services.payment_service.UserCRUD.get_by_id")as mock_get_user :
            mock_get_user .return_value =sample_user

            success =await payment_service ._process_successful_payment (mock_session ,sample_payment )

            assert success is True
            assert sample_user .subscription_expires >original_expiry

            expected_expiry =original_expiry +timedelta (days =30 )
            assert abs ((sample_user .subscription_expires -expected_expiry ).total_seconds ())<60

    @pytest .mark .asyncio
    async def test_cancel_payment_success (self ,payment_service ):
        """Test successful payment cancellation."""
        mock_payment =MockYooKassaPayment (status ="canceled")

        with patch ("src.bot.services.payment_service.Payment.cancel")as mock_cancel :
            mock_cancel .return_value =mock_payment

            success ,message =await payment_service .cancel_payment ("test_payment_id")

            assert success is True
            assert "cancelled"in message
            mock_cancel .assert_called_once ()

    @pytest .mark .asyncio
    async def test_cancel_payment_failure (self ,payment_service ):
        """Test payment cancellation failure."""
        with patch ("src.bot.services.payment_service.Payment.cancel")as mock_cancel :
            mock_cancel .side_effect =Exception ("Cancellation failed")

            success ,message =await payment_service .cancel_payment ("test_payment_id")

            assert success is False
            assert "Failed to cancel"in message

    def test_calculate_subscription_price_monthly (self ,payment_service ):
        """Test monthly subscription price calculation."""
        result =payment_service .calculate_subscription_price (days =30 )

        assert result ["days"]==30
        assert result ["final_price"]==299.0
        assert result ["discount"]==0.0
        assert result ["currency"]=="RUB"

    def test_calculate_subscription_price_quarterly (self ,payment_service ):
        """Test quarterly subscription price calculation."""
        result =payment_service .calculate_subscription_price (days =90 )

        assert result ["days"]==90
        assert result ["discount"]==0.10
        assert result ["final_price"]<result ["base_price"]

    def test_calculate_subscription_price_yearly (self ,payment_service ):
        """Test yearly subscription price calculation."""
        result =payment_service .calculate_subscription_price (days =365 )

        assert result ["days"]==365
        assert result ["discount"]==0.20
        assert result ["final_price"]<result ["base_price"]

    def test_calculate_subscription_price_custom (self ,payment_service ):
        """Test custom subscription price calculation."""
        result =payment_service .calculate_subscription_price (
        days =15 ,
        base_price =500.0 ,
        currency ="EUR"
        )

        assert result ["days"]==15
        assert result ["currency"]=="EUR"
        assert abs (result ["final_price"]-250.0 )<0.01

    @pytest .mark .asyncio
    async def test_get_user_payments (self ,payment_service ,mock_session ):
        """Test getting user payment history."""

        result =await payment_service .get_user_payments (mock_session ,123 )

        assert result ==[]

    @pytest .mark .asyncio
    async def test_health_check_success (self ,payment_service ):
        """Test successful health check."""
        result =await payment_service .health_check ()

        assert result is True

    @pytest .mark .asyncio
    async def test_health_check_invalid_config (self ):
        """Test health check with invalid configuration."""
        with patch ("src.bot.services.payment_service.Configuration.configure"):
            service =PaymentService ()
            service .shop_id =None

            result =await service .health_check ()

            assert result is False

    def test_configuration_failure(self):
        """Test PaymentService initialization with configuration failure."""
        with patch("src.bot.services.payment_service.Configuration.configure") as mock_config:
            mock_config.side_effect = Exception("Configuration failed")

            with pytest.raises(Exception, match="Configuration failed"):
                PaymentService()

    # Additional comprehensive tests for edge cases and error handling

    @pytest.mark.asyncio
    async def test_create_payment_with_metadata(self, payment_service, mock_session, mock_yookassa_payment):
        """Test payment creation with custom metadata."""
        mock_yookassa_payment.metadata = {"user_id": "123", "plan": "premium", "duration": "30"}

        with patch("src.bot.services.payment_service.Payment.create") as mock_create, \
             patch("src.bot.services.payment_service.PaymentCRUD.create") as mock_crud_create:

            mock_create.return_value = mock_yookassa_payment
            mock_crud_create.return_value = MagicMock()

            result = await payment_service.create_payment(
                session=mock_session,
                user_id=123,
                amount=299.0,
                description="Premium subscription",
                metadata={"plan": "premium", "duration": "30"}
            )

            assert result["payment_id"] == "test_payment_id"
            assert "confirmation_url" in result

            # Verify metadata was passed to YooKassa
            create_call_args = mock_create.call_args[0][0]
            assert "metadata" in create_call_args
            assert create_call_args["metadata"]["plan"] == "premium"

    @pytest.mark.asyncio
    async def test_create_payment_with_return_url(self, payment_service, mock_session, mock_yookassa_payment):
        """Test payment creation with custom return URL."""
        with patch("src.bot.services.payment_service.Payment.create") as mock_create, \
             patch("src.bot.services.payment_service.PaymentCRUD.create") as mock_crud_create:

            mock_create.return_value = mock_yookassa_payment
            mock_crud_create.return_value = MagicMock()

            custom_return_url = "https://example.com/payment/return"
            result = await payment_service.create_payment(
                session=mock_session,
                user_id=123,
                amount=299.0,
                return_url=custom_return_url
            )

            assert result["payment_id"] == "test_payment_id"

            # Verify return URL was passed to YooKassa
            create_call_args = mock_create.call_args[0][0]
            assert create_call_args["confirmation"]["return_url"] == custom_return_url

    @pytest.mark.asyncio
    async def test_create_payment_yookassa_api_error(self, payment_service, mock_session):
        """Test payment creation with YooKassa API error."""
        from yookassa.domain.exceptions import ApiError
        
        with patch("src.bot.services.payment_service.Payment.create") as mock_create:
            mock_create.side_effect = ApiError("Invalid shop credentials")

            with pytest.raises(ApiError, match="Invalid shop credentials"):
                await payment_service.create_payment(
                    session=mock_session,
                    user_id=123,
                    amount=299.0
                )

            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_payment_status_with_metadata(self, payment_service, mock_yookassa_payment):
        """Test payment status retrieval with metadata."""
        mock_yookassa_payment.metadata = {"user_id": "123", "plan": "premium"}

        with patch("src.bot.services.payment_service.Payment.find_one") as mock_find:
            mock_find.return_value = mock_yookassa_payment

            result = await payment_service.get_payment_status("test_payment_id")

            assert result is not None
            assert "metadata" in result
            assert result["metadata"]["plan"] == "premium"

    def test_verify_webhook_signature_different_algorithms(self, payment_service):
        """Test webhook signature verification with different hash algorithms."""
        payload = b'{"event": "payment.succeeded"}'
        timestamp = str(int(time.time()))

        # Test with SHA256 (default)
        import hmac
        import hashlib
        message = payload + timestamp.encode()
        signature = hmac.new(
            payment_service.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        result = payment_service.verify_webhook_signature(payload, signature, timestamp)
        assert result is True

    def test_verify_webhook_signature_malformed_timestamp(self, payment_service):
        """Test webhook signature verification with malformed timestamp."""
        payload = b'{"event": "payment.succeeded"}'
        invalid_timestamp = "not-a-number"

        result = payment_service.verify_webhook_signature(payload, "signature", invalid_timestamp)
        assert result is False

    def test_verify_webhook_signature_empty_payload(self, payment_service):
        """Test webhook signature verification with empty payload."""
        payload = b''
        timestamp = str(int(time.time()))

        import hmac
        import hashlib
        message = payload + timestamp.encode()
        signature = hmac.new(
            payment_service.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        result = payment_service.verify_webhook_signature(payload, signature, timestamp)
        assert result is True

    @pytest.mark.asyncio
    async def test_process_webhook_refund_event(self, payment_service, mock_session, sample_payment):
        """Test processing refund webhook event."""
        webhook_data = {
            "event": "refund.succeeded",
            "object": {
                "id": "refund_id",
                "payment_id": "test_payment_id",
                "status": "succeeded",
                "amount": {"value": "100.00", "currency": "RUB"}
            }
        }

        payload = json.dumps(webhook_data).encode()
        timestamp = str(int(time.time()))

        import hmac
        import hashlib
        message = payload + timestamp.encode()
        signature = hmac.new(
            payment_service.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        with patch("src.bot.services.payment_service.PaymentCRUD.get_by_yookassa_id") as mock_get:
            mock_get.return_value = sample_payment

            success, message = await payment_service.process_webhook(
                session=mock_session,
                payload=payload,
                signature=signature,
                timestamp=timestamp
            )

            assert success is True
            assert "refund" in message.lower()

    @pytest.mark.asyncio
    async def test_process_webhook_unknown_event(self, payment_service, mock_session):
        """Test processing unknown webhook event."""
        webhook_data = {
            "event": "unknown.event",
            "object": {
                "id": "test_id"
            }
        }

        payload = json.dumps(webhook_data).encode()
        timestamp = str(int(time.time()))

        import hmac
        import hashlib
        message = payload + timestamp.encode()
        signature = hmac.new(
            payment_service.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        success, message = await payment_service.process_webhook(
            session=mock_session,
            payload=payload,
            signature=signature,
            timestamp=timestamp
        )

        assert success is True
        assert "unknown event" in message.lower()

    @pytest.mark.asyncio
    async def test_process_webhook_malformed_json(self, payment_service, mock_session):
        """Test processing webhook with malformed JSON."""
        payload = b'{"event": "payment.succeeded", invalid json}'
        timestamp = str(int(time.time()))

        import hmac
        import hashlib
        message = payload + timestamp.encode()
        signature = hmac.new(
            payment_service.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        success, message = await payment_service.process_webhook(
            session=mock_session,
            payload=payload,
            signature=signature,
            timestamp=timestamp
        )

        assert success is False
        assert "invalid json" in message.lower()

    @pytest.mark.asyncio
    async def test_process_successful_payment_extend_trial(self, payment_service, mock_session, sample_payment, sample_user):
        """Test extending trial when processing successful payment."""
        # User has active trial but no subscription
        sample_user.trial_expires = datetime.utcnow() + timedelta(days=5)
        sample_user.subscription_expires = None

        with patch("src.bot.services.payment_service.UserCRUD.get_by_id") as mock_get_user:
            mock_get_user.return_value = sample_user

            success = await payment_service._process_successful_payment(mock_session, sample_payment)

            assert success is True
            # Should set subscription to start after trial expires
            assert sample_user.subscription_expires > sample_user.trial_expires

    @pytest.mark.asyncio
    async def test_cancel_payment_already_succeeded(self, payment_service):
        """Test cancelling payment that already succeeded."""
        from yookassa.domain.exceptions import ApiError
        
        with patch("src.bot.services.payment_service.Payment.cancel") as mock_cancel:
            mock_cancel.side_effect = ApiError("Payment already succeeded")

            success, message = await payment_service.cancel_payment("test_payment_id")

            assert success is False
            assert "already succeeded" in message.lower()

    def test_calculate_subscription_price_with_discount_tiers(self, payment_service):
        """Test subscription price calculation with different discount tiers."""
        # Test 3-month subscription (should get 10% discount)
        result = payment_service.calculate_subscription_price(days=90)
        assert result["discount"] == 0.10
        assert result["final_price"] < result["base_price"]

        # Test 6-month subscription (should get 15% discount)
        result = payment_service.calculate_subscription_price(days=180)
        assert result["discount"] == 0.15
        assert result["final_price"] < result["base_price"]

        # Test 12-month subscription (should get 20% discount)
        result = payment_service.calculate_subscription_price(days=365)
        assert result["discount"] == 0.20
        assert result["final_price"] < result["base_price"]

    def test_calculate_subscription_price_edge_cases(self, payment_service):
        """Test subscription price calculation edge cases."""
        # Test zero days
        result = payment_service.calculate_subscription_price(days=0)
        assert result["final_price"] == 0.0

        # Test negative days (should be treated as 0)
        result = payment_service.calculate_subscription_price(days=-5)
        assert result["final_price"] == 0.0

        # Test very large number of days
        result = payment_service.calculate_subscription_price(days=10000)
        assert result["days"] == 10000
        assert result["final_price"] > 0

    @pytest.mark.asyncio
    async def test_get_user_payments_with_filters(self, payment_service, mock_session):
        """Test getting user payments with status filter."""
        sample_payments = [
            Payment(id=1, user_id=123, yookassa_id="pay1", status="succeeded", amount=299.0),
            Payment(id=2, user_id=123, yookassa_id="pay2", status="pending", amount=299.0),
            Payment(id=3, user_id=123, yookassa_id="pay3", status="canceled", amount=299.0),
        ]

        with patch("src.bot.services.payment_service.PaymentCRUD.get_by_user_id") as mock_get:
            mock_get.return_value = sample_payments

            # Test getting all payments
            result = await payment_service.get_user_payments(mock_session, 123)
            assert len(result) == 3

            # Test getting only succeeded payments
            result = await payment_service.get_user_payments(mock_session, 123, status="succeeded")
            assert len(result) == 1
            assert result[0].status == "succeeded"

    @pytest.mark.asyncio
    async def test_create_refund(self, payment_service):
        """Test creating a refund."""
        mock_refund = MagicMock()
        mock_refund.id = "refund_id"
        mock_refund.status = "pending"
        mock_refund.amount = MagicMock()
        mock_refund.amount.value = "100.00"
        mock_refund.amount.currency = "RUB"

        with patch("src.bot.services.payment_service.Refund.create") as mock_create:
            mock_create.return_value = mock_refund

            result = await payment_service.create_refund("test_payment_id", 100.0)

            assert result["refund_id"] == "refund_id"
            assert result["status"] == "pending"
            assert result["amount"] == "100.00"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_refund_failure(self, payment_service):
        """Test refund creation failure."""
        from yookassa.domain.exceptions import ApiError
        
        with patch("src.bot.services.payment_service.Refund.create") as mock_create:
            mock_create.side_effect = ApiError("Refund not allowed")

            with pytest.raises(ApiError, match="Refund not allowed"):
                await payment_service.create_refund("test_payment_id", 100.0)

    @pytest.mark.asyncio
    async def test_health_check_with_api_call(self, payment_service):
        """Test health check that makes actual API call."""
        with patch("src.bot.services.payment_service.Payment.list") as mock_list:
            mock_list.return_value = MagicMock()

            result = await payment_service.health_check()

            assert result is True
            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_api_failure(self, payment_service):
        """Test health check with API failure."""
        from yookassa.domain.exceptions import ApiError
        
        with patch("src.bot.services.payment_service.Payment.list") as mock_list:
            mock_list.side_effect = ApiError("API unavailable")

            result = await payment_service.health_check()

            assert result is False

    def test_webhook_signature_timing_attack_protection(self, payment_service):
        """Test webhook signature verification protects against timing attacks."""
        payload = b'{"event": "payment.succeeded"}'
        timestamp = str(int(time.time()))
        
        # Create correct signature
        import hmac
        import hashlib
        message = payload + timestamp.encode()
        correct_signature = hmac.new(
            payment_service.secret_key.encode(),
            message,
            hashlib.sha256
        ).hexdigest()
        
        # Create incorrect signature of same length
        incorrect_signature = "a" * len(correct_signature)
        
        # Both should take similar time (using constant-time comparison)
        import time
        
        start_time = time.time()
        result1 = payment_service.verify_webhook_signature(payload, correct_signature, timestamp)
        time1 = time.time() - start_time
        
        start_time = time.time()
        result2 = payment_service.verify_webhook_signature(payload, incorrect_signature, timestamp)
        time2 = time.time() - start_time
        
        assert result1 is True
        assert result2 is False
        # Time difference should be minimal (timing attack protection)
        assert abs(time1 - time2) < 0.01  # Less than 10ms difference