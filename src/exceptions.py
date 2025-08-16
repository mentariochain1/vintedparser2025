"""
Custom exception hierarchy for the Vinted Parser Bot.

This module defines all custom exceptions used throughout the application,
providing clear error types for different failure scenarios.
"""

from typing import Optional, Dict, Any


class VintedBotError(Exception):
    """Base exception for all bot-related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseError(VintedBotError):
    """Database operation errors."""
    pass


class UserNotFoundError(DatabaseError):
    """User lookup errors."""
    pass


class PaymentError(VintedBotError):
    """Payment processing errors."""
    pass


class PaymentCreationError(PaymentError):
    """Payment creation failures."""
    pass


class PaymentVerificationError(PaymentError):
    """Payment verification failures."""
    pass


class WebhookError(VintedBotError):
    """Webhook processing errors."""
    pass


class InvalidWebhookSignatureError(WebhookError):
    """Invalid webhook signature errors."""
    pass


class VintedAPIError(VintedBotError):
    """Vinted API communication errors."""
    pass


class VintedRateLimitError(VintedAPIError):
    """Vinted API rate limit errors."""
    pass


class VintedServiceUnavailableError(VintedAPIError):
    """Vinted service unavailable errors."""
    pass


class NotificationError(VintedBotError):
    """Notification sending errors."""
    pass


class TelegramAPIError(VintedBotError):
    """Telegram API communication errors."""
    pass


class ReferralError(VintedBotError):
    """Referral processing errors."""
    pass


class InvalidReferralTokenError(ReferralError):
    """Invalid referral token errors."""
    pass


class ConfigurationError(VintedBotError):
    """Configuration and setup errors."""
    pass


class RateLimitError(VintedBotError):
    """Rate limiting errors."""
    pass


class CircuitBreakerError(VintedBotError):
    """Circuit breaker errors."""
    pass


class ServiceUnavailableError(VintedBotError):
    """Service unavailable errors."""
    pass


class ValidationError(VintedBotError):
    """Input validation errors."""
    pass