"""Tests for security measures."""

import pytest
import time
import json
import base64
import hmac
import hashlib
from unittest.mock import patch, Mock

from src.security.session_manager import (
    SecureTokenManager, WebhookSignatureValidator,
    SecurityHeaders, InputSanitizer
)
from src.validation import (
    TelegramUserInput, SearchQueryInput, PaymentInput,
    WebhookInput, validate_input, sanitize_html
)
from src.exceptions import ValidationError


class TestSecureTokenManager:
    """Test secure token management."""
    
    def test_generate_referral_token(self):
        """Test referral token generation."""
        token_manager = SecureTokenManager("test_secret")
        
        token = token_manager.generate_referral_token(12345)
        
        assert isinstance(token, str)
        assert '.' in token
        assert len(token) > 20
    
    def test_validate_referral_token_success(self):
        """Test successful referral token validation."""
        token_manager = SecureTokenManager("test_secret")
        
        token = token_manager.generate_referral_token(12345)
        is_valid, user_id, error = token_manager.validate_referral_token(token)
        
        assert is_valid is True
        assert user_id == 12345
        assert error is None
    
    def test_validate_referral_token_expired(self):
        """Test expired referral token validation."""
        token_manager = SecureTokenManager("test_secret")
        
        # Generate token with very short expiration
        token = token_manager.generate_referral_token(12345, expires_in=1)
        
        # Wait for expiration
        time.sleep(2)
        
        is_valid, user_id, error = token_manager.validate_referral_token(token)
        
        assert is_valid is False
        assert user_id is None
        assert "expired" in error.lower()
    
    def test_validate_referral_token_invalid_signature(self):
        """Test referral token with invalid signature."""
        token_manager = SecureTokenManager("test_secret")
        
        token = token_manager.generate_referral_token(12345)
        
        # Tamper with token
        tampered_token = token[:-5] + "XXXXX"
        
        is_valid, user_id, error = token_manager.validate_referral_token(tampered_token)
        
        assert is_valid is False
        assert user_id is None
        assert "signature" in error.lower()
    
    def test_validate_referral_token_malformed(self):
        """Test malformed referral token validation."""
        token_manager = SecureTokenManager("test_secret")
        
        malformed_tokens = [
            "",
            "invalid",
            "no.dots.here.invalid",
            "invalid_base64.invalid_base64"
        ]
        
        for token in malformed_tokens:
            is_valid, user_id, error = token_manager.validate_referral_token(token)
            assert is_valid is False
            assert user_id is None
            assert error is not None
    
    def test_generate_session_token(self):
        """Test session token generation."""
        token_manager = SecureTokenManager("test_secret")
        
        session_data = {"role": "user", "permissions": ["search"]}
        token = token_manager.generate_session_token(12345, session_data)
        
        assert isinstance(token, str)
        assert '.' in token
    
    def test_validate_session_token_success(self):
        """Test successful session token validation."""
        token_manager = SecureTokenManager("test_secret")
        
        session_data = {"role": "user", "permissions": ["search"]}
        token = token_manager.generate_session_token(12345, session_data)
        
        is_valid, payload, error = token_manager.validate_session_token(token)
        
        assert is_valid is True
        assert payload["user_id"] == 12345
        assert payload["session_data"] == session_data
        assert error is None


class TestWebhookSignatureValidator:
    """Test webhook signature validation."""
    
    def test_validate_telegram_webhook_success(self):
        """Test successful Telegram webhook validation."""
        validator = WebhookSignatureValidator("test_secret")
        
        payload = b'{"update_id": 123, "message": {"text": "test"}}'
        
        # Generate expected signature
        expected_signature = hmac.new(
            b"test_secret",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = validator.validate_telegram_webhook(payload, expected_signature)
        
        assert is_valid is True
    
    def test_validate_telegram_webhook_invalid(self):
        """Test invalid Telegram webhook validation."""
        validator = WebhookSignatureValidator("test_secret")
        
        payload = b'{"update_id": 123, "message": {"text": "test"}}'
        invalid_signature = "invalid_signature"
        
        is_valid = validator.validate_telegram_webhook(payload, invalid_signature)
        
        assert is_valid is False
    
    def test_validate_yookassa_webhook_success(self):
        """Test successful YooKassa webhook validation."""
        validator = WebhookSignatureValidator("test_secret")
        
        payload = b'{"event": "payment.succeeded", "object": {"id": "test"}}'
        
        # Generate expected signature
        expected_signature = hmac.new(
            b"test_secret",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = validator.validate_yookassa_webhook(payload, expected_signature)
        
        assert is_valid is True
    
    def test_validate_yookassa_webhook_case_insensitive(self):
        """Test YooKassa webhook validation is case insensitive."""
        validator = WebhookSignatureValidator("test_secret")
        
        payload = b'{"event": "payment.succeeded"}'
        
        signature = hmac.new(
            b"test_secret",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Test with uppercase signature
        is_valid = validator.validate_yookassa_webhook(payload, signature.upper())
        assert is_valid is True


class TestSecurityHeaders:
    """Test security headers."""
    
    def test_get_security_headers_production(self):
        """Test security headers for production."""
        headers = SecurityHeaders.get_security_headers(is_production=True)
        
        assert 'X-Content-Type-Options' in headers
        assert 'X-Frame-Options' in headers
        assert 'X-XSS-Protection' in headers
        assert 'Strict-Transport-Security' in headers
        assert 'Content-Security-Policy' in headers
        
        assert headers['X-Content-Type-Options'] == 'nosniff'
        assert headers['X-Frame-Options'] == 'DENY'
    
    def test_get_security_headers_development(self):
        """Test security headers for development."""
        headers = SecurityHeaders.get_security_headers(is_production=False)
        
        assert 'X-Content-Type-Options' in headers
        assert 'X-Frame-Options' in headers
        assert 'Strict-Transport-Security' not in headers


class TestInputSanitizer:
    """Test input sanitization."""
    
    def test_sanitize_sql_input(self):
        """Test SQL input sanitization."""
        dangerous_inputs = [
            "'; DROP TABLE users; --",
            "admin'--",
            "1' OR '1'='1",
            "test/*comment*/",
            "xp_cmdshell"
        ]
        
        for dangerous_input in dangerous_inputs:
            sanitized = InputSanitizer.sanitize_sql_input(dangerous_input)
            
            # Should not contain dangerous characters
            assert "'" not in sanitized
            assert '"' not in sanitized
            assert ';' not in sanitized
            assert '--' not in sanitized
            assert '/*' not in sanitized
            assert '*/' not in sanitized
    
    def test_sanitize_html_input(self):
        """Test HTML input sanitization."""
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>",
            "test & <test> \"test\" 'test'"
        ]
        
        expected_safe = [
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;&#x2F;script&gt;",
            "&lt;img src=x onerror=alert(1)&gt;",
            "javascript:alert(&#x27;xss&#x27;)",
            "&lt;iframe src=&#x27;evil.com&#x27;&gt;&lt;&#x2F;iframe&gt;",
            "test &amp; &lt;test&gt; &quot;test&quot; &#x27;test&#x27;"
        ]
        
        for dangerous_input, expected in zip(dangerous_inputs, expected_safe):
            sanitized = InputSanitizer.sanitize_html_input(dangerous_input)
            assert sanitized == expected
    
    def test_validate_telegram_user_input_valid(self):
        """Test valid Telegram user input validation."""
        user_data = {
            'id': 12345,
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        sanitized = InputSanitizer.validate_telegram_user_input(user_data)
        
        assert sanitized['id'] == 12345
        assert sanitized['username'] == 'testuser'
        assert sanitized['first_name'] == 'Test'
        assert sanitized['last_name'] == 'User'
    
    def test_validate_telegram_user_input_invalid_id(self):
        """Test invalid Telegram user ID validation."""
        user_data = {'id': -1}
        
        with pytest.raises(ValidationError) as exc_info:
            InputSanitizer.validate_telegram_user_input(user_data)
        
        assert "Invalid user ID" in str(exc_info.value)
    
    def test_validate_telegram_user_input_xss_attempt(self):
        """Test XSS attempt in Telegram user input."""
        user_data = {
            'id': 12345,
            'first_name': '<script>alert("xss")</script>',
            'last_name': '<img src=x onerror=alert(1)>'
        }
        
        sanitized = InputSanitizer.validate_telegram_user_input(user_data)
        
        assert '<script>' not in sanitized['first_name']
        assert '<img' not in sanitized['last_name']
        assert '&lt;' in sanitized['first_name']
        assert '&lt;' in sanitized['last_name']


class TestInputValidation:
    """Test Pydantic input validation models."""
    
    def test_telegram_user_input_valid(self):
        """Test valid Telegram user input."""
        data = {
            'user_id': 12345,
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        validated = validate_input(data, TelegramUserInput)
        
        assert validated.user_id == 12345
        assert validated.username == 'testuser'
    
    def test_telegram_user_input_invalid_username(self):
        """Test invalid Telegram username."""
        data = {
            'user_id': 12345,
            'username': 'test@user!'  # Invalid characters
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, TelegramUserInput)
    
    def test_search_query_input_valid(self):
        """Test valid search query input."""
        data = {
            'query': 'vintage sneakers',
            'max_pages': 5,
            'per_page': 100
        }
        
        validated = validate_input(data, SearchQueryInput)
        
        assert validated.query == 'vintage sneakers'
        assert validated.max_pages == 5
    
    def test_search_query_input_sql_injection(self):
        """Test SQL injection attempt in search query."""
        data = {
            'query': "'; DROP TABLE items; --"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_input(data, SearchQueryInput)
        
        assert "Invalid characters" in str(exc_info.value)
    
    def test_search_query_input_xss_attempt(self):
        """Test XSS attempt in search query."""
        data = {
            'query': '<script>alert("xss")</script>'
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_input(data, SearchQueryInput)
        
        assert "Invalid characters" in str(exc_info.value)
    
    def test_payment_input_valid(self):
        """Test valid payment input."""
        from decimal import Decimal
        
        data = {
            'user_id': 12345,
            'amount': Decimal('100.50'),
            'currency': 'RUB',
            'description': 'Premium subscription'
        }
        
        validated = validate_input(data, PaymentInput)
        
        assert validated.user_id == 12345
        assert validated.amount == Decimal('100.50')
        assert validated.currency == 'RUB'
    
    def test_payment_input_invalid_amount(self):
        """Test invalid payment amount."""
        from decimal import Decimal
        
        data = {
            'user_id': 12345,
            'amount': Decimal('-10.00')  # Negative amount
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, PaymentInput)
    
    def test_webhook_input_valid(self):
        """Test valid webhook input."""
        data = {
            'signature': 'abcdef123456',
            'timestamp': int(time.time()),
            'payload': {'event': 'test', 'data': {}}
        }
        
        validated = validate_input(data, WebhookInput)
        
        assert validated.signature == 'abcdef123456'
        assert validated.payload['event'] == 'test'
    
    def test_webhook_input_old_timestamp(self):
        """Test webhook with old timestamp."""
        data = {
            'signature': 'abcdef123456',
            'timestamp': int(time.time()) - 400,  # 400 seconds ago
            'payload': {'event': 'test'}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_input(data, WebhookInput)
        
        assert "timestamp" in str(exc_info.value).lower()
    
    def test_sanitize_html_function(self):
        """Test HTML sanitization function."""
        dangerous_html = '<script>alert("xss")</script><img src=x onerror=alert(1)>'
        
        sanitized = sanitize_html(dangerous_html)
        
        assert '<script>' not in sanitized
        assert '<img' not in sanitized
        assert '&lt;script&gt;' in sanitized
        assert '&lt;img' in sanitized


class TestSecurityIntegration:
    """Test security integration scenarios."""
    
    def test_referral_token_security_chain(self):
        """Test complete referral token security chain."""
        token_manager = SecureTokenManager("test_secret")
        
        # Generate token
        original_user_id = 12345
        token = token_manager.generate_referral_token(original_user_id)
        
        # Validate token
        is_valid, user_id, error = token_manager.validate_referral_token(token)
        
        assert is_valid is True
        assert user_id == original_user_id
        assert error is None
        
        # Test token tampering
        tampered_token = token[:-10] + "0123456789"
        is_valid, user_id, error = token_manager.validate_referral_token(tampered_token)
        
        assert is_valid is False
        assert user_id is None
        assert error is not None
    
    def test_webhook_security_chain(self):
        """Test complete webhook security chain."""
        validator = WebhookSignatureValidator("webhook_secret")
        
        # Valid webhook
        payload = b'{"update_id": 123, "message": {"text": "hello"}}'
        signature = hmac.new(
            b"webhook_secret",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        assert validator.validate_telegram_webhook(payload, signature) is True
        
        # Invalid webhook (tampered payload)
        tampered_payload = b'{"update_id": 456, "message": {"text": "hello"}}'
        assert validator.validate_telegram_webhook(tampered_payload, signature) is False
    
    def test_input_validation_security_chain(self):
        """Test complete input validation security chain."""
        # Test SQL injection prevention
        dangerous_query = {
            'query': "test'; DROP TABLE users; --"
        }
        
        with pytest.raises(ValidationError):
            validate_input(dangerous_query, SearchQueryInput)
        
        # Test XSS prevention
        dangerous_user = {
            'user_id': 12345,
            'first_name': '<script>alert("xss")</script>'
        }
        
        sanitized = InputSanitizer.validate_telegram_user_input(dangerous_user)
        assert '<script>' not in sanitized['first_name']
        assert '&lt;script&gt;' in sanitized['first_name']
    
    @patch('src.security.session_manager.logger')
    def test_security_logging(self, mock_logger):
        """Test security event logging."""
        token_manager = SecureTokenManager("test_secret")
        
        # Generate token (should log)
        token = token_manager.generate_referral_token(12345)
        mock_logger.info.assert_called()
        
        # Validate token (should log)
        token_manager.validate_referral_token(token)
        assert mock_logger.info.call_count >= 2
        
        # Invalid token (should log warning)
        token_manager.validate_referral_token("invalid_token")
        mock_logger.warning.assert_called()