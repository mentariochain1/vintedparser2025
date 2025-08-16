"""
Secure session management for the Vinted Parser Bot.

Provides secure token generation, validation, and session handling
with proper expiration and security measures.
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json
import base64
import logging

from config import settings
from exceptions import ValidationError, InvalidReferralTokenError

logger = logging.getLogger(__name__)


class SecureTokenManager:
    """Manages secure token generation and validation."""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = (secret_key or settings.secret_key).encode('utf-8')
        self.token_ttl = 3600 * 24 * 14  # 14 days default TTL
    
    def generate_referral_token(self, user_id: int, expires_in: Optional[int] = None) -> str:
        """
        Generate a secure referral token.
        
        Args:
            user_id: User ID to encode in token
            expires_in: Token expiration time in seconds
            
        Returns:
            Secure referral token
        """
        expires_in = expires_in or self.token_ttl
        expires_at = int(time.time()) + expires_in
        
        # Create payload
        payload = {
            'user_id': user_id,
            'expires_at': expires_at,
            'nonce': secrets.token_hex(8)
        }
        
        # Encode payload
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
        
        # Create signature
        signature = hmac.new(
            self.secret_key,
            payload_b64.encode(),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        # Combine payload and signature
        token = f"{payload_b64}.{signature_b64}"
        
        logger.info(f"Generated referral token for user {user_id}, expires at {expires_at}")
        
        return token
    
    def validate_referral_token(self, token: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Validate a referral token.
        
        Args:
            token: Token to validate
            
        Returns:
            Tuple of (is_valid, user_id, error_message)
        """
        try:
            if not token or '.' not in token:
                return False, None, "Invalid token format"
            
            payload_b64, signature_b64 = token.split('.', 1)
            
            # Verify signature
            expected_signature = hmac.new(
                self.secret_key,
                payload_b64.encode(),
                hashlib.sha256
            ).digest()
            expected_signature_b64 = base64.urlsafe_b64encode(expected_signature).decode().rstrip('=')
            
            if not hmac.compare_digest(signature_b64, expected_signature_b64):
                return False, None, "Invalid token signature"
            
            # Decode payload
            payload_b64_padded = payload_b64 + '=' * (4 - len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64_padded).decode()
            payload = json.loads(payload_json)
            
            # Validate payload structure
            if not all(key in payload for key in ['user_id', 'expires_at', 'nonce']):
                return False, None, "Invalid token payload"
            
            user_id = payload['user_id']
            expires_at = payload['expires_at']
            
            # Check expiration
            if time.time() > expires_at:
                return False, None, "Token has expired"
            
            # Validate user_id
            if not isinstance(user_id, int) or user_id <= 0:
                return False, None, "Invalid user ID in token"
            
            logger.info(f"Successfully validated referral token for user {user_id}")
            return True, user_id, None
            
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Token validation error: {e}")
            return False, None, f"Token parsing error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error validating token: {e}")
            return False, None, "Token validation failed"
    
    def generate_session_token(self, user_id: int, session_data: Dict[str, Any]) -> str:
        """
        Generate a secure session token.
        
        Args:
            user_id: User ID
            session_data: Session data to encode
            
        Returns:
            Secure session token
        """
        expires_at = int(time.time()) + 3600  # 1 hour session
        
        payload = {
            'user_id': user_id,
            'expires_at': expires_at,
            'session_data': session_data,
            'nonce': secrets.token_hex(16)
        }
        
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
        
        signature = hmac.new(
            self.secret_key,
            payload_b64.encode(),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        return f"{payload_b64}.{signature_b64}"
    
    def validate_session_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate a session token.
        
        Args:
            token: Session token to validate
            
        Returns:
            Tuple of (is_valid, session_data, error_message)
        """
        try:
            if not token or '.' not in token:
                return False, None, "Invalid token format"
            
            payload_b64, signature_b64 = token.split('.', 1)
            
            # Verify signature
            expected_signature = hmac.new(
                self.secret_key,
                payload_b64.encode(),
                hashlib.sha256
            ).digest()
            expected_signature_b64 = base64.urlsafe_b64encode(expected_signature).decode().rstrip('=')
            
            if not hmac.compare_digest(signature_b64, expected_signature_b64):
                return False, None, "Invalid token signature"
            
            # Decode payload
            payload_b64_padded = payload_b64 + '=' * (4 - len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64_padded).decode()
            payload = json.loads(payload_json)
            
            # Check expiration
            if time.time() > payload.get('expires_at', 0):
                return False, None, "Session has expired"
            
            return True, payload, None
            
        except Exception as e:
            logger.error(f"Session token validation error: {e}")
            return False, None, "Session validation failed"


class WebhookSignatureValidator:
    """Validates webhook signatures for security."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode('utf-8')
    
    def validate_telegram_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Validate Telegram webhook signature.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from X-Telegram-Bot-Api-Secret-Token header
            
        Returns:
            True if signature is valid
        """
        try:
            expected_signature = hmac.new(
                self.secret_key,
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Telegram webhook signature validation error: {e}")
            return False
    
    def validate_yookassa_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Validate YooKassa webhook signature.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from request headers
            
        Returns:
            True if signature is valid
        """
        try:
            expected_signature = hmac.new(
                self.secret_key,
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature.lower(), expected_signature.lower())
            
        except Exception as e:
            logger.error(f"YooKassa webhook signature validation error: {e}")
            return False


class SecurityHeaders:
    """Manages security headers for HTTP responses."""
    
    @staticmethod
    def get_security_headers(is_production: bool = True) -> Dict[str, str]:
        """
        Get security headers for HTTP responses.
        
        Args:
            is_production: Whether running in production mode
            
        Returns:
            Dictionary of security headers
        """
        headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none';",
        }
        
        if is_production:
            headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return headers


class InputSanitizer:
    """Sanitizes user input to prevent injection attacks."""
    
    @staticmethod
    def sanitize_sql_input(value: str) -> str:
        """
        Sanitize input for SQL queries.
        
        Args:
            value: Input value to sanitize
            
        Returns:
            Sanitized value
        """
        if not isinstance(value, str):
            return str(value)
        
        # Remove or escape dangerous characters
        dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
        
        for char in dangerous_chars:
            value = value.replace(char, '')
        
        return value.strip()
    
    @staticmethod
    def sanitize_html_input(value: str) -> str:
        """
        Sanitize HTML input to prevent XSS.
        
        Args:
            value: Input value to sanitize
            
        Returns:
            Sanitized value
        """
        if not isinstance(value, str):
            return str(value)
        
        # HTML entity encoding - order matters, & must be first
        replacements = [
            ('&', '&amp;'),
            ('<', '&lt;'),
            ('>', '&gt;'),
            ('"', '&quot;'),
            ("'", '&#x27;'),
            ('/', '&#x2F;')
        ]
        
        for char, replacement in replacements:
            value = value.replace(char, replacement)
        
        return value
    
    @staticmethod
    def validate_telegram_user_input(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize Telegram user input.
        
        Args:
            user_data: User data from Telegram
            
        Returns:
            Sanitized user data
        """
        sanitized = {}
        
        # Validate user ID
        user_id = user_data.get('id')
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValidationError("Invalid user ID")
        sanitized['id'] = user_id
        
        # Sanitize text fields
        text_fields = ['username', 'first_name', 'last_name']
        for field in text_fields:
            value = user_data.get(field)
            if value:
                sanitized[field] = InputSanitizer.sanitize_html_input(str(value)[:64])
        
        return sanitized


# Global instances
token_manager = SecureTokenManager()
webhook_validator = WebhookSignatureValidator(settings.webhook_secret)
security_headers = SecurityHeaders()
input_sanitizer = InputSanitizer()