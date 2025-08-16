"""Tests for YooKassa webhook processing."""

import json
import time
from unittest .mock import AsyncMock ,MagicMock ,patch

import pytest
from fastapi .testclient import TestClient

from src .main import create_app

@pytest .fixture
def app ():
    """Create test FastAPI app."""
    return create_app ()

@pytest .fixture
def client (app ):
    """Create test client."""
    return TestClient (app )

@pytest .fixture
def mock_payment_service ():
    """Mock payment service for webhook tests."""
    with patch ('src.main.PaymentService')as mock_class :
        mock_instance =MagicMock ()
        mock_class .return_value =mock_instance
        yield mock_instance

@pytest .fixture
def mock_db_session ():
    """Mock database session."""
    with patch ('src.main.get_db_session')as mock :
        session =AsyncMock ()
        mock .return_value .__aenter__ .return_value =session
        yield session

class TestYooKassaWebhook :
    """Test YooKassa webhook endpoint."""

    def test_webhook_success (self ,client ,mock_payment_service ,mock_db_session ):
        """Test successful webhook processing."""

        mock_payment_service .process_webhook .return_value =(True ,"Payment processed successfully")

        payload ={
        "event":"payment.succeeded",
        "object":{
        "id":"test_payment_123",
        "status":"succeeded",
        "amount":{"value":"299.00","currency":"RUB"},
        "metadata":{"user_id":"123456789"}
        }
        }

        headers ={
        "Yookassa-Signature":"test_signature",
        "Yookassa-Timestamp":str (int (time .time ())),
        "Content-Type":"application/json"
        }

        response =client .post (
        "/payment/webhook",
        json =payload ,
        headers =headers
        )

        assert response .status_code ==200
        assert response .json ()["status"]=="ok"
        assert "successfully"in response .json ()["message"]

        mock_payment_service .process_webhook .assert_called_once ()

    def test_webhook_processing_failure (self ,client ,mock_payment_service ,mock_db_session ):
        """Test webhook processing failure."""

        mock_payment_service .process_webhook .return_value =(False ,"Invalid signature")

        payload ={
        "event":"payment.succeeded",
        "object":{
        "id":"test_payment_123",
        "status":"succeeded"
        }
        }

        headers ={
        "Yookassa-Signature":"invalid_signature",
        "Yookassa-Timestamp":str (int (time .time ())),
        "Content-Type":"application/json"
        }

        response =client .post (
        "/payment/webhook",
        json =payload ,
        headers =headers
        )

        assert response .status_code ==200
        assert response .json ()["status"]=="error"
        assert "Invalid signature"in response .json ()["message"]

    def test_webhook_exception (self ,client ,mock_payment_service ,mock_db_session ):
        """Test webhook processing with exception."""

        mock_payment_service .process_webhook .side_effect =Exception ("Database error")

        payload ={
        "event":"payment.succeeded",
        "object":{
        "id":"test_payment_123",
        "status":"succeeded"
        }
        }

        headers ={
        "Yookassa-Signature":"test_signature",
        "Yookassa-Timestamp":str (int (time .time ())),
        "Content-Type":"application/json"
        }

        response =client .post (
        "/payment/webhook",
        json =payload ,
        headers =headers
        )

        assert response .status_code ==200
        assert response .json ()["status"]=="error"
        assert "Failed to process webhook"in response .json ()["message"]

    def test_webhook_invalid_json (self ,client ):
        """Test webhook with invalid JSON payload."""
        headers ={
        "Yookassa-Signature":"test_signature",
        "Yookassa-Timestamp":str (int (time .time ())),
        "Content-Type":"application/json"
        }

        response =client .post (
        "/payment/webhook",
        data ="invalid json",
        headers =headers
        )

        assert response .status_code ==422

    def test_webhook_missing_headers (self ,client ):
        """Test webhook with missing headers."""
        payload ={
        "event":"payment.succeeded",
        "object":{
        "id":"test_payment_123",
        "status":"succeeded"
        }
        }

        response =client .post (
        "/payment/webhook",
        json =payload
        )

        assert response .status_code ==200
        assert response .json ()["status"]=="error"

class TestPaymentSuccessPage :
    """Test payment success redirect page."""

    def test_payment_success_page (self ,client ):
        """Test payment success page."""
        response =client .get ("/payment/success")

        assert response .status_code ==200
        data =response .json ()
        assert data ["status"]=="success"
        assert "Payment completed successfully"in data ["message"]
        assert "close this page"in data ["message"]

    def test_payment_success_page_with_params (self ,client ):
        """Test payment success page with query parameters."""
        response =client .get ("/payment/success?payment_id=test_123&status=succeeded")

        assert response .status_code ==200
        data =response .json ()
        assert data ["status"]=="success"

class TestWebhookIntegration :
    """Integration tests for webhook processing."""

    @pytest .mark .asyncio
    async def test_webhook_payment_succeeded_flow (self ,mock_db_session ):
        """Test complete webhook flow for successful payment."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        with patch .object (payment_service ,'verify_webhook_signature',return_value =True ):

            with patch ('src.bot.services.payment_service.PaymentCRUD')as mock_crud :
                mock_payment =MagicMock ()
                mock_payment .user_id =1
                mock_crud .update_status .return_value =mock_payment

                with patch ('src.bot.services.payment_service.UserCRUD')as mock_user_crud :
                    mock_user =MagicMock ()
                    mock_user .id =1
                    mock_user .subscription_expires =None
                    mock_user_crud .get_by_id .return_value =mock_user

                    payload =json .dumps ({
                    "event":"payment.succeeded",
                    "object":{
                    "id":"test_payment_123",
                    "status":"succeeded",
                    "amount":{"value":"299.00","currency":"RUB"},
                    "metadata":{"user_id":"1"}
                    }
                    }).encode ('utf-8')

                    success ,message =await payment_service .process_webhook (
                    session =mock_db_session ,
                    payload =payload ,
                    signature ="test_signature",
                    timestamp =str (int (time .time ()))
                    )

                    assert success is True
                    assert "successfully"in message

                    mock_crud .update_status .assert_called_once ()
                    mock_user_crud .get_by_id .assert_called_once ()

    @pytest .mark .asyncio
    async def test_webhook_payment_canceled_flow (self ,mock_db_session ):
        """Test webhook flow for canceled payment."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        with patch .object (payment_service ,'verify_webhook_signature',return_value =True ):
            with patch ('src.bot.services.payment_service.PaymentCRUD')as mock_crud :
                mock_payment =MagicMock ()
                mock_payment .user_id =1
                mock_crud .update_status .return_value =mock_payment

                payload =json .dumps ({
                "event":"payment.canceled",
                "object":{
                "id":"test_payment_123",
                "status":"canceled"
                }
                }).encode ('utf-8')

                success ,message =await payment_service .process_webhook (
                session =mock_db_session ,
                payload =payload ,
                signature ="test_signature",
                timestamp =str (int (time .time ()))
                )

                assert success is True
                assert "cancelled"in message

                mock_crud .update_status .assert_called_once ()

    @pytest .mark .asyncio
    async def test_webhook_invalid_signature (self ,mock_db_session ):
        """Test webhook with invalid signature."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        with patch .object (payment_service ,'verify_webhook_signature',return_value =False ):
            payload =json .dumps ({
            "event":"payment.succeeded",
            "object":{"id":"test_payment_123"}
            }).encode ('utf-8')

            success ,message =await payment_service .process_webhook (
            session =mock_db_session ,
            payload =payload ,
            signature ="invalid_signature",
            timestamp =str (int (time .time ()))
            )

            assert success is False
            assert "Invalid signature"in message

    @pytest .mark .asyncio
    async def test_webhook_payment_not_found (self ,mock_db_session ):
        """Test webhook for payment not found in database."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        with patch .object (payment_service ,'verify_webhook_signature',return_value =True ):
            with patch ('src.bot.services.payment_service.PaymentCRUD')as mock_crud :

                mock_crud .update_status .return_value =None

                payload =json .dumps ({
                "event":"payment.succeeded",
                "object":{
                "id":"nonexistent_payment",
                "status":"succeeded"
                }
                }).encode ('utf-8')

                success ,message =await payment_service .process_webhook (
                session =mock_db_session ,
                payload =payload ,
                signature ="test_signature",
                timestamp =str (int (time .time ()))
                )

                assert success is False
                assert "Payment not found"in message

    @pytest .mark .asyncio
    async def test_webhook_malformed_payload (self ,mock_db_session ):
        """Test webhook with malformed payload."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        with patch .object (payment_service ,'verify_webhook_signature',return_value =True ):

            payload =b"invalid json"

            success ,message =await payment_service .process_webhook (
            session =mock_db_session ,
            payload =payload ,
            signature ="test_signature",
            timestamp =str (int (time .time ()))
            )

            assert success is False
            assert "failed"in message .lower ()

    @pytest .mark .asyncio
    async def test_webhook_missing_payment_id (self ,mock_db_session ):
        """Test webhook with missing payment ID."""
        from src .bot .services .payment_service import PaymentService

        payment_service =PaymentService ()

        with patch .object (payment_service ,'verify_webhook_signature',return_value =True ):
            payload =json .dumps ({
            "event":"payment.succeeded",
            "object":{
            "status":"succeeded"
            }
            }).encode ('utf-8')

            success ,message =await payment_service .process_webhook (
            session =mock_db_session ,
            payload =payload ,
            signature ="test_signature",
            timestamp =str (int (time .time ()))
            )

            assert success is False
            assert "No payment ID"in message 