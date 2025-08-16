"""Configuration management using Pydantic settings."""

from pydantic import Field
from pydantic_settings import BaseSettings ,SettingsConfigDict

class Settings (BaseSettings ):
    """Application settings loaded from environment variables."""

    model_config =SettingsConfigDict (
    env_file =".env",
    env_file_encoding ="utf-8",
    case_sensitive =False ,
    extra ="ignore"
    )

    bot_token :str =Field (...,description ="Telegram Bot API token")
    webhook_domain :str =Field (...,description ="Domain for webhook URL")
    webhook_path :str =Field (default ="/telegram",description ="Webhook endpoint path")
    webhook_secret :str =Field (...,description ="Webhook secret token")

    # Deprecated: Supabase settings (kept for backward compatibility)
    supabase_url :str =Field (default ="",description ="Deprecated: Supabase project URL")
    supabase_service_key :str =Field (default ="",description ="Deprecated: Supabase service role key")
    supabase_anon_key :str =Field (default ="",description ="Deprecated: Supabase anonymous key")
    db_schema :str =Field (default ="public",description ="Database schema")
    database_url :str =Field (default ="postgresql+asyncpg://postgres:postgres@localhost:5432/vinted_bot",description ="PostgreSQL database connection URL")

    redis_url :str =Field (default ="redis://localhost:6379/1",description ="Redis connection URL")

    yookassa_shop_id :str =Field (...,description ="YooKassa shop ID")
    yookassa_secret_key :str =Field (...,description ="YooKassa secret key")

    default_trial_days :int =Field (default =7 ,description ="Default trial period in days")
    referral_bonus_days :int =Field (default =3 ,description ="Referral bonus days")
    referral_secret :str =Field (...,description ="Secret for signing referral links")
    secret_key :str =Field (...,description ="Application secret key for token signing")

    vinted_rate_limit :int =Field (default =30 ,description ="Vinted API requests per minute")
    max_concurrent_requests :int =Field (default =10 ,description ="Max concurrent HTTP requests")

    environment :str =Field (default ="development",description ="Environment (development/production)")
    debug :bool =Field (default =False ,description ="Enable debug mode")

    log_level :str =Field (default ="INFO",description ="Logging level")

    @property
    def webhook_url (self )->str :
        """Full webhook URL."""
        return f"{self .webhook_domain .rstrip ('/')}{self .webhook_path }"

    @property
    def is_production (self )->bool :
        """Check if running in production."""
        return self .environment .lower ()=="production"

settings =Settings ()