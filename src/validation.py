"""
Input validation models using Pydantic.

This module defines validation models for all user inputs and API requests
to prevent injection attacks and ensure data integrity.
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal

from exceptions import ValidationError


class TelegramUserInput(BaseModel):
    """Validation for Telegram user input."""
    
    user_id: int = Field(..., gt=0, description="Telegram user ID")
    username: Optional[str] = Field(None, max_length=32, description="Telegram username")
    first_name: Optional[str] = Field(None, max_length=64, description="User first name")
    last_name: Optional[str] = Field(None, max_length=64, description="User last name")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate Telegram username format."""
        if v is not None:
            # Must start with letter, then letters/numbers/underscore, 5-32 chars
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', v):
                raise ValidationError("Invalid username format")
        return v
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v):
        """Validate user names for XSS and injection attempts."""
        if v is not None:
            # Remove potential XSS characters
            dangerous_chars = ['<', '>', '"', "'", '&', 'script', 'javascript:', 'data:']
            v_lower = v.lower()
            for char in dangerous_chars:
                if char in v_lower:
                    raise ValidationError(f"Invalid characters in name: {char}")
            
            # Limit length and ensure printable characters
            if len(v) > 64:
                raise ValidationError("Name too long")
            
            if not v.isprintable():
                raise ValidationError("Name contains non-printable characters")
        
        return v


class SearchQueryInput(BaseModel):
    """Validation for search query input."""
    
    query: str = Field(..., min_length=1, max_length=255, description="Search query")
    max_pages: Optional[int] = Field(5, ge=1, le=10, description="Maximum pages to search")
    per_page: Optional[int] = Field(100, ge=10, le=200, description="Items per page")
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Validate search query for safety."""
        if not v or not v.strip():
            raise ValidationError("Search query cannot be empty")
        
        # Remove leading/trailing whitespace
        v = v.strip()
        
        # Check for SQL injection patterns
        sql_patterns = [
            r'union\s+select', r'drop\s+table', r'delete\s+from',
            r'insert\s+into', r'update\s+.*\s+set', r'exec\s*\('
        ]
        
        # Check for XSS patterns
        xss_patterns = [
            r'<script', r'</script>', r'javascript\s*:', r'vbscript\s*:',
            r'on\w+\s*=', r'<iframe', r'<object', r'<embed'
        ]
        
        v_lower = v.lower()
        for pattern in sql_patterns + xss_patterns:
            if re.search(pattern, v_lower):
                raise ValidationError("Invalid characters in search query")
        
        # Limit special characters
        if len(re.findall(r'[^\w\s\-\.]', v)) > 10:
            raise ValidationError("Too many special characters in query")
        
        return v


class PaymentInput(BaseModel):
    """Validation for payment input."""
    
    user_id: int = Field(..., gt=0, description="User ID")
    amount: Decimal = Field(..., gt=0, le=100000, description="Payment amount")
    currency: str = Field("RUB", pattern=r'^[A-Z]{3}$', description="Currency code")
    description: Optional[str] = Field(None, max_length=128, description="Payment description")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Validate payment amount."""
        if v <= 0:
            raise ValidationError("Payment amount must be positive")
        
        if v > 100000:
            raise ValidationError("Payment amount too large")
        
        # Check decimal places (max 2)
        if v.as_tuple().exponent < -2:
            raise ValidationError("Too many decimal places in amount")
        
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Validate payment description."""
        if v is not None:
            # Check for XSS patterns, but allow normal text
            dangerous_patterns = [
                r'<script', r'</script>', r'javascript\s*:', r'vbscript\s*:',
                r'on\w+\s*=', r'<iframe', r'<object', r'<embed'
            ]
            
            v_lower = v.lower()
            for pattern in dangerous_patterns:
                if re.search(pattern, v_lower):
                    raise ValidationError(f"Invalid content in description")
        
        return v


class WebhookInput(BaseModel):
    """Validation for webhook input."""
    
    signature: str = Field(..., min_length=1, max_length=256, description="Webhook signature")
    timestamp: Optional[int] = Field(None, description="Webhook timestamp")
    payload: Dict[str, Any] = Field(..., description="Webhook payload")
    
    @field_validator('signature')
    @classmethod
    def validate_signature(cls, v):
        """Validate webhook signature format."""
        # Should be hex string
        if not re.match(r'^[a-fA-F0-9]+$', v):
            raise ValidationError("Invalid signature format")
        
        return v
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        """Validate webhook timestamp."""
        if v is not None:
            current_time = int(datetime.utcnow().timestamp())
            # Allow 5 minutes skew
            if abs(current_time - v) > 300:
                raise ValidationError("Webhook timestamp too old or in future")
        
        return v
    
    @field_validator('payload')
    @classmethod
    def validate_payload(cls, v):
        """Validate webhook payload structure."""
        if not isinstance(v, dict):
            raise ValidationError("Payload must be a dictionary")
        
        # Limit payload size (prevent DoS)
        if len(str(v)) > 10000:
            raise ValidationError("Payload too large")
        
        return v


class ReferralTokenInput(BaseModel):
    """Validation for referral token input."""
    
    token: str = Field(..., min_length=1, max_length=128, description="Referral token")
    
    @field_validator('token')
    @classmethod
    def validate_token(cls, v):
        """Validate referral token format."""
        # Should be base64url encoded
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValidationError("Invalid token format")
        
        return v


class NotificationInput(BaseModel):
    """Validation for notification input."""
    
    user_ids: List[int] = Field(..., min_length=1, max_length=1000, description="User IDs")
    message: str = Field(..., min_length=1, max_length=4096, description="Notification message")
    parse_mode: Optional[str] = Field(None, pattern=r'^(HTML|Markdown|MarkdownV2)$')
    
    @field_validator('user_ids')
    @classmethod
    def validate_user_ids(cls, v):
        """Validate user ID list."""
        if not v:
            raise ValidationError("User ID list cannot be empty")
        
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValidationError("Duplicate user IDs found")
        
        # Validate each ID
        for user_id in v:
            if user_id <= 0:
                raise ValidationError(f"Invalid user ID: {user_id}")
        
        return v
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        """Validate notification message."""
        if not v.strip():
            raise ValidationError("Message cannot be empty")
        
        # Check for potential XSS in HTML mode
        dangerous_patterns = [
            r'<script', r'javascript:', r'data:', r'vbscript:',
            r'on\w+\s*=', r'<iframe', r'<object', r'<embed'
        ]
        
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, v_lower):
                raise ValidationError("Potentially dangerous content in message")
        
        return v


class DatabaseQueryInput(BaseModel):
    """Validation for database query parameters."""
    
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Query limit")
    offset: Optional[int] = Field(0, ge=0, description="Query offset")
    order_by: Optional[str] = Field(None, max_length=50, description="Order by field")
    order_direction: Optional[str] = Field("ASC", pattern=r'^(ASC|DESC)$')
    
    @field_validator('order_by')
    @classmethod
    def validate_order_by(cls, v):
        """Validate order by field name."""
        if v is not None:
            # Only allow alphanumeric and underscore
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
                raise ValidationError("Invalid order by field name")
            
            # Prevent SQL injection
            dangerous_words = ['union', 'select', 'drop', 'delete', 'insert', 'update']
            if v.lower() in dangerous_words:
                raise ValidationError("Invalid order by field name")
        
        return v


class ConfigurationInput(BaseModel):
    """Validation for configuration input."""
    
    key: str = Field(..., min_length=1, max_length=100, description="Configuration key")
    value: str = Field(..., max_length=1000, description="Configuration value")
    
    @field_validator('key')
    @classmethod
    def validate_key(cls, v):
        """Validate configuration key."""
        # Only allow alphanumeric, underscore, and dot
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', v):
            raise ValidationError("Invalid configuration key format")
        
        return v
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v):
        """Validate configuration value."""
        # Check for potential code injection
        dangerous_patterns = [
            r'<script', r'javascript:', r'eval\s*\(',
            r'exec\s*\(', r'system\s*\(', r'shell_exec'
        ]
        
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, v_lower):
                raise ValidationError("Potentially dangerous content in value")
        
        return v


def validate_input(data: Dict[str, Any], model_class: BaseModel) -> BaseModel:
    """
    Validate input data against a Pydantic model.
    
    Args:
        data: Input data to validate
        model_class: Pydantic model class to validate against
        
    Returns:
        Validated model instance
        
    Raises:
        ValidationError: If validation fails
    """
    try:
        return model_class(**data)
    except Exception as e:
        raise ValidationError(f"Input validation failed: {str(e)}")


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return text
    
    # Replace dangerous characters - order matters, & must be first
    replacements = [
        ('&', '&amp;'),
        ('<', '&lt;'),
        ('>', '&gt;'),
        ('"', '&quot;'),
        ("'", '&#x27;')
    ]
    
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    
    return text


def validate_telegram_update(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate Telegram update data.
    
    Args:
        update_data: Raw update data from Telegram
        
    Returns:
        Validated update data
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(update_data, dict):
        raise ValidationError("Update data must be a dictionary")
    
    # Check required fields
    if 'update_id' not in update_data:
        raise ValidationError("Missing update_id")
    
    update_id = update_data.get('update_id')
    if not isinstance(update_id, int) or update_id < 0:
        raise ValidationError("Invalid update_id")
    
    # Validate message if present
    if 'message' in update_data:
        message = update_data['message']
        if not isinstance(message, dict):
            raise ValidationError("Invalid message format")
        
        # Validate user data
        if 'from' in message:
            user_data = message['from']
            if 'id' not in user_data or not isinstance(user_data['id'], int):
                raise ValidationError("Invalid user ID in message")
    
    return update_data