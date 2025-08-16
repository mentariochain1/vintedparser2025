"""Tests for input validation system."""

import pytest
from decimal import Decimal
from unittest.mock import patch

from src.validation import (
    TelegramUserInput, SearchQueryInput, PaymentInput,
    WebhookInput, ReferralTokenInput, NotificationInput,
    DatabaseQueryInput, ConfigurationInput, validate_input,
    sanitize_html, validate_telegram_update
)
from src.exceptions import ValidationError


class TestTelegramUserInput:
    """Test Telegram user input validation."""
    
    def test_valid_user_input(self):
        """Test valid user input."""
        data = {
            'user_id': 12345,
            'username': 'testuser',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        
        validated = validate_input(data, TelegramUserInput)
        
        assert validated.user_id == 12345
        assert validated.username == 'testuser'
        assert validated.first_name == 'John'
        assert validated.last_name == 'Doe'
    
    def test_invalid_user_id(self):
        """Test invalid user ID."""
        data = {'user_id': -1}
        
        with pytest.raises(ValidationError):
            validate_input(data, TelegramUserInput)
    
    def test_invalid_username_format(self):
        """Test invalid username format."""
        invalid_usernames = [
            'test@user',  # Invalid character
            'ab',         # Too short
            'a' * 33,     # Too long
            '123test',    # Can't start with number
        ]
        
        for username in invalid_usernames:
            data = {'user_id': 12345, 'username': username}
            with pytest.raises(ValidationError):
                validate_input(data, TelegramUserInput)
    
    def test_xss_in_names(self):
        """Test XSS prevention in names."""
        dangerous_names = [
            '<script>alert("xss")</script>',
            'javascript:alert(1)',
            '<img src=x onerror=alert(1)>',
            'test&lt;script&gt;'
        ]
        
        for name in dangerous_names:
            data = {'user_id': 12345, 'first_name': name}
            with pytest.raises(ValidationError):
                validate_input(data, TelegramUserInput)


class TestSearchQueryInput:
    """Test search query input validation."""
    
    def test_valid_search_query(self):
        """Test valid search query."""
        data = {
            'query': 'vintage sneakers',
            'max_pages': 5,
            'per_page': 100
        }
        
        validated = validate_input(data, SearchQueryInput)
        
        assert validated.query == 'vintage sneakers'
        assert validated.max_pages == 5
        assert validated.per_page == 100
    
    def test_empty_query(self):
        """Test empty search query."""
        data = {'query': ''}
        
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention."""
        sql_injections = [
            "'; DROP TABLE items; --",
            "UNION SELECT * FROM users",
            "DELETE FROM items WHERE 1=1",
            "INSERT INTO items VALUES (1, 'test')",
            "UPDATE items SET price=0"
        ]
        
        for injection in sql_injections:
            data = {'query': injection}
            with pytest.raises(ValidationError):
                validate_input(data, SearchQueryInput)
    
    def test_xss_prevention(self):
        """Test XSS prevention in search query."""
        xss_attempts = [
            '<script>alert("xss")</script>',
            'javascript:alert(1)',
            'vbscript:msgbox("xss")'
        ]
        
        for xss in xss_attempts:
            data = {'query': xss}
            with pytest.raises(ValidationError):
                validate_input(data, SearchQueryInput)
    
    def test_too_many_special_characters(self):
        """Test query with too many special characters."""
        data = {'query': '!@#$%^&*()!@#$%^&*()!@#$%^&*()'}
        
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)
    
    def test_query_length_limits(self):
        """Test query length limits."""
        # Too long
        data = {'query': 'a' * 256}
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)
    
    def test_page_limits(self):
        """Test page parameter limits."""
        # Invalid max_pages
        data = {'query': 'test', 'max_pages': 0}
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)
        
        data = {'query': 'test', 'max_pages': 11}
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)
        
        # Invalid per_page
        data = {'query': 'test', 'per_page': 5}
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)
        
        data = {'query': 'test', 'per_page': 201}
        with pytest.raises(ValidationError):
            validate_input(data, SearchQueryInput)


class TestPaymentInput:
    """Test payment input validation."""
    
    def test_valid_payment_input(self):
        """Test valid payment input."""
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
        assert validated.description == 'Premium subscription'
    
    def test_invalid_amount(self):
        """Test invalid payment amounts."""
        invalid_amounts = [
            Decimal('0'),      # Zero
            Decimal('-10.50'), # Negative
            Decimal('100001'), # Too large
            Decimal('10.123')  # Too many decimals
        ]
        
        for amount in invalid_amounts:
            data = {'user_id': 12345, 'amount': amount}
            with pytest.raises(ValidationError):
                validate_input(data, PaymentInput)
    
    def test_invalid_currency(self):
        """Test invalid currency codes."""
        invalid_currencies = [
            'USD1',  # Too long
            'US',    # Too short
            'usd',   # Lowercase
            '123'    # Numbers
        ]
        
        for currency in invalid_currencies:
            data = {
                'user_id': 12345,
                'amount': Decimal('100.00'),
                'currency': currency
            }
            with pytest.raises(ValidationError):
                validate_input(data, PaymentInput)
    
    def test_xss_in_description(self):
        """Test XSS prevention in payment description."""
        dangerous_descriptions = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert(1)>',
            'javascript:alert(1)'
        ]
        
        for desc in dangerous_descriptions:
            data = {
                'user_id': 12345,
                'amount': Decimal('100.00'),
                'description': desc
            }
            with pytest.raises(ValidationError):
                validate_input(data, PaymentInput)


class TestWebhookInput:
    """Test webhook input validation."""
    
    def test_valid_webhook_input(self):
        """Test valid webhook input."""
        import time
        
        data = {
            'signature': 'abcdef123456789',
            'timestamp': int(time.time()),
            'payload': {'event': 'test', 'data': {}}
        }
        
        validated = validate_input(data, WebhookInput)
        
        assert validated.signature == 'abcdef123456789'
        assert validated.payload['event'] == 'test'
    
    def test_invalid_signature_format(self):
        """Test invalid signature format."""
        import time
        
        invalid_signatures = [
            'invalid_chars!@#',  # Invalid characters
            '',                  # Empty
            'g' * 257           # Too long
        ]
        
        for signature in invalid_signatures:
            data = {
                'signature': signature,
                'timestamp': int(time.time()),
                'payload': {}
            }
            with pytest.raises(ValidationError):
                validate_input(data, WebhookInput)
    
    def test_old_timestamp(self):
        """Test webhook with old timestamp."""
        import time
        
        data = {
            'signature': 'abcdef123456',
            'timestamp': int(time.time()) - 400,  # 400 seconds ago
            'payload': {}
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, WebhookInput)
    
    def test_future_timestamp(self):
        """Test webhook with future timestamp."""
        import time
        
        data = {
            'signature': 'abcdef123456',
            'timestamp': int(time.time()) + 400,  # 400 seconds in future
            'payload': {}
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, WebhookInput)
    
    def test_large_payload(self):
        """Test webhook with large payload."""
        import time
        
        # Create large payload
        large_payload = {'data': 'x' * 10001}
        
        data = {
            'signature': 'abcdef123456',
            'timestamp': int(time.time()),
            'payload': large_payload
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, WebhookInput)


class TestReferralTokenInput:
    """Test referral token input validation."""
    
    def test_valid_referral_token(self):
        """Test valid referral token."""
        data = {'token': 'eyJhbGciOiJIUzI1NiJ9'}
        
        validated = validate_input(data, ReferralTokenInput)
        
        assert validated.token == 'eyJhbGciOiJIUzI1NiJ9'
    
    def test_invalid_token_format(self):
        """Test invalid token format."""
        invalid_tokens = [
            'invalid@token!',  # Invalid characters
            '',               # Empty
            'a' * 129        # Too long
        ]
        
        for token in invalid_tokens:
            data = {'token': token}
            with pytest.raises(ValidationError):
                validate_input(data, ReferralTokenInput)


class TestNotificationInput:
    """Test notification input validation."""
    
    def test_valid_notification_input(self):
        """Test valid notification input."""
        data = {
            'user_ids': [12345, 67890],
            'message': 'Hello, this is a test notification!',
            'parse_mode': 'HTML'
        }
        
        validated = validate_input(data, NotificationInput)
        
        assert validated.user_ids == [12345, 67890]
        assert validated.message == 'Hello, this is a test notification!'
        assert validated.parse_mode == 'HTML'
    
    def test_empty_user_ids(self):
        """Test empty user IDs list."""
        data = {
            'user_ids': [],
            'message': 'Test message'
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, NotificationInput)
    
    def test_too_many_user_ids(self):
        """Test too many user IDs."""
        data = {
            'user_ids': list(range(1001)),  # 1001 user IDs
            'message': 'Test message'
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, NotificationInput)
    
    def test_duplicate_user_ids(self):
        """Test duplicate user IDs."""
        data = {
            'user_ids': [12345, 67890, 12345],  # Duplicate
            'message': 'Test message'
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, NotificationInput)
    
    def test_invalid_user_ids(self):
        """Test invalid user IDs."""
        data = {
            'user_ids': [12345, -1, 67890],  # Negative ID
            'message': 'Test message'
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, NotificationInput)
    
    def test_empty_message(self):
        """Test empty message."""
        data = {
            'user_ids': [12345],
            'message': '   '  # Only whitespace
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, NotificationInput)
    
    def test_dangerous_message_content(self):
        """Test dangerous content in message."""
        dangerous_messages = [
            '<script>alert("xss")</script>',
            'javascript:alert(1)',
            '<iframe src="evil.com"></iframe>',
            '<object data="evil.swf"></object>',
            '<embed src="evil.swf">'
        ]
        
        for message in dangerous_messages:
            data = {
                'user_ids': [12345],
                'message': message
            }
            with pytest.raises(ValidationError):
                validate_input(data, NotificationInput)
    
    def test_invalid_parse_mode(self):
        """Test invalid parse mode."""
        data = {
            'user_ids': [12345],
            'message': 'Test message',
            'parse_mode': 'INVALID'
        }
        
        with pytest.raises(ValidationError):
            validate_input(data, NotificationInput)


class TestDatabaseQueryInput:
    """Test database query input validation."""
    
    def test_valid_database_query(self):
        """Test valid database query parameters."""
        data = {
            'limit': 50,
            'offset': 10,
            'order_by': 'created_at',
            'order_direction': 'DESC'
        }
        
        validated = validate_input(data, DatabaseQueryInput)
        
        assert validated.limit == 50
        assert validated.offset == 10
        assert validated.order_by == 'created_at'
        assert validated.order_direction == 'DESC'
    
    def test_invalid_limit(self):
        """Test invalid limit values."""
        invalid_limits = [0, -1, 1001]
        
        for limit in invalid_limits:
            data = {'limit': limit}
            with pytest.raises(ValidationError):
                validate_input(data, DatabaseQueryInput)
    
    def test_invalid_offset(self):
        """Test invalid offset values."""
        data = {'offset': -1}
        
        with pytest.raises(ValidationError):
            validate_input(data, DatabaseQueryInput)
    
    def test_sql_injection_in_order_by(self):
        """Test SQL injection prevention in order_by."""
        dangerous_order_by = [
            'name; DROP TABLE users',
            'UNION SELECT * FROM passwords',
            'name OR 1=1',
            'delete'
        ]
        
        for order_by in dangerous_order_by:
            data = {'order_by': order_by}
            with pytest.raises(ValidationError):
                validate_input(data, DatabaseQueryInput)
    
    def test_invalid_order_direction(self):
        """Test invalid order direction."""
        data = {'order_direction': 'INVALID'}
        
        with pytest.raises(ValidationError):
            validate_input(data, DatabaseQueryInput)


class TestConfigurationInput:
    """Test configuration input validation."""
    
    def test_valid_configuration(self):
        """Test valid configuration input."""
        data = {
            'key': 'app.max_users',
            'value': '1000'
        }
        
        validated = validate_input(data, ConfigurationInput)
        
        assert validated.key == 'app.max_users'
        assert validated.value == '1000'
    
    def test_invalid_key_format(self):
        """Test invalid configuration key format."""
        invalid_keys = [
            '123invalid',     # Can't start with number
            'key-with-dash',  # Invalid character
            'key with space', # Space not allowed
            ''               # Empty
        ]
        
        for key in invalid_keys:
            data = {'key': key, 'value': 'test'}
            with pytest.raises(ValidationError):
                validate_input(data, ConfigurationInput)
    
    def test_dangerous_value_content(self):
        """Test dangerous content in configuration value."""
        dangerous_values = [
            '<script>alert("xss")</script>',
            'javascript:alert(1)',
            'eval("malicious_code")',
            'exec("rm -rf /")',
            'system("malicious_command")'
        ]
        
        for value in dangerous_values:
            data = {'key': 'test.key', 'value': value}
            with pytest.raises(ValidationError):
                validate_input(data, ConfigurationInput)


class TestUtilityFunctions:
    """Test utility validation functions."""
    
    def test_sanitize_html(self):
        """Test HTML sanitization."""
        test_cases = [
            ('<script>alert("xss")</script>', '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'),
            ('<img src=x onerror=alert(1)>', '&lt;img src=x onerror=alert(1)&gt;'),
            ('Normal text', 'Normal text'),
            ('Text with & ampersand', 'Text with &amp; ampersand'),
            ('"Quoted text"', '&quot;Quoted text&quot;'),
            ("'Single quoted'", '&#x27;Single quoted&#x27;')
        ]
        
        for input_text, expected in test_cases:
            result = sanitize_html(input_text)
            assert result == expected
    
    def test_sanitize_html_empty_input(self):
        """Test HTML sanitization with empty input."""
        assert sanitize_html('') == ''
        assert sanitize_html(None) is None
    
    def test_validate_telegram_update_valid(self):
        """Test valid Telegram update validation."""
        update_data = {
            'update_id': 123456,
            'message': {
                'message_id': 1,
                'from': {'id': 12345, 'first_name': 'Test'},
                'text': 'Hello'
            }
        }
        
        validated = validate_telegram_update(update_data)
        
        assert validated['update_id'] == 123456
        assert validated['message']['from']['id'] == 12345
    
    def test_validate_telegram_update_invalid(self):
        """Test invalid Telegram update validation."""
        # Missing update_id
        with pytest.raises(ValidationError):
            validate_telegram_update({})
        
        # Invalid update_id
        with pytest.raises(ValidationError):
            validate_telegram_update({'update_id': -1})
        
        # Invalid message format
        with pytest.raises(ValidationError):
            validate_telegram_update({
                'update_id': 123,
                'message': 'invalid'  # Should be dict
            })
        
        # Invalid user ID in message
        with pytest.raises(ValidationError):
            validate_telegram_update({
                'update_id': 123,
                'message': {
                    'from': {'id': 'invalid'}  # Should be int
                }
            })
    
    def test_validate_input_function(self):
        """Test generic validate_input function."""
        # Valid input
        data = {'user_id': 12345, 'username': 'testuser'}
        validated = validate_input(data, TelegramUserInput)
        assert validated.user_id == 12345
        
        # Invalid input
        data = {'user_id': -1}
        with pytest.raises(ValidationError):
            validate_input(data, TelegramUserInput)


class TestValidationIntegration:
    """Test validation integration scenarios."""
    
    def test_complete_user_registration_validation(self):
        """Test complete user registration validation chain."""
        # Valid registration
        user_data = {
            'user_id': 12345,
            'username': 'newuser',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        
        validated = validate_input(user_data, TelegramUserInput)
        assert validated.user_id == 12345
        
        # Invalid registration with XSS attempt
        user_data['first_name'] = '<script>alert("xss")</script>'
        
        with pytest.raises(ValidationError):
            validate_input(user_data, TelegramUserInput)
    
    def test_complete_search_validation_chain(self):
        """Test complete search validation chain."""
        # Valid search
        search_data = {
            'query': 'vintage sneakers nike',
            'max_pages': 3,
            'per_page': 50
        }
        
        validated = validate_input(search_data, SearchQueryInput)
        assert validated.query == 'vintage sneakers nike'
        
        # Invalid search with SQL injection
        search_data['query'] = "'; DROP TABLE items; --"
        
        with pytest.raises(ValidationError):
            validate_input(search_data, SearchQueryInput)
    
    def test_complete_payment_validation_chain(self):
        """Test complete payment validation chain."""
        # Valid payment
        payment_data = {
            'user_id': 12345,
            'amount': Decimal('99.99'),
            'currency': 'RUB',
            'description': 'Premium subscription'
        }
        
        validated = validate_input(payment_data, PaymentInput)
        assert validated.amount == Decimal('99.99')
        
        # Invalid payment with XSS in description
        payment_data['description'] = '<script>steal_payment_info()</script>'
        
        with pytest.raises(ValidationError):
            validate_input(payment_data, PaymentInput)