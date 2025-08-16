"""Comprehensive integration tests for bot handlers."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import User, Payment, Item, Photo


class TestStartHandlerIntegration:
    """Integration tests for start handler with complete user flows."""

    @pytest.mark.asyncio
    async def test_complete_new_user_flow(self, mock_session, sample_user):
        """Test complete new user registration flow."""
        # Mock the handler dependencies
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.create_user.return_value = sample_user
            mock_user_service.decode_referral_payload.return_value = None

            # Create mock message
            message = MagicMock()
            message.from_user.id = 123456789
            message.from_user.username = "testuser"
            message.from_user.first_name = "Test"
            message.answer = AsyncMock()

            # Import and test the handler
            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart()
            await start_handler(message, command)

            # Verify user creation was called
            mock_user_service.create_user.assert_called_once_with(
                session=mock_session,
                tg_id=123456789,
                username="testuser",
                first_name="Test",
                referrer_id=None
            )

            # Verify welcome message was sent
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "Welcome to Vinted Parser Bot" in call_args

    @pytest.mark.asyncio
    async def test_referral_flow_integration(self, mock_session):
        """Test complete referral flow integration."""
        # Create referrer and new user
        referrer = User(
            id=1,
            tg_id=111111111,
            username="referrer",
            first_name="Referrer",
            trial_expires=datetime.utcnow() + timedelta(days=5),
            referrals_count=0,
        )

        new_user = User(
            id=2,
            tg_id=222222222,
            username="newuser",
            first_name="NewUser",
            trial_expires=datetime.utcnow() + timedelta(days=7),
            referred_by=1,
            referrals_count=0,
        )

        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.decode_referral_payload.return_value = 1
            mock_user_service.get_user_by_id.return_value = referrer
            mock_user_service.create_user.return_value = new_user
            mock_user_service.process_referral.return_value = (True, "Referral processed successfully")

            # Create mock message with referral
            message = MagicMock()
            message.from_user.id = 222222222
            message.from_user.username = "newuser"
            message.from_user.first_name = "NewUser"
            message.answer = AsyncMock()
            message.bot.send_message = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart(args="referral_payload")
            await start_handler(message, command)

            # Verify referral processing
            mock_user_service.process_referral.assert_called_once_with(
                session=mock_session,
                inviter_id=1,
                invitee_id=2
            )

            # Verify both users got notified
            message.answer.assert_called_once()
            message.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_user_flow(self, mock_session, sample_user):
        """Test existing user flow integration."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user

            message = MagicMock()
            message.from_user.id = sample_user.tg_id
            message.from_user.username = sample_user.username
            message.from_user.first_name = sample_user.first_name
            message.answer = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart()
            await start_handler(message, command)

            # Verify no user creation
            mock_user_service.create_user.assert_not_called()

            # Verify welcome back message
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "Welcome back" in call_args


class TestSearchHandlerIntegration:
    """Integration tests for search handler with complete search flows."""

    @pytest.mark.asyncio
    async def test_complete_search_flow_premium_user(self, mock_session, sample_user_with_subscription):
        """Test complete search flow for premium user."""
        with patch("src.bot.handlers.search.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.search.user_service") as mock_user_service, \
             patch("src.bot.handlers.search.search_task_manager") as mock_task_manager:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.is_premium_active.return_value = True
            mock_task_manager.queue_search_task.return_value = "search_123"

            # Test search command
            message = MagicMock()
            message.from_user.id = sample_user_with_subscription.tg_id
            message.answer = AsyncMock()

            state = AsyncMock()

            from src.bot.handlers.search import search_command
            await search_command(message, state)

            # Verify premium check and state setting
            mock_user_service.is_premium_active.assert_called_once()
            state.set_state.assert_called_once()
            message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_query_processing_integration(self, mock_session):
        """Test search query processing integration."""
        with patch("src.bot.handlers.search.search_task_manager") as mock_task_manager, \
             patch("asyncio.create_task") as mock_create_task, \
             patch("asyncio.sleep"):

            mock_task_manager.queue_search_task.return_value = "search_123"
            mock_task_manager.is_search_complete.return_value = False

            message = MagicMock()
            message.text = "Nike sneakers"
            message.from_user.id = 123456789
            message.chat.id = 987654321
            message.answer = AsyncMock()

            search_msg = MagicMock()
            search_msg.message_id = 999
            message.answer.return_value = search_msg

            state = AsyncMock()

            from src.bot.handlers.search import process_search_query
            await process_search_query(message, state)

            # Verify search task was queued
            mock_task_manager.queue_search_task.assert_called_once()
            call_kwargs = mock_task_manager.queue_search_task.call_args[1]
            assert call_kwargs["query"] == "Nike sneakers"
            assert call_kwargs["user_id"] == 123456789

            # Verify state was cleared
            state.clear.assert_called_once()


class TestPaymentHandlerIntegration:
    """Integration tests for payment handler with complete payment flows."""

    @pytest.mark.asyncio
    async def test_complete_payment_creation_flow(self, mock_session, sample_user, mock_yookassa_payment):
        """Test complete payment creation flow."""
        with patch("src.bot.handlers.payment.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.payment.user_service") as mock_user_service, \
             patch("src.bot.handlers.payment.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            mock_payment_service.calculate_subscription_price.return_value = {
                "days": 30,
                "final_price": 299.0,
                "currency": "RUB"
            }
            mock_payment_service.create_payment.return_value = {
                "payment_id": "test_payment_123",
                "confirmation_url": "https://yookassa.ru/checkout/test_payment_123",
                "status": "pending"
            }

            # Create callback query for payment confirmation
            callback = MagicMock()
            callback.data = "confirm_pay_30"
            callback.from_user.id = sample_user.tg_id
            callback.answer = AsyncMock()
            callback.message.edit_text = AsyncMock()

            from src.bot.handlers.payment import handle_payment_confirmation
            await handle_payment_confirmation(callback)

            # Verify payment creation
            mock_payment_service.create_payment.assert_called_once()
            create_args = mock_payment_service.create_payment.call_args[1]
            assert create_args["user_id"] == sample_user.id
            assert create_args["amount"] == 299.0

            # Verify response
            callback.message.edit_text.assert_called_once()
            edit_args = callback.message.edit_text.call_args[0][0]
            assert "Payment Created Successfully" in edit_args

    @pytest.mark.asyncio
    async def test_payment_status_check_integration(self, mock_session):
        """Test payment status check integration."""
        with patch("src.bot.handlers.payment.payment_service") as mock_payment_service:

            mock_payment_service.get_payment_status.return_value = {
                "payment_id": "test_payment_123",
                "status": "succeeded",
                "amount": "299.00",
                "currency": "RUB",
                "metadata": {"user_id": "123456789"}
            }

            callback = MagicMock()
            callback.data = "check_payment_test_payment_123"
            callback.from_user.id = 123456789
            callback.answer = AsyncMock()
            callback.message.edit_text = AsyncMock()

            from src.bot.handlers.payment import handle_payment_status_check
            await handle_payment_status_check(callback)

            # Verify status check
            mock_payment_service.get_payment_status.assert_called_once_with("test_payment_123")

            # Verify success response
            callback.message.edit_text.assert_called_once()
            edit_args = callback.message.edit_text.call_args[0][0]
            assert "Payment Successful" in edit_args

class TestReferralHandlerIntegration:
    """Integration tests for referral handler with complete referral flows."""

    @pytest.mark.asyncio
    async def test_complete_invite_flow(self, mock_session, sample_user):
        """Test complete invite generation flow."""
        with patch("src.bot.handlers.referral.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.referral.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            mock_user_service.generate_referral_link.return_value = "https://t.me/testbot?start=abc123"
            mock_user_service.get_referral_stats.return_value = {
                "referrals_count": 3,
                "trial_expires": sample_user.trial_expires,
                "subscription_expires": None
            }
            mock_user_service.referral_bonus_days = 3
            mock_user_service.default_trial_days = 7

            message = MagicMock()
            message.from_user.id = sample_user.tg_id
            message.from_user.first_name = sample_user.first_name
            message.answer = AsyncMock()

            # Mock bot info
            bot_info = MagicMock()
            bot_info.username = "testbot"
            message.bot.get_me = AsyncMock(return_value=bot_info)

            from src.bot.handlers.referral import invite_handler
            await invite_handler(message)

            # Verify referral link generation
            mock_user_service.generate_referral_link.assert_called_once_with("testbot", sample_user.id)

            # Verify response contains referral link
            message.answer.assert_called_once()
            response_text = message.answer.call_args[0][0]
            assert "https://t.me/testbot?start=abc123" in response_text
            assert "Referred users: **3**" in response_text

    @pytest.mark.asyncio
    async def test_referral_stats_integration(self, mock_session, sample_user):
        """Test referral statistics integration."""
        with patch("src.bot.handlers.referral.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.referral.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            mock_user_service.get_referral_stats.return_value = {
                "referrals_count": 5,
                "trial_expires": sample_user.trial_expires,
                "subscription_expires": None
            }
            mock_user_service.referral_bonus_days = 3

            message = MagicMock()
            message.from_user.id = sample_user.tg_id
            message.from_user.first_name = sample_user.first_name
            message.answer = AsyncMock()

            from src.bot.handlers.referral import referrals_stats_handler
            await referrals_stats_handler(message)

            # Verify stats retrieval
            mock_user_service.get_referral_stats.assert_called_once()

            # Verify response contains stats
            message.answer.assert_called_once()
            response_text = message.answer.call_args[0][0]
            assert "Total referrals: **5**" in response_text
            assert "Bonus days earned: **15** days" in response_text


class TestWebhookIntegration:
    """Integration tests for webhook processing."""

    @pytest.mark.asyncio
    async def test_payment_webhook_integration(self, mock_session, sample_payment, valid_webhook_signature):
        """Test complete payment webhook processing integration."""
        payload, signature, timestamp = valid_webhook_signature

        with patch("src.main.get_db_session") as mock_get_session, \
             patch("src.main.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_payment_service.process_webhook.return_value = (True, "Payment processed successfully")

            # Create FastAPI test client
            from fastapi.testclient import TestClient
            from src.main import app

            client = TestClient(app)

            # Send webhook request
            response = client.post(
                "/webhooks/yookassa",
                content=payload,
                headers={
                    "Yookassa-Signature": signature,
                    "Yookassa-Timestamp": timestamp,
                    "Content-Type": "application/json"
                }
            )

            # Verify webhook processing
            assert response.status_code == 200
            mock_payment_service.process_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_job_integration(self, mock_session):
        """Test background job execution integration."""
        with patch("src.tasks.search_tasks.vinted_service") as mock_vinted_service, \
             patch("src.tasks.search_tasks.get_db_session") as mock_get_session:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_vinted_service.search_and_get_details.return_value = [
                {
                    "id": 12345,
                    "title": "Test Item",
                    "price": 25.0,
                    "currency": "EUR",
                    "photos": ["photo1.jpg", "photo2.jpg"]
                }
            ]

            from src.tasks.search_tasks import process_search_task

            # Execute background search task
            result = await process_search_task(
                search_id="search_123",
                query="test query",
                user_id=123456789,
                max_pages=2
            )

            # Verify search execution
            mock_vinted_service.search_and_get_details.assert_called_once()
            assert result["status"] == "completed"
            assert len(result["items"]) == 1


class TestErrorHandlingIntegration:
    """Integration tests for error handling across handlers."""

    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_session, mock_database_error):
        """Test database error handling integration."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.side_effect = mock_database_error

            message = MagicMock()
            message.from_user.id = 123456789
            message.from_user.username = "testuser"
            message.from_user.first_name = "Test"
            message.answer = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart()
            await start_handler(message, command)

            # Verify error response
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "error" in call_args.lower()

    @pytest.mark.asyncio
    async def test_external_api_error_handling(self, mock_session):
        """Test external API error handling integration."""
        with patch("src.bot.handlers.payment.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.payment.user_service") as mock_user_service, \
             patch("src.bot.handlers.payment.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = MagicMock(id=1)
            mock_payment_service.create_payment.side_effect = Exception("YooKassa API error")

            callback = MagicMock()
            callback.data = "confirm_pay_30"
            callback.from_user.id = 123456789
            callback.answer = AsyncMock()
            callback.message.edit_text = AsyncMock()

            from src.bot.handlers.payment import handle_payment_confirmation
            await handle_payment_confirmation(callback)

            # Verify error handling
            callback.message.edit_text.assert_called_once()
            edit_args = callback.message.edit_text.call_args[0][0]
            assert "Failed to create payment" in edit_args


class TestStateManagementIntegration:
    """Integration tests for FSM state management."""

    @pytest.mark.asyncio
    async def test_search_state_flow_integration(self, mock_session):
        """Test complete search state flow integration."""
        with patch("src.bot.handlers.search.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.search.user_service") as mock_user_service, \
             patch("src.bot.handlers.search.search_task_manager") as mock_task_manager:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.is_premium_active.return_value = True
            mock_task_manager.queue_search_task.return_value = "search_123"

            # Test state transitions
            state = AsyncMock()

            # 1. Start search command
            message = MagicMock()
            message.from_user.id = 123456789
            message.answer = AsyncMock()

            from src.bot.handlers.search import search_command, SearchStates
            await search_command(message, state)

            # Verify state was set
            state.set_state.assert_called_once_with(SearchStates.waiting_for_query)

            # 2. Process search query
            message.text = "test query"
            search_msg = MagicMock()
            search_msg.message_id = 999
            message.answer.return_value = search_msg

            with patch("asyncio.create_task"), patch("asyncio.sleep"):
                from src.bot.handlers.search import process_search_query
                await process_search_query(message, state)

            # Verify state was cleared
            state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_user_handling(self, mock_session):
        """Test handling multiple concurrent users."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.create_user.side_effect = lambda **kwargs: User(
                id=kwargs["tg_id"],
                tg_id=kwargs["tg_id"],
                username=kwargs["username"],
                first_name=kwargs["first_name"],
                trial_expires=datetime.utcnow() + timedelta(days=7)
            )

            # Create multiple concurrent user requests
            tasks = []
            for i in range(5):
                message = MagicMock()
                message.from_user.id = 123456789 + i
                message.from_user.username = f"user{i}"
                message.from_user.first_name = f"User{i}"
                message.answer = AsyncMock()

                from src.bot.handlers.start import start_handler
                from aiogram.filters import CommandStart

                command = CommandStart()
                task = asyncio.create_task(start_handler(message, command))
                tasks.append((task, message))

            # Wait for all tasks to complete
            await asyncio.gather(*[task for task, _ in tasks])

            # Verify all users were created
            assert mock_user_service.create_user.call_count == 5

            # Verify all got responses
            for _, message in tasks:
                message.answer.assert_called_once()