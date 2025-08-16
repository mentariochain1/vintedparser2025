"""Isolated tests for payment functionality without VintedService dependencies."""

import pytest
import sys
from unittest .mock import MagicMock ,patch
from datetime import datetime ,timedelta

def test_payment_service_pricing_isolated ():
    """Test payment service pricing calculations in isolation."""

    sys .modules ['src.bot.handlers']=MagicMock ()
    sys .modules ['src.bot.handlers.start']=MagicMock ()
    sys .modules ['src.bot.handlers.search']=MagicMock ()
    sys .modules ['src.bot.handlers.payment']=MagicMock ()
    sys .modules ['src.tasks.search_tasks']=MagicMock ()
    sys .modules ['src.bot.services.vinted_service']=MagicMock ()

    with patch ('src.config.settings')as mock_settings :
        mock_settings .yookassa_shop_id ="test_shop"
        mock_settings .yookassa_secret_key ="test_secret"

        from src .bot .services .payment_service import PaymentService

        service =PaymentService ()

        monthly =service .calculate_subscription_price (30 )
        assert monthly ['days']==30
        assert monthly ['discount']==0.0
        assert monthly ['final_price']==299.0
        assert monthly ['currency']=='RUB'

        quarterly =service .calculate_subscription_price (90 )
        assert quarterly ['days']==90
        assert quarterly ['discount']==0.10
        assert quarterly ['final_price']<quarterly ['base_price']

        yearly =service .calculate_subscription_price (365 )
        assert yearly ['days']==365
        assert yearly ['discount']==0.20
        assert yearly ['final_price']<yearly ['base_price']

        print ("✅ Payment service pricing tests passed!")

@pytest .mark .asyncio
async def test_payment_service_health_check_isolated ():
    """Test payment service health check in isolation."""

    sys .modules ['src.bot.handlers']=MagicMock ()
    sys .modules ['src.bot.handlers.start']=MagicMock ()
    sys .modules ['src.bot.handlers.search']=MagicMock ()
    sys .modules ['src.bot.handlers.payment']=MagicMock ()
    sys .modules ['src.tasks.search_tasks']=MagicMock ()
    sys .modules ['src.bot.services.vinted_service']=MagicMock ()

    with patch ('src.config.settings')as mock_settings :
        mock_settings .yookassa_shop_id ="test_shop"
        mock_settings .yookassa_secret_key ="test_secret"

        from src .bot .services .payment_service import PaymentService

        service =PaymentService ()
        health =await service .health_check ()
        assert health is True

        print ("✅ Payment service health check passed!")

def test_webhook_signature_verification_isolated ():
    """Test webhook signature verification in isolation."""

    sys .modules ['src.bot.handlers']=MagicMock ()
    sys .modules ['src.bot.handlers.start']=MagicMock ()
    sys .modules ['src.bot.handlers.search']=MagicMock ()
    sys .modules ['src.bot.handlers.payment']=MagicMock ()
    sys .modules ['src.tasks.search_tasks']=MagicMock ()
    sys .modules ['src.bot.services.vinted_service']=MagicMock ()

    with patch ('src.config.settings')as mock_settings :
        mock_settings .yookassa_shop_id ="test_shop"
        mock_settings .yookassa_secret_key ="test_secret_key"

        from src .bot .services .payment_service import PaymentService

        service =PaymentService ()

        payload =b'{"event": "payment.succeeded"}'
        import time
        timestamp =str (int (time .time ()))

        import hmac
        import hashlib
        message =payload +timestamp .encode ()
        valid_signature =hmac .new (
        service .secret_key .encode (),
        message ,
        hashlib .sha256
        ).hexdigest ()

        result =service .verify_webhook_signature (payload ,valid_signature ,timestamp )
        assert result is True

        result =service .verify_webhook_signature (payload ,"invalid",timestamp )
        assert result is False

        print ("✅ Webhook signature verification tests passed!")

def test_payment_handlers_exist ():
    """Test that payment handlers can be imported and have the right functions."""

    sys .modules ['src.bot.handlers']=MagicMock ()
    sys .modules ['src.bot.handlers.start']=MagicMock ()
    sys .modules ['src.bot.handlers.search']=MagicMock ()
    sys .modules ['src.tasks.search_tasks']=MagicMock ()
    sys .modules ['src.bot.services.vinted_service']=MagicMock ()

    with patch ('src.config.settings')as mock_settings ,patch ('src.bot.services.payment_service.PaymentService')as mock_ps ,patch ('src.bot.services.user_service.UserService')as mock_us ,patch ('src.db.base.get_db_session')as mock_session :

        mock_settings .yookassa_shop_id ="test_shop"
        mock_settings .yookassa_secret_key ="test_secret"

        import importlib .util
        spec =importlib .util .spec_from_file_location (
        "payment_handlers",
        "src/bot/handlers/payment.py"
        )
        payment_module =importlib .util .module_from_spec (spec )
        spec .loader .exec_module (payment_module )

        assert hasattr (payment_module ,'payment_command')
        assert hasattr (payment_module ,'subscription_status_command')
        assert hasattr (payment_module ,'handle_payment_callback')
        assert hasattr (payment_module ,'handle_payment_confirmation')
        assert hasattr (payment_module ,'handle_payment_status_check')
        assert hasattr (payment_module ,'router')

        print ("✅ Payment handlers structure tests passed!")

def test_main_app_webhook_endpoints ():
    """Test that main app has the required webhook endpoints."""
    with open ('src/main.py','r')as f :
        content =f .read ()

    assert '@app.post("/payment/webhook")'in content
    assert 'yookassa_webhook_handler'in content
    assert '@app.get("/payment/success")'in content
    assert 'payment_success_page'in content
    assert 'PaymentService'in content
    assert 'process_webhook'in content

    print ("✅ Main app webhook endpoints tests passed!")

if __name__ =="__main__":

    test_payment_service_pricing_isolated ()
    import asyncio
    asyncio .run (test_payment_service_health_check_isolated ())
    test_webhook_signature_verification_isolated ()
    test_payment_handlers_exist ()
    test_main_app_webhook_endpoints ()
    print ("🎉 All isolated payment tests passed!")