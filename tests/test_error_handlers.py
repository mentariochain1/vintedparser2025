"""Tests for error handling system."""

import pytest
from unittest.mock import Mock, patch
from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.exceptions import (
    VintedBotError, DatabaseError, UserNotFoundError, PaymentError,
    PaymentCreationError, VintedAPIError, VintedRateLimitError,
    CircuitBreakerError, ValidationError
)
from src.error_handlers import ErrorHandler, GracefulDegradation


class TestErrorHandler:
    """Test error handler functionality."""
    
    def test_get_user_friendly_message_known_error(self):
        """Test user-friendly message for known error types."""
        error = UserNotFoundError("User not found")
        message = ErrorHandler.get_user_friendly_message(error)
        assert message == "❌ User account not found. Please start the bot with /start"
    
    def test_get_user_friendly_message_vinted_bot_error(self):
        """Test user-friendly message for VintedBotError."""
        error = VintedBotError("Custom error message")
        message = ErrorHandler.get_user_friendly_message(error)
        assert message == "❌ Custom error message"
    
    def test_get_user_friendly_message_unknown_error(self):
        """Test user-friendly message for unknown error types."""
        error = ValueError("Some value error")
        message = ErrorHandler.get_user_friendly_message(error)
        assert message == "❌ An unexpected error occurred. Please try again later"
    
    def test_get_http_status_code_known_error(self):
        """Test HTTP status code for known error types."""
        error = UserNotFoundError("User not found")
        status_code = ErrorHandler.get_http_status_code(error)
        assert status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_http_status_code_rate_limit_error(self):
        """Test HTTP status code for rate limit error."""
        error = VintedRateLimitError("Rate limit exceeded")
        status_code = ErrorHandler.get_http_status_code(error)
        assert status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    def test_get_http_status_code_unknown_error(self):
        """Test HTTP status code for unknown error types."""
        error = ValueError("Some value error")
        status_code = ErrorHandler.get_http_status_code(error)
        assert status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('src.error_handlers.logger')
    def test_log_error_warning_level(self, mock_logger):
        """Test error logging with warning level."""
        error = CircuitBreakerError("Circuit breaker open")
        ErrorHandler.log_error(error, {"context": "test"})
        
        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == 30  # WARNING level
    
    @patch('src.error_handlers.logger')
    def test_log_error_info_level(self, mock_logger):
        """Test error logging with info level."""
        error = ValidationError("Invalid input")
        ErrorHandler.log_error(error, {"context": "test"})
        
        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == 20  # INFO level
    
    @patch('src.error_handlers.logger')
    def test_log_error_error_level(self, mock_logger):
        """Test error logging with error level."""
        error = DatabaseError("Database connection failed")
        ErrorHandler.log_error(error, {"context": "test"})
        
        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[0] == 40  # ERROR level
    
    def test_handle_telegram_error_forbidden(self):
        """Test handling Telegram forbidden error."""
        from aiogram.exceptions import TelegramForbiddenError
        
        error = TelegramForbiddenError("Forbidden: bot was blocked by the user")
        should_retry, message = ErrorHandler.handle_telegram_error(error, 12345)
        
        assert should_retry is False
        assert message == "User has blocked the bot"
    
    def test_handle_telegram_error_bad_request(self):
        """Test handling Telegram bad request error."""
        from aiogram.exceptions import TelegramBadRequest
        
        error = TelegramBadRequest("Bad Request: message not found")
        should_retry, message = ErrorHandler.handle_telegram_error(error, 12345)
        
        assert should_retry is False
        assert "Invalid Telegram request" in message
    
    def test_handle_telegram_error_network(self):
        """Test handling Telegram network error."""
        from aiogram.exceptions import TelegramNetworkError
        
        error = TelegramNetworkError("Network error")
        should_retry, message = ErrorHandler.handle_telegram_error(error, 12345)
        
        assert should_retry is True
        assert message == "Network error, will retry"
    
    def test_create_error_response_basic(self):
        """Test creating basic error response."""
        error = UserNotFoundError("User not found")
        response = ErrorHandler.create_error_response(error, "test-123")
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        content = response.body.decode()
        assert "User account not found" in content
        assert "test-123" in content
    
    def test_create_error_response_with_details(self):
        """Test creating error response with details."""
        error = VintedBotError("Test error", details={"key": "value"})
        response = ErrorHandler.create_error_response(error, "test-123", include_details=True)
        
        content = response.body.decode()
        assert "key" in content
        assert "value" in content


class TestGracefulDegradation:
    """Test graceful degradation strategies."""
    
    @pytest.mark.asyncio
    async def test_handle_vinted_unavailable(self):
        """Test handling Vinted service unavailability."""
        result = await GracefulDegradation.handle_vinted_unavailable()
        
        assert result["status"] == "degraded"
        assert "Search service temporarily unavailable" in result["message"]
        assert result["fallback"] == "cached_results"
        assert result["retry_after"] == 300
    
    @pytest.mark.asyncio
    async def test_handle_payment_unavailable(self):
        """Test handling payment service unavailability."""
        result = await GracefulDegradation.handle_payment_unavailable()
        
        assert result["status"] == "degraded"
        assert "Payment service temporarily unavailable" in result["message"]
        assert result["fallback"] == "manual_payment"
        assert result["retry_after"] == 600
    
    @pytest.mark.asyncio
    async def test_handle_notification_failure(self):
        """Test handling notification service failures."""
        result = await GracefulDegradation.handle_notification_failure(5)
        
        assert result["status"] == "degraded"
        assert "Failed to send notifications to 5 users" in result["message"]
        assert result["fallback"] == "retry_queue"
        assert result["retry_after"] == 180


class TestErrorIntegration:
    """Test error handling integration scenarios."""
    
    def test_payment_creation_error_chain(self):
        """Test payment creation error handling chain."""
        # Create a payment creation error
        error = PaymentCreationError(
            "Failed to create payment",
            details={"user_id": 12345, "amount": "100.00"}
        )
        
        # Test user-friendly message
        message = ErrorHandler.get_user_friendly_message(error)
        assert "Failed to create payment" in message
        
        # Test HTTP status code
        status_code = ErrorHandler.get_http_status_code(error)
        assert status_code == status.HTTP_402_PAYMENT_REQUIRED
        
        # Test error response creation
        response = ErrorHandler.create_error_response(error, "test-123", include_details=True)
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    
    def test_vinted_api_error_chain(self):
        """Test Vinted API error handling chain."""
        # Create a Vinted API error
        error = VintedAPIError(
            "API request failed",
            details={"query": "test search", "status_code": 500}
        )
        
        # Test user-friendly message
        message = ErrorHandler.get_user_friendly_message(error)
        assert "Search service error" in message
        
        # Test HTTP status code
        status_code = ErrorHandler.get_http_status_code(error)
        assert status_code == status.HTTP_502_BAD_GATEWAY
    
    def test_circuit_breaker_error_chain(self):
        """Test circuit breaker error handling chain."""
        # Create a circuit breaker error
        error = CircuitBreakerError(
            "Circuit breaker is open",
            details={"service": "vinted_api", "failure_count": 5}
        )
        
        # Test user-friendly message
        message = ErrorHandler.get_user_friendly_message(error)
        assert "Service temporarily unavailable" in message
        
        # Test HTTP status code
        status_code = ErrorHandler.get_http_status_code(error)
        assert status_code == status.HTTP_503_SERVICE_UNAVAILABLE