"""Test configuration module."""

import pytest
from pydantic import ValidationError

from src .config import Settings

def test_settings_validation ():
    """Test that settings validation works correctly."""

    settings =Settings (
    bot_token ="test_token",
    webhook_domain ="https://example.com",
    webhook_secret ="test_secret",
    supabase_url ="https://test.supabase.co",
    supabase_service_key ="test_service_key",
    supabase_anon_key ="test_anon_key",
    yookassa_shop_id ="123456",
    yookassa_secret_key ="test_secret_key",
    referral_secret ="test_referral_secret",
    )

    assert settings .bot_token =="test_token"
    assert settings .webhook_url =="https://example.com/telegram"
    assert settings .default_trial_days ==7
    assert settings .referral_bonus_days ==3

def test_webhook_url_property ():
    """Test webhook URL property construction."""
    settings =Settings (
    bot_token ="test_token",
    webhook_domain ="https://example.com/",
    webhook_path ="/custom",
    webhook_secret ="test_secret",
    supabase_url ="https://test.supabase.co",
    supabase_service_key ="test_service_key",
    supabase_anon_key ="test_anon_key",
    yookassa_shop_id ="123456",
    yookassa_secret_key ="test_secret_key",
    referral_secret ="test_referral_secret",
    )

    assert settings .webhook_url =="https://example.com/custom"

def test_is_production_property ():
    """Test production environment detection."""
    settings =Settings (
    bot_token ="test_token",
    webhook_domain ="https://example.com",
    webhook_secret ="test_secret",
    supabase_url ="https://test.supabase.co",
    supabase_service_key ="test_service_key",
    supabase_anon_key ="test_anon_key",
    yookassa_shop_id ="123456",
    yookassa_secret_key ="test_secret_key",
    referral_secret ="test_referral_secret",
    environment ="production",
    )

    assert settings .is_production is True

    settings .environment ="development"
    assert settings .is_production is False

def test_missing_required_fields ():
    """Test that missing required fields raise validation errors."""
    with pytest .raises (ValidationError ):
        Settings ()