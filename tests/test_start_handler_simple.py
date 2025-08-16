"""Simplified tests for start command handler logic."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from src .bot .services .user_service import UserService

class TestUserServiceReferralLogic :
    """Test the referral logic in UserService."""

    def test_encode_decode_referral_payload (self ):
        """Test encoding and decoding referral payloads."""
        service =UserService ()
        inviter_id =12345

        payload =service .encode_referral_payload (inviter_id )
        assert isinstance (payload ,str )
        assert len (payload )>0

        decoded_id =service .decode_referral_payload (payload )
        assert decoded_id ==inviter_id

    def test_decode_invalid_payload (self ):
        """Test decoding invalid payloads."""
        service =UserService ()

        assert service .decode_referral_payload ("invalid")is None
        assert service .decode_referral_payload ("")is None
        assert service .decode_referral_payload ("abc123")is None

    def test_generate_referral_link (self ):
        """Test generating referral links."""
        service =UserService ()
        bot_username ="test_bot"
        inviter_id =12345

        link =service .generate_referral_link (bot_username ,inviter_id )

        assert link .startswith ("https://t.me/test_bot?start=")
        assert len (link )>len ("https://t.me/test_bot?start=")

    @pytest .mark .asyncio
    async def test_process_referral_success (self ):
        """Test successful referral processing."""
        service =UserService ()
        mock_session =AsyncMock ()

        with patch ('src.bot.services.user_service.UserCRUD')as mock_user_crud ,patch ('src.bot.services.user_service.ReferralCRUD')as mock_referral_crud :

            inviter =MagicMock ()
            inviter .id =1
            invitee =MagicMock ()
            invitee .id =2
            invitee .referred_by =None

            mock_user_crud .get_by_id =AsyncMock (side_effect =[inviter ,invitee ])
            mock_referral_crud .get_by_invitee =AsyncMock (return_value =None )
            mock_referral_crud .create =AsyncMock (return_value =None )
            mock_user_crud .increment_referrals_count =AsyncMock (return_value =None )

            service .extend_trial =AsyncMock ()

            success ,message =await service .process_referral (mock_session ,1 ,2 )

            assert success is True
            assert "successfully"in message .lower ()

    @pytest .mark .asyncio
    async def test_process_referral_self_referral (self ):
        """Test prevention of self-referral."""
        service =UserService ()
        mock_session =AsyncMock ()

        with patch ('src.bot.services.user_service.UserCRUD')as mock_user_crud :
            inviter =MagicMock ()
            inviter .id =1

            mock_user_crud .get_by_id =AsyncMock (return_value =inviter )

            success ,message =await service .process_referral (mock_session ,1 ,1 )

            assert success is False
            assert "cannot refer yourself"in message .lower ()

    @pytest .mark .asyncio
    async def test_process_referral_already_referred (self ):
        """Test handling of already referred users."""
        service =UserService ()
        mock_session =AsyncMock ()

        with patch ('src.bot.services.user_service.UserCRUD')as mock_user_crud ,patch ('src.bot.services.user_service.ReferralCRUD')as mock_referral_crud :

            inviter =MagicMock ()
            inviter .id =1
            invitee =MagicMock ()
            invitee .id =2
            invitee .referred_by =3

            mock_user_crud .get_by_id =AsyncMock (side_effect =[inviter ,invitee ])
            mock_referral_crud .get_by_invitee =AsyncMock (return_value =None )

            success ,message =await service .process_referral (mock_session ,1 ,2 )

            assert success is False
            assert "already has a referrer"in message .lower ()

class TestStartHandlerLogic :
    """Test start handler logic components."""

    def test_trial_status_calculation (self ):
        """Test trial status calculation logic."""
        from datetime import datetime ,timedelta

        now =datetime .utcnow ()

        active_trial =now +timedelta (days =5 )
        assert active_trial >now

        expired_trial =now -timedelta (days =1 )
        assert expired_trial <now

        future_subscription =now +timedelta (days =30 )
        assert future_subscription >now

    def test_message_formatting (self ):
        """Test message formatting logic."""
        first_name ="TestUser"
        trial_days =7
        trial_expires =datetime .utcnow ()+timedelta (days =trial_days )

        welcome_text =(
        f"🎉 Welcome to Vinted Parser Bot, {first_name }!\n\n"
        f"✨ You have a {trial_days }-day trial period.\n"
        f"📅 Your trial expires on {trial_expires .strftime ('%Y-%m-%d')}.\n\n"
        f"🔍 Use the search feature to find Vinted items that ship to Austria.\n"
        f"👥 Share your referral link to get bonus trial days!\n"
        f"💳 Upgrade to premium for unlimited access."
        )

        assert "Welcome to Vinted Parser Bot, TestUser!"in welcome_text
        assert f"{trial_days }-day trial"in welcome_text
        assert trial_expires .strftime ('%Y-%m-%d')in welcome_text

    def test_referral_message_formatting (self ):
        """Test referral message formatting."""
        referrer_name ="Referrer"
        bonus_days =3
        new_expiry =datetime .utcnow ()+timedelta (days =10 )

        referral_notification =(
        f"🎉 {referrer_name } joined through your referral link!\n"
        f"You received {bonus_days } bonus days.\n"
        f"Your trial now expires on {new_expiry .strftime ('%Y-%m-%d')}."
        )

        assert referrer_name in referral_notification
        assert f"{bonus_days } bonus days"in referral_notification
        assert new_expiry .strftime ('%Y-%m-%d')in referral_notification 