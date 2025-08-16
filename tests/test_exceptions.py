"""Tests for custom exception hierarchy."""

import pytest

from src.exceptions import (
    VintedBotError, DatabaseError, UserNotFoundError, PaymentError,
    PaymentCreationError, PaymentVerificationError, WebhookError,
    InvalidWebhookSignatureError, VintedAPIError, VintedRateLimitError,
    VintedServiceUnavailableError, NotificationError, TelegramAPIError,
    ReferralError, InvalidReferralTokenError, ConfigurationError,
    RateLimitError, CircuitBreakerError, ServiceUnavailableError,
    ValidationError
)


class TestVintedBotError:
    """Test base VintedBotError class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = VintedBotError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details == {}
    
    def test_error_with_details(self):
        """Test error creation with details."""
        details = {"user_id": 12345, "action": "search"}
        error = VintedBotError("Test error", details=details)
        
        assert error.message == "Test error"
        assert error.details == details
        assert error.details["user_id"] == 12345
    
    def test_error_inheritance(self):
        """Test that VintedBotError inherits from Exception."""
        error = VintedBotError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, VintedBotError)


class TestDatabaseErrors:
    """Test database-related errors."""
    
    def test_database_error(self):
        """Test DatabaseError creation."""
        error = DatabaseError("Database connection failed")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Database connection failed"
    
    def test_user_not_found_error(self):
        """Test UserNotFoundError creation."""
        error = UserNotFoundError("User 12345 not found")
        
        assert isinstance(error, DatabaseError)
        assert isinstance(error, VintedBotError)
        assert str(error) == "User 12345 not found"


class TestPaymentErrors:
    """Test payment-related errors."""
    
    def test_payment_error(self):
        """Test PaymentError creation."""
        error = PaymentError("Payment processing failed")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Payment processing failed"
    
    def test_payment_creation_error(self):
        """Test PaymentCreationError creation."""
        details = {"amount": "100.00", "currency": "RUB"}
        error = PaymentCreationError("Failed to create payment", details=details)
        
        assert isinstance(error, PaymentError)
        assert isinstance(error, VintedBotError)
        assert error.details["amount"] == "100.00"
    
    def test_payment_verification_error(self):
        """Test PaymentVerificationError creation."""
        error = PaymentVerificationError("Invalid payment signature")
        
        assert isinstance(error, PaymentError)
        assert isinstance(error, VintedBotError)


class TestWebhookErrors:
    """Test webhook-related errors."""
    
    def test_webhook_error(self):
        """Test WebhookError creation."""
        error = WebhookError("Webhook processing failed")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Webhook processing failed"
    
    def test_invalid_webhook_signature_error(self):
        """Test InvalidWebhookSignatureError creation."""
        error = InvalidWebhookSignatureError("Invalid webhook signature")
        
        assert isinstance(error, WebhookError)
        assert isinstance(error, VintedBotError)


class TestVintedAPIErrors:
    """Test Vinted API-related errors."""
    
    def test_vinted_api_error(self):
        """Test VintedAPIError creation."""
        error = VintedAPIError("Vinted API request failed")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Vinted API request failed"
    
    def test_vinted_rate_limit_error(self):
        """Test VintedRateLimitError creation."""
        details = {"retry_after": 60}
        error = VintedRateLimitError("Rate limit exceeded", details=details)
        
        assert isinstance(error, VintedAPIError)
        assert isinstance(error, VintedBotError)
        assert error.details["retry_after"] == 60
    
    def test_vinted_service_unavailable_error(self):
        """Test VintedServiceUnavailableError creation."""
        error = VintedServiceUnavailableError("Vinted service is down")
        
        assert isinstance(error, VintedAPIError)
        assert isinstance(error, VintedBotError)


class TestNotificationErrors:
    """Test notification-related errors."""
    
    def test_notification_error(self):
        """Test NotificationError creation."""
        error = NotificationError("Failed to send notification")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Failed to send notification"


class TestTelegramAPIErrors:
    """Test Telegram API-related errors."""
    
    def test_telegram_api_error(self):
        """Test TelegramAPIError creation."""
        error = TelegramAPIError("Telegram API error")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Telegram API error"


class TestReferralErrors:
    """Test referral-related errors."""
    
    def test_referral_error(self):
        """Test ReferralError creation."""
        error = ReferralError("Referral processing failed")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Referral processing failed"
    
    def test_invalid_referral_token_error(self):
        """Test InvalidReferralTokenError creation."""
        error = InvalidReferralTokenError("Invalid referral token")
        
        assert isinstance(error, ReferralError)
        assert isinstance(error, VintedBotError)


class TestSystemErrors:
    """Test system-related errors."""
    
    def test_configuration_error(self):
        """Test ConfigurationError creation."""
        error = ConfigurationError("Invalid configuration")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Invalid configuration"
    
    def test_rate_limit_error(self):
        """Test RateLimitError creation."""
        details = {"limit": 100, "window": 60}
        error = RateLimitError("Rate limit exceeded", details=details)
        
        assert isinstance(error, VintedBotError)
        assert error.details["limit"] == 100
    
    def test_circuit_breaker_error(self):
        """Test CircuitBreakerError creation."""
        details = {"service": "vinted_api", "state": "open"}
        error = CircuitBreakerError("Circuit breaker is open", details=details)
        
        assert isinstance(error, VintedBotError)
        assert error.details["service"] == "vinted_api"
    
    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError creation."""
        error = ServiceUnavailableError("Service temporarily unavailable")
        
        assert isinstance(error, VintedBotError)
        assert str(error) == "Service temporarily unavailable"
    
    def test_validation_error(self):
        """Test ValidationError creation."""
        details = {"field": "email", "value": "invalid-email"}
        error = ValidationError("Invalid input", details=details)
        
        assert isinstance(error, VintedBotError)
        assert error.details["field"] == "email"


class TestErrorHierarchy:
    """Test error inheritance hierarchy."""
    
    def test_all_errors_inherit_from_vinted_bot_error(self):
        """Test that all custom errors inherit from VintedBotError."""
        error_classes = [
            DatabaseError, UserNotFoundError, PaymentError,
            PaymentCreationError, PaymentVerificationError, WebhookError,
            InvalidWebhookSignatureError, VintedAPIError, VintedRateLimitError,
            VintedServiceUnavailableError, NotificationError, TelegramAPIError,
            ReferralError, InvalidReferralTokenError, ConfigurationError,
            RateLimitError, CircuitBreakerError, ServiceUnavailableError,
            ValidationError
        ]
        
        for error_class in error_classes:
            error = error_class("Test message")
            assert isinstance(error, VintedBotError)
            assert isinstance(error, Exception)
    
    def test_specific_inheritance_chains(self):
        """Test specific inheritance chains."""
        # Database errors
        user_error = UserNotFoundError("User not found")
        assert isinstance(user_error, DatabaseError)
        assert isinstance(user_error, VintedBotError)
        
        # Payment errors
        payment_creation_error = PaymentCreationError("Creation failed")
        assert isinstance(payment_creation_error, PaymentError)
        assert isinstance(payment_creation_error, VintedBotError)
        
        payment_verification_error = PaymentVerificationError("Verification failed")
        assert isinstance(payment_verification_error, PaymentError)
        assert isinstance(payment_verification_error, VintedBotError)
        
        # Webhook errors
        signature_error = InvalidWebhookSignatureError("Invalid signature")
        assert isinstance(signature_error, WebhookError)
        assert isinstance(signature_error, VintedBotError)
        
        # Vinted API errors
        rate_limit_error = VintedRateLimitError("Rate limited")
        assert isinstance(rate_limit_error, VintedAPIError)
        assert isinstance(rate_limit_error, VintedBotError)
        
        service_unavailable_error = VintedServiceUnavailableError("Service down")
        assert isinstance(service_unavailable_error, VintedAPIError)
        assert isinstance(service_unavailable_error, VintedBotError)
        
        # Referral errors
        invalid_token_error = InvalidReferralTokenError("Invalid token")
        assert isinstance(invalid_token_error, ReferralError)
        assert isinstance(invalid_token_error, VintedBotError)


class TestErrorUsagePatterns:
    """Test common error usage patterns."""
    
    def test_error_with_context(self):
        """Test error creation with contextual information."""
        error = VintedAPIError(
            "Search request failed",
            details={
                "query": "vintage sneakers",
                "status_code": 500,
                "retry_count": 3,
                "timestamp": "2025-01-01T12:00:00Z"
            }
        )
        
        assert "Search request failed" in str(error)
        assert error.details["query"] == "vintage sneakers"
        assert error.details["status_code"] == 500
        assert error.details["retry_count"] == 3
    
    def test_error_chaining(self):
        """Test error chaining with original exception."""
        original_error = ConnectionError("Network unreachable")
        
        try:
            raise original_error
        except ConnectionError as e:
            wrapped_error = VintedAPIError(
                "Failed to connect to Vinted API",
                details={"original_error": str(e), "error_type": type(e).__name__}
            )
        
        assert "Failed to connect to Vinted API" in str(wrapped_error)
        assert wrapped_error.details["original_error"] == "Network unreachable"
        assert wrapped_error.details["error_type"] == "ConnectionError"
    
    def test_error_serialization(self):
        """Test error serialization for logging/monitoring."""
        error = PaymentCreationError(
            "Payment creation failed",
            details={
                "user_id": 12345,
                "amount": "100.00",
                "currency": "RUB",
                "payment_method": "bank_card"
            }
        )
        
        # Test that error can be converted to dict-like structure
        error_data = {
            "error_type": type(error).__name__,
            "message": error.message,
            "details": error.details
        }
        
        assert error_data["error_type"] == "PaymentCreationError"
        assert error_data["message"] == "Payment creation failed"
        assert error_data["details"]["user_id"] == 12345