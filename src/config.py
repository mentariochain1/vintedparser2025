"""Configuration management using Pydantic settings."""

import secrets
from typing import Final, Optional
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


# Security Constants
DEFAULT_SECRET_KEY_LENGTH: Final[int] = 32
DEFAULT_TOKEN_TTL: Final[int] = 3600 * 24 * 14  # 14 days
DEFAULT_SESSION_TTL: Final[int] = 3600  # 1 hour

# Rate Limiting Constants
DEFAULT_RATE_LIMIT_REQUESTS: Final[int] = 60
DEFAULT_RATE_LIMIT_WINDOW: Final[int] = 60
VINTED_RATE_LIMIT_REQUESTS: Final[int] = 30
VINTED_RATE_LIMIT_WINDOW: Final[int] = 60

# Database Constants
DEFAULT_DB_POOL_SIZE: Final[int] = 10
DEFAULT_DB_MAX_OVERFLOW: Final[int] = 20
DEFAULT_DB_POOL_TIMEOUT: Final[int] = 30

# Application Constants
DEFAULT_TRIAL_DAYS: Final[int] = 7
DEFAULT_REFERRAL_BONUS_DAYS: Final[int] = 3
DEFAULT_MAX_CONCURRENT_REQUESTS: Final[int] = 10


class Settings(BaseSettings):
    """Application settings loaded from environment variables with security validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Core Application Settings
    environment: str = Field(
        default="development",
        description="Environment (development/production/staging)"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode (WARNING: Never enable in production)"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL)"
    )

    # Telegram Bot Configuration
    bot_token: str = Field(
        ...,
        description="Telegram Bot API token",
        min_length=45,
        max_length=50
    )
    webhook_domain: str = Field(
        ...,
        description="Domain for webhook URL (must include https:// in production)"
    )
    webhook_path: str = Field(
        default="/telegram",
        description="Webhook endpoint path"
    )
    webhook_secret: str = Field(
        ...,
        description="Webhook secret token for signature validation",
        min_length=32
    )

    # Database Configuration
    database_url: str = Field(
        ...,
        description="PostgreSQL database connection URL"
    )
    db_pool_size: int = Field(
        default=DEFAULT_DB_POOL_SIZE,
        description="Database connection pool size",
        ge=1,
        le=100
    )
    db_max_overflow: int = Field(
        default=DEFAULT_DB_MAX_OVERFLOW,
        description="Maximum overflow connections",
        ge=0,
        le=50
    )
    db_pool_timeout: int = Field(
        default=DEFAULT_DB_POOL_TIMEOUT,
        description="Database connection timeout in seconds",
        ge=5,
        le=300
    )

    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis connection URL"
    )
    redis_pool_size: int = Field(
        default=10,
        description="Redis connection pool size",
        ge=1,
        le=100
    )

    # Payment Processing (YooKassa)
    yookassa_shop_id: str = Field(
        ...,
        description="YooKassa shop ID"
    )
    yookassa_secret_key: str = Field(
        ...,
        description="YooKassa secret key",
        min_length=32
    )

    # Security Keys
    secret_key: str = Field(
        default_factory=lambda: secrets.token_hex(DEFAULT_SECRET_KEY_LENGTH),
        description="Application secret key for token signing",
        min_length=32
    )
    referral_secret: str = Field(
        default_factory=lambda: secrets.token_hex(DEFAULT_SECRET_KEY_LENGTH),
        description="Secret for signing referral links",
        min_length=32
    )

    # Business Logic Settings
    default_trial_days: int = Field(
        default=DEFAULT_TRIAL_DAYS,
        description="Default trial period in days",
        ge=1,
        le=365
    )
    referral_bonus_days: int = Field(
        default=DEFAULT_REFERRAL_BONUS_DAYS,
        description="Referral bonus days",
        ge=1,
        le=90
    )

    # Rate Limiting
    rate_limit_requests: int = Field(
        default=DEFAULT_RATE_LIMIT_REQUESTS,
        description="Default rate limit requests per window",
        ge=1,
        le=1000
    )
    rate_limit_window: int = Field(
        default=DEFAULT_RATE_LIMIT_WINDOW,
        description="Rate limit window in seconds",
        ge=1,
        le=3600
    )

    # External API Settings
    vinted_rate_limit: int = Field(
        default=VINTED_RATE_LIMIT_REQUESTS,
        description="Vinted API requests per minute",
        ge=1,
        le=60
    )
    max_concurrent_requests: int = Field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        description="Max concurrent HTTP requests",
        ge=1,
        le=50
    )

    # Security Settings
    disable_ssl_verification: bool = Field(
        default=False,
        description="Disable SSL verification for Vinted scraper (DANGER: Never enable in production)"
    )
    enable_security_headers: bool = Field(
        default=True,
        description="Enable security headers"
    )
    enable_cors: bool = Field(
        default=True,
        description="Enable CORS middleware"
    )

    # Monitoring
    enable_prometheus: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    enable_health_checks: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate Telegram bot token format."""
        if not v:
            raise ValueError("Bot token is required")

        # Telegram bot tokens have format: <bot_id>:<token>
        # Bot ID should be numeric, token should be alphanumeric with specific length
        if ":" not in v:
            raise ValueError("Bot token must contain ':' separator")

        bot_id, token = v.split(":", 1)

        # Bot ID should be numeric
        if not bot_id.isdigit() or len(bot_id) < 8:
            raise ValueError("Invalid bot ID format")

        # Token should be reasonably long and contain expected characters
        if len(token) < 30 or not any(c.isalnum() for c in token):
            raise ValueError("Invalid token format")

        return v

    @field_validator("webhook_domain")
    @classmethod
    def validate_webhook_domain(cls, v: str, info: ValidationInfo) -> str:
        """Validate webhook domain format."""
        if not v:
            raise ValueError("Webhook domain is required")

        # In production, must use HTTPS
        is_production = info.data.get("environment", "").lower() == "production"
        if is_production and not v.startswith("https://"):
            raise ValueError("Production webhook domain must use HTTPS")

        return v.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format and security."""
        if not v:
            raise ValueError("Database URL is required")

        # Ensure no default credentials are used
        forbidden_patterns = ["postgres:postgres@", "user:password@", "root:root@"]
        for pattern in forbidden_patterns:
            if pattern in v:
                raise ValueError(f"Database URL contains insecure default credentials: {pattern}")

        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_environments = {"development", "staging", "production"}
        if v.lower() not in valid_environments:
            raise ValueError(f"Environment must be one of: {', '.join(valid_environments)}")
        return v.lower()

    @field_validator("disable_ssl_verification")
    @classmethod
    def validate_ssl_setting(cls, v: bool, info: ValidationInfo) -> bool:
        """Warn about disabling SSL verification."""
        is_production = info.data.get("environment", "").lower() == "production"
        if v and is_production:
            raise ValueError("SSL verification cannot be disabled in production")
        return v

    @property
    def webhook_url(self) -> str:
        """Full webhook URL."""
        return f"{self.webhook_domain}{self.webhook_path}"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging."""
        return self.environment == "staging"

    def get_rate_limit_config(self) -> dict:
        """Get rate limiting configuration."""
        return {
            "requests": self.rate_limit_requests,
            "window_seconds": self.rate_limit_window,
        }

    def get_database_config(self) -> dict:
        """Get database configuration."""
        return {
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
        }


# Global settings instance
settings = Settings()