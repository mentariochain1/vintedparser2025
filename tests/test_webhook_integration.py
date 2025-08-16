"""Comprehensive integration tests for webhook processing and background jobs."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.db.models import User, Payment


class TestWebhookProcessingIntegration:
    """Integration tests for webhook processing with database state changes."""

    @pytest.fixture
    def test_client(self):
        """Create FastAPI test client."""
        from src.main import app
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_yookassa_webhook_complete_flow(self, test_client, mock_session, sample_user, sample_payment):
        """Test complete YooKassa webhook processing flow."""
        webhook_data = {
            "event": "payment.succeeded",
            "object": {
                "id": "test_payment_123",
                "status": "succeeded",
                "amount": {"value": "299.00", "currency": "RUB"},
                "metadata": {"user_id": str(sample_user.id)}
            }
        }

        payload = json.dumps(webhook_data).encode()
        timestamp = str(int(datetime.utcnow().timestamp()))

        # Create valid signature
        import hmac
        import hashlib
        secret_key = "test_secret_key"
        message = payload + timestamp.encode()
        signature = hmac.new(secret_key.encode(), message, hashlib.sha256).hexdigest()

        with patch("src.main.get_db_session") as mock_get_session, \
             patch("src.main.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_payment_service.process_webhook.return_value = (True, "Payment processed successfully")

            # Send webhook request
            response = test_client.post(
                "/webhooks/yookassa",
                content=payload,
                headers={
                    "Yookassa-Signature": signature,
                    "Yookassa-Timestamp": timestamp,
                    "Content-Type": "application/json"
                }
            )

            # Verify response
            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # Verify webhook processing was called
            mock_payment_service.process_webhook.assert_called_once()
            call_args = mock_payment_service.process_webhook.call_args[1]
            assert call_args["payload"] == payload
            assert call_args["signature"] == signature
            assert call_args["timestamp"] == timestamp

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature(self, test_client):
        """Test webhook with invalid signature."""
        webhook_data = {"event": "payment.succeeded", "object": {"id": "test"}}
        payload = json.dumps(webhook_data).encode()
        timestamp = str(int(datetime.utcnow().timestamp()))
        invalid_signature = "invalid_signature"

        response = test_client.post(
            "/webhooks/yookassa",
            content=payload,
            headers={
                "Yookassa-Signature": invalid_signature,
                "Yookassa-Timestamp": timestamp,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid signature" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_malformed_payload(self, test_client):
        """Test webhook with malformed JSON payload."""
        payload = b'{"invalid": json}'
        timestamp = str(int(datetime.utcnow().timestamp()))

        # Create signature for malformed payload
        import hmac
        import hashlib
        secret_key = "test_secret_key"
        message = payload + timestamp.encode()
        signature = hmac.new(secret_key.encode(), message, hashlib.sha256).hexdigest()

        response = test_client.post(
            "/webhooks/yookassa",
            content=payload,
            headers={
                "Yookassa-Signature": signature,
                "Yookassa-Timestamp": timestamp,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]


class TestBackgroundJobIntegration:
    """Integration tests for background job execution."""

    @pytest.mark.asyncio
    async def test_search_task_complete_execution(self, mock_session):
        """Test complete search task execution with database updates."""
        mock_items = [
            {
                "id": 12345,
                "title": "Test Item 1",
                "price": 25.0,
                "currency": "EUR",
                "brand": "Nike",
                "size": "M",
                "condition": "Good",
                "description": "Test description 1",
                "seller_id": 67890,
                "url": "https://www.vinted.at/items/12345",
                "photos": ["photo1.jpg", "photo2.jpg"],
                "ships_to_at": True
            },
            {
                "id": 12346,
                "title": "Test Item 2",
                "price": 35.0,
                "currency": "EUR",
                "brand": "Adidas",
                "size": "L",
                "condition": "Very Good",
                "description": "Test description 2",
                "seller_id": 67891,
                "url": "https://www.vinted.at/items/12346",
                "photos": ["photo3.jpg"],
                "ships_to_at": True
            }
        ]

        with patch("src.tasks.search_tasks.vinted_service") as mock_vinted_service, \
             patch("src.tasks.search_tasks.get_db_session") as mock_get_session, \
             patch("src.tasks.search_tasks.ItemCRUD") as mock_item_crud, \
             patch("src.tasks.search_tasks.PhotoCRUD") as mock_photo_crud:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_vinted_service.search_and_get_details.return_value = mock_items
            mock_item_crud.upsert.return_value = None
            mock_photo_crud.upsert_batch.return_value = None

            from src.tasks.search_tasks import process_search_task

            # Execute search task
            result = await process_search_task(
                search_id="search_123",
                query="Nike sneakers",
                user_id=123456789,
                max_pages=2
            )

            # Verify search execution
            mock_vinted_service.search_and_get_details.assert_called_once_with(
                "Nike sneakers", max_pages=2
            )

            # Verify database operations
            assert mock_item_crud.upsert.call_count == 2
            assert mock_photo_crud.upsert_batch.call_count == 2

            # Verify result
            assert result["status"] == "completed"
            assert result["total_items"] == 2
            assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_search_task_with_errors(self, mock_session):
        """Test search task execution with partial errors."""
        with patch("src.tasks.search_tasks.vinted_service") as mock_vinted_service, \
             patch("src.tasks.search_tasks.get_db_session") as mock_get_session, \
             patch("src.tasks.search_tasks.ItemCRUD") as mock_item_crud:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_vinted_service.search_and_get_details.side_effect = Exception("Vinted API error")

            from src.tasks.search_tasks import process_search_task

            # Execute search task
            result = await process_search_task(
                search_id="search_123",
                query="test query",
                user_id=123456789,
                max_pages=1
            )

            # Verify error handling
            assert result["status"] == "failed"
            assert "error" in result
            assert "Vinted API error" in result["error"]

            # Verify no database operations
            mock_item_crud.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_notification_task_execution(self, mock_session):
        """Test notification task execution."""
        with patch("src.tasks.notification_handlers.notification_service") as mock_notification_service, \
             patch("src.tasks.notification_handlers.get_db_session") as mock_get_session:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_notification_service.send_search_results.return_value = True

            from src.tasks.notification_handlers import send_search_notification

            # Execute notification task
            result = await send_search_notification(
                user_id=123456789,
                search_results=[{"id": 1, "title": "Test Item"}],
                query="test query"
            )

            # Verify notification sending
            mock_notification_service.send_search_results.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_background_jobs(self, mock_session):
        """Test concurrent execution of multiple background jobs."""
        import asyncio

        with patch("src.tasks.search_tasks.vinted_service") as mock_vinted_service, \
             patch("src.tasks.search_tasks.get_db_session") as mock_get_session:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_vinted_service.search_and_get_details.return_value = []

            from src.tasks.search_tasks import process_search_task

            # Create multiple concurrent tasks
            tasks = []
            for i in range(3):
                task = asyncio.create_task(process_search_task(
                    search_id=f"search_{i}",
                    query=f"query_{i}",
                    user_id=123456789 + i,
                    max_pages=1
                ))
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)

            # Verify all tasks completed
            assert len(results) == 3
            assert all(result["status"] == "completed" for result in results)

            # Verify all searches were executed
            assert mock_vinted_service.search_and_get_details.call_count == 3


class TestDatabaseStateIntegration:
    """Integration tests for database state changes during handler execution."""

    @pytest.mark.asyncio
    async def test_user_creation_database_integration(self, mock_session):
        """Test user creation with database state verification."""
        created_user = User(
            id=1,
            tg_id=123456789,
            username="testuser",
            first_name="Test",
            trial_expires=datetime.utcnow() + timedelta(days=7),
            referrals_count=0
        )

        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.create_user.return_value = created_user

            message = MagicMock()
            message.from_user.id = 123456789
            message.from_user.username = "testuser"
            message.from_user.first_name = "Test"
            message.answer = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart()
            await start_handler(message, command)

            # Verify user creation was called with correct parameters
            mock_user_service.create_user.assert_called_once_with(
                session=mock_session,
                tg_id=123456789,
                username="testuser",
                first_name="Test",
                referrer_id=None
            )

            # Verify database session was committed
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_payment_processing_database_integration(self, mock_session, sample_user):
        """Test payment processing with database state changes."""
        created_payment = Payment(
            id=1,
            user_id=sample_user.id,
            yookassa_id="test_payment_123",
            amount=299.0,
            currency="RUB",
            status="pending"
        )

        with patch("src.bot.handlers.payment.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.payment.user_service") as mock_user_service, \
             patch("src.bot.handlers.payment.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            mock_payment_service.create_payment.return_value = {
                "payment_id": "test_payment_123",
                "confirmation_url": "https://yookassa.ru/checkout/test_payment_123",
                "status": "pending"
            }

            callback = MagicMock()
            callback.data = "confirm_pay_30"
            callback.from_user.id = sample_user.tg_id
            callback.answer = AsyncMock()
            callback.message.edit_text = AsyncMock()

            from src.bot.handlers.payment import handle_payment_confirmation
            await handle_payment_confirmation(callback)

            # Verify payment creation with database session
            mock_payment_service.create_payment.assert_called_once()
            create_args = mock_payment_service.create_payment.call_args[1]
            assert create_args["session"] == mock_session
            assert create_args["user_id"] == sample_user.id

    @pytest.mark.asyncio
    async def test_referral_processing_database_integration(self, mock_session):
        """Test referral processing with database state changes."""
        inviter = User(id=1, tg_id=111111111, referrals_count=0)
        invitee = User(id=2, tg_id=222222222, referred_by=None)

        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.decode_referral_payload.return_value = 1
            mock_user_service.get_user_by_id.return_value = inviter
            mock_user_service.create_user.return_value = invitee
            mock_user_service.process_referral.return_value = (True, "Referral processed")

            message = MagicMock()
            message.from_user.id = 222222222
            message.from_user.username = "invitee"
            message.from_user.first_name = "Invitee"
            message.answer = AsyncMock()
            message.bot.send_message = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart(args="referral_payload")
            await start_handler(message, command)

            # Verify referral processing with database session
            mock_user_service.process_referral.assert_called_once_with(
                session=mock_session,
                inviter_id=1,
                invitee_id=2
            )

            # Verify database operations were committed
            mock_session.commit.assert_called()