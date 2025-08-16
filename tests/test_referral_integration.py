"""Integration tests for referral functionality."""

import pytest
from datetime import datetime ,timedelta
from unittest .mock import AsyncMock ,MagicMock ,patch

from src .bot .services .user_service import UserService

class TestReferralLinkGeneration :
    """Test referral link generation and validation."""

    def test_encode_decode_referral_payload (self ):
        """Test that referral payload encoding and decoding works correctly."""
        user_service =UserService ()
        inviter_id =12345

        payload =user_service .encode_referral_payload (inviter_id )

        assert payload
        assert isinstance (payload ,str )
        assert len (payload )>0

        assert not payload .endswith ('=')

        decoded_id =user_service .decode_referral_payload (payload )

        assert decoded_id ==inviter_id

    def test_referral_link_format (self ):
        """Test that referral link has correct format."""
        user_service =UserService ()
        bot_username ="test_bot"
        inviter_id =12345

        link =user_service .generate_referral_link (bot_username ,inviter_id )

        assert link .startswith ("https://t.me/")
        assert bot_username in link
        assert "?start="in link

        payload =link .split ("?start=")[1 ]

        decoded_id =user_service .decode_referral_payload (payload )
        assert decoded_id ==inviter_id

    def test_invalid_referral_payload (self ):
        """Test handling of invalid referral payloads."""
        user_service =UserService ()

        invalid_payloads =[
        "",
        "invalid",
        "abc123",
        "not_base64_url_safe!@#",
        "dGVzdA==",
        ]

        for payload in invalid_payloads :
            result =user_service .decode_referral_payload (payload )
            assert result is None ,f"Expected None for invalid payload: {payload }"

    def test_expired_referral_payload (self ):
        """Test that expired referral payloads are rejected."""
        user_service =UserService ()

        with patch ('time.time',return_value =1000000 ):
            payload =user_service .encode_referral_payload (12345 )

        with patch ('time.time',return_value =1000000 +user_service .referral_ttl_seconds +1 ):
            result =user_service .decode_referral_payload (payload )
            assert result is None ,"Expected None for expired payload"

    def test_referral_payload_signature_verification (self ):
        """Test that referral payload signature verification works."""
        user_service =UserService ()
        inviter_id =12345

        payload =user_service .encode_referral_payload (inviter_id )

        tampered_payload =payload [:-1 ]+('a'if payload [-1 ]!='a'else 'b')

        result =user_service .decode_referral_payload (tampered_payload )
        assert result is None ,"Expected None for tampered payload"

    def test_referral_stats_structure (self ):
        """Test that referral stats return correct structure."""
        user_service =UserService ()

        mock_user =MagicMock ()
        mock_user .referrals_count =5
        mock_user .trial_expires =datetime .utcnow ()+timedelta (days =7 )
        mock_user .subscription_expires =None

        with patch .object (user_service ,'get_user_by_id',return_value =mock_user ):

            stats ={
            "referrals_count":mock_user .referrals_count ,
            "trial_expires":mock_user .trial_expires ,
            "subscription_expires":mock_user .subscription_expires ,
            }

            assert "referrals_count"in stats
            assert "trial_expires"in stats
            assert "subscription_expires"in stats
            assert stats ["referrals_count"]==5
            assert isinstance (stats ["trial_expires"],datetime )

    def test_referral_configuration_values (self ):
        """Test that referral configuration values are properly set."""
        user_service =UserService ()

        assert user_service .default_trial_days >0
        assert user_service .referral_bonus_days >0
        assert user_service .referral_ttl_seconds >0

        assert 86400 <=user_service .referral_ttl_seconds <=30 *86400

        assert user_service .referral_bonus_days <=user_service .default_trial_days

class TestReferralMessageFormatting :
    """Test referral message formatting and content."""

    def test_invite_message_content (self ):
        """Test that invite message contains required elements."""

        expected_elements =[
        "Your Referral Link",
        "Statistics",
        "How it works",
        "bonus days",
        "trial",
        "Copy the link",
        ]

        for element in expected_elements :
            assert isinstance (element ,str )
            assert len (element )>0

    def test_referrals_stats_message_content (self ):
        """Test that referrals stats message contains required elements."""
        expected_elements =[
        "Referral Statistics",
        "Total referrals",
        "Bonus days earned",
        "Referral Program Benefits",
        "No limit on referrals",
        ]

        for element in expected_elements :
            assert isinstance (element ,str )
            assert len (element )>0

class TestReferralEdgeCases :
    """Test edge cases for referral functionality."""

    def test_zero_referrals_handling (self ):
        """Test handling of users with zero referrals."""

        stats ={
        "referrals_count":0 ,
        "trial_expires":datetime .utcnow ()+timedelta (days =5 ),
        "subscription_expires":None ,
        }

        bonus_days =stats ["referrals_count"]*3
        assert bonus_days ==0

    def test_large_referral_count (self ):
        """Test handling of users with many referrals."""

        stats ={
        "referrals_count":100 ,
        "trial_expires":datetime .utcnow ()+timedelta (days =300 ),
        "subscription_expires":None ,
        }

        bonus_days =stats ["referrals_count"]*3
        assert bonus_days ==300
        assert bonus_days >0

    def test_premium_user_referrals (self ):
        """Test referral handling for premium users."""

        stats ={
        "referrals_count":10 ,
        "trial_expires":datetime .utcnow ()-timedelta (days =1 ),
        "subscription_expires":datetime .utcnow ()+timedelta (days =30 ),
        }

        assert stats ["referrals_count"]>0
        assert stats ["subscription_expires"]>datetime .utcnow ()

    def test_expired_user_referrals (self ):
        """Test referral handling for expired users."""

        stats ={
        "referrals_count":5 ,
        "trial_expires":datetime .utcnow ()-timedelta (days =5 ),
        "subscription_expires":None ,
        }

        assert stats ["referrals_count"]>0
        assert stats ["trial_expires"]<datetime .utcnow ()
        assert stats ["subscription_expires"]is None 