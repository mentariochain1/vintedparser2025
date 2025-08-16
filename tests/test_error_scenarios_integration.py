"""Integration tests for error scenarios and edge cases."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import User


class TestDatabaseErrorIntegration:
    """Integration tests for database error handling."""

    @pytest.mark.asyncio
    async def test_database_connection_failure(self, mock_database_error):
        """Test handler behavior when database connection fails."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session:
            mock_get_session.side_effect = mock_database_error

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
            assert "error" in call_args.lower() or "sorry" in call_args.lower()

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self, mock_session, mock_database_error):
        """Test database transaction rollback on error."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.create_user.side_effect = mock_database_error

            message = MagicMock()
            message.from_user.id = 123456789
            message.from_user.username = "testuser"
            message.from_user.first_name = "Test"
            message.answer = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart()
            await start_handler(message, command)

            # Verify rollback was called
            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self, mock_session):
        """Test concurrent database operations don't interfere."""
        import asyncio

        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            
            # Simulate slow database operation
            async def slow_create_user(**kwargs):
                await asyncio.sleep(0.1)
                return User(
                    id=kwargs["tg_id"],
                    tg_id=kwargs["tg_id"],
                    username=kwargs["username"],
                    first_name=kwargs["first_name"],
                    trial_expires=datetime.utcnow() + timedelta(days=7)
                )
            
            mock_user_service.create_user.side_effect = slow_create_user

            # Create concurrent requests
            tasks = []
            for i in range(3):
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

            # Wait for all tasks
            await asyncio.gather(*[task for task, _ in tasks])

            # Verify all operations completed
            assert mock_user_service.create_user.call_count == 3
            for _, message in tasks:
                message.answer.assert_called_once()


class TestExternalAPIErrorIntegration:
    """Integration tests for external API error handling."""

    @pytest.mark.asyncio
    async def test_vinted_api_failure(self, mock_session):
        """Test handling of Vinted API failures."""
        with patch("src.tasks.search_tasks.vinted_service") as mock_vinted_service, \
             patch("src.tasks.search_tasks.get_db_session") as mock_get_session:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_vinted_service.search_and_get_details.side_effect = Exception("Vinted API unavailable")

            from src.tasks.search_tasks import process_search_task

            result = await process_search_task(
                search_id="search_123",
                query="test query",
                user_id=123456789,
                max_pages=1
            )

            # Verify error handling
            assert result["status"] == "failed"
            assert "Vinted API unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_yookassa_api_failure(self, mock_session, sample_user):
        """Test handling of YooKassa API failures."""
        with patch("src.bot.handlers.payment.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.payment.user_service") as mock_user_service, \
             patch("src.bot.handlers.payment.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            mock_payment_service.create_payment.side_effect = Exception("YooKassa API error")

            callback = MagicMock()
            callback.data = "confirm_pay_30"
            callback.from_user.id = sample_user.tg_id
            callback.answer = AsyncMock()
            callback.message.edit_text = AsyncMock()

            from src.bot.handlers.payment import handle_payment_confirmation
            await handle_payment_confirmation(callback)

            # Verify error response
            callback.message.edit_text.assert_called_once()
            edit_args = callback.message.edit_text.call_args[0][0]
            assert "Failed to create payment" in edit_args

    @pytest.mark.asyncio
    async def test_telegram_api_failure(self, mock_session, sample_user):
        """Test handling of Telegram API failures."""
        with patch("src.bot.handlers.referral.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.referral.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            mock_user_service.generate_referral_link.return_value = "https://t.me/bot?start=abc"
            mock_user_service.get_referral_stats.return_value = {
                "referrals_count": 0,
                "trial_expires": sample_user.trial_expires,
                "subscription_expires": None
            }

            message = MagicMock()
            message.from_user.id = sample_user.tg_id
            message.from_user.first_name = sample_user.first_name
            message.answer = AsyncMock()
            message.answer.side_effect = Exception("Telegram API error")

            # Mock bot info
            bot_info = MagicMock()
            bot_info.username = "testbot"
            message.bot.get_me = AsyncMock(return_value=bot_info)

            from src.bot.handlers.referral import invite_handler

            # Should not raise exception
            await invite_handler(message)

            # Verify attempt was made
            message.answer.assert_called_once()


class TestRateLimitingIntegration:
    """Integration tests for rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_search_rate_limiting(self, mock_session):
        """Test search rate limiting integration."""
        with patch("src.bot.handlers.search.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.search.user_service") as mock_user_service, \
             patch("src.bot.handlers.search.search_task_manager") as mock_task_manager:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.is_premium_active.return_value = True
            
            # Simulate rate limit exceeded
            from src.exceptions import RateLimitError
            mock_task_manager.queue_search_task.side_effect = RateLimitError("Rate limit exceeded")

            message = MagicMock()
            message.text = "test query"
            message.from_user.id = 123456789
            message.chat.id = 987654321
            message.answer = AsyncMock()

            state = AsyncMock()

            from src.bot.handlers.search import process_search_query
            await process_search_query(message, state)

            # Verify rate limit response
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "rate limit" in call_args.lower() or "too many" in call_args.lower()

    @pytest.mark.asyncio
    async def test_payment_rate_limiting(self, mock_session, sample_user):
        """Test payment creation rate limiting."""
        with patch("src.bot.handlers.payment.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.payment.user_service") as mock_user_service, \
             patch("src.bot.handlers.payment.payment_service") as mock_payment_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = sample_user
            
            # Simulate rate limit from YooKassa
            from yookassa.domain.exceptions import ApiError
            mock_payment_service.create_payment.side_effect = ApiError("Rate limit exceeded")

            callback = MagicMock()
            callback.data = "confirm_pay_30"
            callback.from_user.id = sample_user.tg_id
            callback.answer = AsyncMock()
            callback.message.edit_text = AsyncMock()

            from src.bot.handlers.payment import handle_payment_confirmation
            await handle_payment_confirmation(callback)

            # Verify rate limit handling
            callback.message.edit_text.assert_called_once()
            edit_args = callback.message.edit_text.call_args[0][0]
            assert "rate limit" in edit_args.lower() or "try again" in edit_args.lower()


class TestEdgeCaseIntegration:
    """Integration tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_very_long_search_query(self, mock_session):
        """Test handling of very long search queries."""
        with patch("src.bot.handlers.search.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.search.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.is_premium_active.return_value = True

            message = MagicMock()
            message.text = "a" * 1000  # Very long query
            message.from_user.id = 123456789
            message.answer = AsyncMock()

            state = AsyncMock()

            from src.bot.handlers.search import process_search_query
            await process_search_query(message, state)

            # Verify query length validation
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "too long" in call_args.lower()

    @pytest.mark.asyncio
    async def test_special_characters_in_input(self, mock_session):
        """Test handling of special characters in user input."""
        with patch("src.bot.handlers.search.get_db_session") as mock_get_session, \
             patch("src.bot.handlers.search.user_service") as mock_user_service, \
             patch("src.bot.handlers.search.search_task_manager") as mock_task_manager:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.is_premium_active.return_value = True
            mock_task_manager.queue_search_task.return_value = "search_123"

            message = MagicMock()
            message.text = "test <script>alert('xss')</script> query"
            message.from_user.id = 123456789
            message.chat.id = 987654321
            message.answer = AsyncMock()

            search_msg = MagicMock()
            search_msg.message_id = 999
            message.answer.return_value = search_msg

            state = AsyncMock()

            with patch("asyncio.create_task"), patch("asyncio.sleep"):
                from src.bot.handlers.search import process_search_query
                await process_search_query(message, state)

            # Verify search was processed (input sanitization should happen in service layer)
            mock_task_manager.queue_search_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_without_username(self, mock_session):
        """Test handling of users without username."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.create_user.return_value = User(
                id=1,
                tg_id=123456789,
                username=None,  # No username
                first_name="Test",
                trial_expires=datetime.utcnow() + timedelta(days=7)
            )

            message = MagicMock()
            message.from_user.id = 123456789
            message.from_user.username = None  # No username
            message.from_user.first_name = "Test"
            message.answer = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart()
            await start_handler(message, command)

            # Verify user creation with None username
            mock_user_service.create_user.assert_called_once_with(
                session=mock_session,
                tg_id=123456789,
                username=None,
                first_name="Test",
                referrer_id=None
            )

    @pytest.mark.asyncio
    async def test_empty_search_results(self, mock_session):
        """Test handling of empty search results."""
        with patch("src.tasks.search_tasks.vinted_service") as mock_vinted_service, \
             patch("src.tasks.search_tasks.get_db_session") as mock_get_session:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_vinted_service.search_and_get_details.return_value = []  # Empty results

            from src.tasks.search_tasks import process_search_task

            result = await process_search_task(
                search_id="search_123",
                query="nonexistent item",
                user_id=123456789,
                max_pages=1
            )

            # Verify empty results handling
            assert result["status"] == "completed"
            assert result["total_items"] == 0
            assert len(result["items"]) == 0

    @pytest.mark.asyncio
    async def test_malformed_callback_data(self, mock_session):
        """Test handling of malformed callback data."""
        callback = MagicMock()
        callback.data = "invalid_callback_format"
        callback.from_user.id = 123456789
        callback.answer = AsyncMock()

        from src.bot.handlers.payment import handle_payment_callback
        await handle_payment_callback(callback)

        # Verify error response
        callback.answer.assert_called_once()
        answer_args = callback.answer.call_args[1]
        assert answer_args.get("show_alert") is True
        assert "invalid" in answer_args.get("text", "").lower()

    @pytest.mark.asyncio
    async def test_expired_referral_payload(self, mock_session):
        """Test handling of expired referral payload."""
        with patch("src.bot.handlers.start.get_session") as mock_get_session, \
             patch("src.bot.handlers.start.user_service") as mock_user_service:

            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_user_service.get_user.return_value = None
            mock_user_service.decode_referral_payload.return_value = None  # Expired/invalid
            mock_user_service.create_user.return_value = User(
                id=1,
                tg_id=123456789,
                username="testuser",
                first_name="Test",
                trial_expires=datetime.utcnow() + timedelta(days=7)
            )

            message = MagicMock()
            message.from_user.id = 123456789
            message.from_user.username = "testuser"
            message.from_user.first_name = "Test"
            message.answer = AsyncMock()

            from src.bot.handlers.start import start_handler
            from aiogram.filters import CommandStart

            command = CommandStart(args="expired_payload")
            await start_handler(message, command)

            # Verify user creation without referral
            mock_user_service.create_user.assert_called_once_with(
                session=mock_session,
                tg_id=123456789,
                username="testuser",
                first_name="Test",
                referrer_id=None
            )

            # Verify no referral processing
            mock_user_service.process_referral.assert_not_called()