"""
Global error handlers for the Vinted Parser Bot.

Provides centralized error handling with user-friendly messages,
logging, and graceful degradation strategies.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError

from src.exceptions import (
    VintedBotError, DatabaseError, UserNotFoundError, PaymentError,
    PaymentCreationError, PaymentVerificationError, WebhookError,
    InvalidWebhookSignatureError, VintedAPIError, VintedRateLimitError,
    VintedServiceUnavailableError, NotificationError, TelegramAPIError,
    ReferralError, InvalidReferralTokenError, ConfigurationError,
    RateLimitError, CircuitBreakerError, ServiceUnavailableError,
    ValidationError
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling for the application."""
    
    @staticmethod
    def get_user_friendly_message(error: Exception) -> str:
        """
        Get user-friendly error message based on exception type.
        
        Args:
            error: Exception instance
            
        Returns:
            User-friendly error message
        """
        error_messages = {
            UserNotFoundError: "❌ User account not found. Please start the bot with /start",
            PaymentCreationError: "❌ Failed to create payment. Please try again later",
            PaymentVerificationError: "❌ Payment verification failed. Please contact support",
            InvalidWebhookSignatureError: "❌ Invalid request signature",
            VintedRateLimitError: "⏳ Too many requests. Please wait a moment and try again",
            VintedServiceUnavailableError: "🔧 Vinted service is temporarily unavailable. Please try again later",
            NotificationError: "📱 Failed to send notification. Your search results are still saved",
            TelegramAPIError: "📱 Telegram service error. Please try again",
            InvalidReferralTokenError: "❌ Invalid referral link. Please check the link and try again",
            RateLimitError: "⏳ Too many requests. Please wait before trying again",
            CircuitBreakerError: "🔧 Service temporarily unavailable. Please try again later",
            ServiceUnavailableError: "🔧 Service unavailable. Please try again later",
            ValidationError: "❌ Invalid input. Please check your data and try again",
            DatabaseError: "💾 Database error. Please try again later",
            VintedAPIError: "🔍 Search service error. Please try again",
            PaymentError: "💳 Payment processing error. Please try again",
            WebhookError: "🔗 Webhook processing error",
            ReferralError: "👥 Referral processing error. Please try again",
            TelegramForbiddenError: "🚫 Bot access denied. Please unblock the bot",
            TelegramBadRequest: "📱 Invalid request to Telegram",
            TelegramNetworkError: "🌐 Network error. Please try again"
        }
        
        # Check for specific error types
        for error_type, message in error_messages.items():
            if isinstance(error, error_type):
                return message
        
        # Check for generic VintedBotError
        if isinstance(error, VintedBotError):
            return f"❌ {error.message}"
        
        # Default message for unknown errors
        return "❌ An unexpected error occurred. Please try again later"
    
    @staticmethod
    def get_http_status_code(error: Exception) -> int:
        """
        Get appropriate HTTP status code for exception.
        
        Args:
            error: Exception instance
            
        Returns:
            HTTP status code
        """
        status_codes = {
            UserNotFoundError: status.HTTP_404_NOT_FOUND,
            InvalidWebhookSignatureError: status.HTTP_401_UNAUTHORIZED,
            ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
            RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
            VintedRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
            CircuitBreakerError: status.HTTP_503_SERVICE_UNAVAILABLE,
            ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
            VintedServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
            PaymentCreationError: status.HTTP_402_PAYMENT_REQUIRED,
            PaymentVerificationError: status.HTTP_400_BAD_REQUEST,
            DatabaseError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            VintedAPIError: status.HTTP_502_BAD_GATEWAY,
            TelegramAPIError: status.HTTP_502_BAD_GATEWAY,
            ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR
        }
        
        for error_type, status_code in status_codes.items():
            if isinstance(error, error_type):
                return status_code
        
        # Default to 500 for unknown errors
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @staticmethod
    def log_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log error with appropriate level and context.
        
        Args:
            error: Exception instance
            context: Additional context information
        """
        context = context or {}
        
        # Determine log level based on error type
        if isinstance(error, (RateLimitError, CircuitBreakerError)):
            log_level = logging.WARNING
        elif isinstance(error, (ValidationError, UserNotFoundError)):
            log_level = logging.INFO
        else:
            log_level = logging.ERROR
        
        # Log with context
        logger.log(
            log_level,
            f"{type(error).__name__}: {str(error)}",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "error_details": getattr(error, 'details', {}),
                **context
            }
        )
    
    @staticmethod
    def handle_telegram_error(error: Exception, user_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Handle Telegram-specific errors.
        
        Args:
            error: Exception instance
            user_id: User ID for context
            
        Returns:
            Tuple of (should_retry, error_message)
        """
        context = {"user_id": user_id} if user_id else {}
        
        if isinstance(error, TelegramForbiddenError):
            ErrorHandler.log_error(error, context)
            return False, "User has blocked the bot"
        
        elif isinstance(error, TelegramBadRequest):
            ErrorHandler.log_error(error, context)
            return False, f"Invalid Telegram request: {str(error)}"
        
        elif isinstance(error, TelegramNetworkError):
            ErrorHandler.log_error(error, context)
            return True, "Network error, will retry"
        
        else:
            ErrorHandler.log_error(error, context)
            return False, f"Telegram API error: {str(error)}"
    
    @staticmethod
    def create_error_response(
        error: Exception,
        request_id: Optional[str] = None,
        include_details: bool = False
    ) -> JSONResponse:
        """
        Create standardized error response.
        
        Args:
            error: Exception instance
            request_id: Request ID for tracking
            include_details: Whether to include error details
            
        Returns:
            JSONResponse with error information
        """
        status_code = ErrorHandler.get_http_status_code(error)
        message = ErrorHandler.get_user_friendly_message(error)
        
        response_data = {
            "error": True,
            "message": message,
            "error_type": type(error).__name__,
            "request_id": request_id
        }
        
        if include_details and isinstance(error, VintedBotError):
            response_data["details"] = error.details
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )


class GracefulDegradation:
    """Strategies for graceful service degradation."""
    
    @staticmethod
    async def handle_vinted_unavailable() -> Dict[str, Any]:
        """Handle Vinted service unavailability."""
        return {
            "status": "degraded",
            "message": "Search service temporarily unavailable",
            "fallback": "cached_results",
            "retry_after": 300  # 5 minutes
        }
    
    @staticmethod
    async def handle_payment_unavailable() -> Dict[str, Any]:
        """Handle payment service unavailability."""
        return {
            "status": "degraded",
            "message": "Payment service temporarily unavailable",
            "fallback": "manual_payment",
            "retry_after": 600  # 10 minutes
        }
    
    @staticmethod
    async def handle_notification_failure(user_count: int) -> Dict[str, Any]:
        """Handle notification service failures."""
        return {
            "status": "degraded",
            "message": f"Failed to send notifications to {user_count} users",
            "fallback": "retry_queue",
            "retry_after": 180  # 3 minutes
        }


# Global error handler instance
error_handler = ErrorHandler()