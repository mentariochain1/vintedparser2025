"""Comprehensive tests for UserService."""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.services.user_service import UserService
from src.db.models import User, Referral

class TestUserService:
    """Comprehensive test cases for UserService."""

    @pytest.fixture
    def user_service(self, mock_settings):
        """Create UserService instance for testing."""
        with patch("src.bot.services.user_service.settings", mock_settings):
            return UserService()

    @pytest .mark .asyncio
    async def test_create_user_success (self ,user_service ,mock_session ):
        """Test successful user creation."""
        with patch ("src.bot.services.user_service.UserCRUD.create")as mock_create :
            mock_user =User (
            id =1 ,
            tg_id =123456789 ,
            username ="testuser",
            first_name ="Test",
            trial_expires =datetime .utcnow ()+timedelta (days =7 ),
            )
            mock_create .return_value =mock_user

            result =await user_service .create_user (
            session =mock_session ,
            tg_id =123456789 ,
            username ="testuser",
            first_name ="Test",
            )

            assert result ==mock_user
            mock_create .assert_called_once ()
            mock_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_get_user_by_tg_id (self ,user_service ,mock_session ,sample_user ):
        """Test getting user by Telegram ID."""
        with patch ("src.bot.services.user_service.UserCRUD.get_by_tg_id")as mock_get :
            mock_get .return_value =sample_user

            result =await user_service .get_user (mock_session ,123456789 )

            assert result ==sample_user
            mock_get .assert_called_once_with (mock_session ,123456789 )

    @pytest .mark .asyncio
    async def test_extend_trial_success (self ,user_service ,mock_session ,sample_user ):
        """Test successful trial extension."""
        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get ,patch ("src.bot.services.user_service.UserCRUD.update_trial_expires")as mock_update :

            mock_get .return_value =sample_user
            updated_user =User (
            id =sample_user .id ,
            tg_id =sample_user .tg_id ,
            username =sample_user .username ,
            first_name =sample_user .first_name ,
            joined_at =sample_user .joined_at ,
            trial_expires =datetime .utcnow ()+timedelta (days =10 ),
            referrals_count =sample_user .referrals_count ,
            )
            mock_update .return_value =updated_user

            result =await user_service .extend_trial (mock_session ,1 ,3 )

            assert result ==updated_user
            mock_get .assert_called_once_with (mock_session ,1 )
            mock_update .assert_called_once ()
            mock_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_extend_trial_user_not_found (self ,user_service ,mock_session ):
        """Test trial extension when user not found."""
        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =None

            result =await user_service .extend_trial (mock_session ,999 ,3 )

            assert result is None
            mock_session .commit .assert_not_called ()

    @pytest .mark .asyncio
    async def test_is_premium_active_trial_valid (self ,user_service ,mock_session ):
        """Test premium status with valid trial."""
        user =User (
        id =1 ,
        tg_id =123456789 ,
        trial_expires =datetime .utcnow ()+timedelta (days =1 ),
        subscription_expires =None ,
        )

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =user

            result =await user_service .is_premium_active (mock_session ,1 )

            assert result is True

    @pytest .mark .asyncio
    async def test_is_premium_active_subscription_valid (self ,user_service ,mock_session ):
        """Test premium status with valid subscription."""
        user =User (
        id =1 ,
        tg_id =123456789 ,
        trial_expires =datetime .utcnow ()-timedelta (days =1 ),
        subscription_expires =datetime .utcnow ()+timedelta (days =30 ),
        )

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =user

            result =await user_service .is_premium_active (mock_session ,1 )

            assert result is True

    @pytest .mark .asyncio
    async def test_is_premium_active_expired (self ,user_service ,mock_session ):
        """Test premium status when both trial and subscription expired."""
        user =User (
        id =1 ,
        tg_id =123456789 ,
        trial_expires =datetime .utcnow ()-timedelta (days =1 ),
        subscription_expires =datetime .utcnow ()-timedelta (days =1 ),
        )

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =user

            result =await user_service .is_premium_active (mock_session ,1 )

            assert result is False

    @pytest .mark .asyncio
    async def test_is_premium_active_user_not_found (self ,user_service ,mock_session ):
        """Test premium status when user not found."""
        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =None

            result =await user_service .is_premium_active (mock_session ,999 )

            assert result is False

    @pytest .mark .asyncio
    async def test_process_referral_success (self ,user_service ,mock_session ):
        """Test successful referral processing."""
        inviter =User (id =1 ,tg_id =111 ,referrals_count =0 ,trial_expires =datetime .utcnow ()+timedelta (days =5 ))
        invitee =User (id =2 ,tg_id =222 ,referred_by =None )

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get ,patch ("src.bot.services.user_service.ReferralCRUD.get_by_invitee")as mock_get_referral ,patch ("src.bot.services.user_service.ReferralCRUD.create")as mock_create_referral ,patch ("src.bot.services.user_service.UserCRUD.increment_referrals_count")as mock_increment ,patch .object (user_service ,"extend_trial")as mock_extend :

            mock_get .side_effect =[inviter ,invitee ]
            mock_get_referral .return_value =None

            success ,message =await user_service .process_referral (mock_session ,1 ,2 )

            assert success is True
            assert "successfully"in message
            mock_create_referral .assert_called_once_with (
            session =mock_session ,
            inviter_id =1 ,
            invitee_id =2 ,
            bonus_awarded =True ,
            )
            mock_increment .assert_called_once_with (mock_session ,1 )
            mock_extend .assert_called_once_with (mock_session ,1 ,3 )
            mock_session .commit .assert_called_once ()

    @pytest .mark .asyncio
    async def test_process_referral_self_referral (self ,user_service ,mock_session ):
        """Test referral processing with self-referral attempt."""
        user =User (id =1 ,tg_id =111 )

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =user

            success ,message =await user_service .process_referral (mock_session ,1 ,1 )

            assert success is False
            assert "Cannot refer yourself"in message

    @pytest .mark .asyncio
    async def test_process_referral_already_referred (self ,user_service ,mock_session ):
        """Test referral processing when user already referred."""
        inviter =User (id =1 ,tg_id =111 )
        invitee =User (id =2 ,tg_id =222 ,referred_by =None )

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get ,patch ("src.bot.services.user_service.ReferralCRUD.get_by_invitee")as mock_get_referral :

            mock_get .side_effect =[inviter ,invitee ]
            mock_get_referral .return_value =AsyncMock ()

            success ,message =await user_service .process_referral (mock_session ,1 ,2 )

            assert success is False
            assert "already referred"in message

    @pytest .mark .asyncio
    async def test_process_referral_inviter_not_found (self ,user_service ,mock_session ):
        """Test referral processing when inviter not found."""
        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =None

            success ,message =await user_service .process_referral (mock_session ,999 ,2 )

            assert success is False
            assert "Inviter not found"in message

    def test_encode_decode_referral_payload (self ,user_service ):
        """Test referral payload encoding and decoding."""
        inviter_id =12345

        payload =user_service .encode_referral_payload (inviter_id )
        assert isinstance (payload ,str )
        assert len (payload )>0

        decoded_id =user_service .decode_referral_payload (payload )
        assert decoded_id ==inviter_id

    def test_decode_referral_payload_invalid (self ,user_service ):
        """Test decoding invalid referral payload."""

        result =user_service .decode_referral_payload ("invalid-payload")
        assert result is None

        result =user_service .decode_referral_payload ("dGVzdA")
        assert result is None

    def test_decode_referral_payload_expired (self ,user_service ):
        """Test decoding expired referral payload."""

        old_timestamp =int (time .time ())-(15 *24 *3600 )

        with patch ("time.time",return_value =old_timestamp ):
            payload =user_service .encode_referral_payload (12345 )

        result =user_service .decode_referral_payload (payload )
        assert result is None

    def test_generate_referral_link (self ,user_service ):
        """Test referral link generation."""
        bot_username ="testbot"
        inviter_id =12345

        link =user_service .generate_referral_link (bot_username ,inviter_id )

        assert link .startswith (f"https://t.me/{bot_username }?start=")
        assert len (link )>len (f"https://t.me/{bot_username }?start=")

    @pytest .mark .asyncio
    async def test_get_referral_stats_success (self ,user_service ,mock_session ,sample_user ):
        """Test getting referral statistics."""
        sample_user .referrals_count =5

        with patch ("src.bot.services.user_service.UserCRUD.get_by_id")as mock_get :
            mock_get .return_value =sample_user

            stats =await user_service .get_referral_stats (mock_session ,1 )

            assert stats ["referrals_count"]==5
            assert stats ["trial_expires"]==sample_user .trial_expires
            assert stats ["subscription_expires"]==sample_user .subscription_expires

    @pytest.mark.asyncio
    async def test_get_referral_stats_user_not_found(self, user_service, mock_session):
        """Test getting referral statistics when user not found."""
        with patch("src.bot.services.user_service.UserCRUD.get_by_id") as mock_get:
            mock_get.return_value = None

            stats = await user_service.get_referral_stats(mock_session, 999)

            assert stats["referrals_count"] == 0
            assert stats["trial_expires"] is None
            assert stats["subscription_expires"] is None

    # Additional comprehensive tests for edge cases and error handling

    @pytest.mark.asyncio
    async def test_create_user_with_referrer(self, user_service, mock_session):
        """Test user creation with referrer."""
        with patch("src.bot.services.user_service.UserCRUD.create") as mock_create:
            mock_user = User(
                id=2,
                tg_id=987654321,
                username="newuser",
                first_name="New",
                trial_expires=datetime.utcnow() + timedelta(days=7),
                referred_by=1,
            )
            mock_create.return_value = mock_user

            result = await user_service.create_user(
                session=mock_session,
                tg_id=987654321,
                username="newuser",
                first_name="New",
                referrer_id=1,
            )

            assert result == mock_user
            assert result.referred_by == 1
            mock_create.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_database_error(self, user_service, mock_session, mock_database_error):
        """Test user creation with database error."""
        with patch("src.bot.services.user_service.UserCRUD.create") as mock_create:
            mock_create.side_effect = mock_database_error

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.create_user(
                    session=mock_session,
                    tg_id=123456789,
                    username="testuser",
                    first_name="Test",
                )

            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_trial_with_cap(self, user_service, mock_session, sample_user):
        """Test trial extension with maximum cap."""
        # Set user trial to near maximum
        sample_user.trial_expires = datetime.utcnow() + timedelta(days=85)
        
        with patch("src.bot.services.user_service.UserCRUD.get_by_id") as mock_get, \
             patch("src.bot.services.user_service.UserCRUD.update_trial_expires") as mock_update:

            mock_get.return_value = sample_user
            updated_user = User(
                id=sample_user.id,
                tg_id=sample_user.tg_id,
                username=sample_user.username,
                first_name=sample_user.first_name,
                joined_at=sample_user.joined_at,
                trial_expires=datetime.utcnow() + timedelta(days=90),  # Capped at 90 days
                referrals_count=sample_user.referrals_count,
            )
            mock_update.return_value = updated_user

            result = await user_service.extend_trial(mock_session, 1, 10)

            assert result == updated_user
            # Verify the extension was capped
            max_allowed = datetime.utcnow() + timedelta(days=90)
            assert result.trial_expires <= max_allowed

    @pytest.mark.asyncio
    async def test_is_premium_active_no_user(self, user_service, mock_session):
        """Test premium status check when user doesn't exist."""
        with patch("src.bot.services.user_service.UserCRUD.get_by_id") as mock_get:
            mock_get.return_value = None

            result = await user_service.is_premium_active(mock_session, 999)

            assert result is False

    @pytest.mark.asyncio
    async def test_process_referral_invitee_not_found(self, user_service, mock_session):
        """Test referral processing when invitee not found."""
        inviter = User(id=1, tg_id=111)

        with patch("src.bot.services.user_service.UserCRUD.get_by_id") as mock_get:
            mock_get.side_effect = [inviter, None]  # inviter exists, invitee doesn't

            success, message = await user_service.process_referral(mock_session, 1, 2)

            assert success is False
            assert "Invitee not found" in message

    @pytest.mark.asyncio
    async def test_process_referral_database_error(self, user_service, mock_session, mock_database_error):
        """Test referral processing with database error."""
        inviter = User(id=1, tg_id=111, referrals_count=0, trial_expires=datetime.utcnow() + timedelta(days=5))
        invitee = User(id=2, tg_id=222, referred_by=None)

        with patch("src.bot.services.user_service.UserCRUD.get_by_id") as mock_get, \
             patch("src.bot.services.user_service.ReferralCRUD.get_by_invitee") as mock_get_referral, \
             patch("src.bot.services.user_service.ReferralCRUD.create") as mock_create_referral:

            mock_get.side_effect = [inviter, invitee]
            mock_get_referral.return_value = None
            mock_create_referral.side_effect = mock_database_error

            success, message = await user_service.process_referral(mock_session, 1, 2)

            assert success is False
            assert "Database connection failed" in message
            mock_session.rollback.assert_called_once()

    def test_encode_decode_referral_payload_edge_cases(self, user_service):
        """Test referral payload encoding/decoding edge cases."""
        # Test with very large user ID
        large_id = 999999999999
        payload = user_service.encode_referral_payload(large_id)
        decoded_id = user_service.decode_referral_payload(payload)
        assert decoded_id == large_id

        # Test with minimum user ID
        min_id = 1
        payload = user_service.encode_referral_payload(min_id)
        decoded_id = user_service.decode_referral_payload(payload)
        assert decoded_id == min_id

    def test_decode_referral_payload_malformed(self, user_service):
        """Test decoding malformed referral payloads."""
        # Empty string
        result = user_service.decode_referral_payload("")
        assert result is None

        # Invalid base64
        result = user_service.decode_referral_payload("invalid!")
        assert result is None

        # Valid base64 but wrong format
        import base64
        invalid_data = base64.urlsafe_b64encode(b"not:a:valid:format").decode().rstrip("=")
        result = user_service.decode_referral_payload(invalid_data)
        assert result is None

    def test_generate_referral_link_special_characters(self, user_service):
        """Test referral link generation with special bot username."""
        bot_username = "test_bot_123"
        inviter_id = 12345

        link = user_service.generate_referral_link(bot_username, inviter_id)

        assert link.startswith(f"https://t.me/{bot_username}?start=")
        assert len(link) > len(f"https://t.me/{bot_username}?start=")

    @pytest.mark.asyncio
    async def test_get_user_by_tg_id_not_found(self, user_service, mock_session):
        """Test getting user by Telegram ID when not found."""
        with patch("src.bot.services.user_service.UserCRUD.get_by_tg_id") as mock_get:
            mock_get.return_value = None

            result = await user_service.get_user(mock_session, 999999999)

            assert result is None
            mock_get.assert_called_once_with(mock_session, 999999999)

    @pytest.mark.asyncio
    async def test_update_user_subscription(self, user_service, mock_session, sample_user):
        """Test updating user subscription."""
        new_expiry = datetime.utcnow() + timedelta(days=30)
        
        with patch("src.bot.services.user_service.UserCRUD.update_subscription_expires") as mock_update:
            updated_user = User(
                id=sample_user.id,
                tg_id=sample_user.tg_id,
                username=sample_user.username,
                first_name=sample_user.first_name,
                joined_at=sample_user.joined_at,
                trial_expires=sample_user.trial_expires,
                subscription_expires=new_expiry,
                referrals_count=sample_user.referrals_count,
            )
            mock_update.return_value = updated_user

            result = await user_service.update_subscription(mock_session, 1, new_expiry)

            assert result == updated_user
            assert result.subscription_expires == new_expiry
            mock_update.assert_called_once_with(mock_session, 1, new_expiry)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_subscription_not_found(self, user_service, mock_session):
        """Test updating subscription when user not found."""
        new_expiry = datetime.utcnow() + timedelta(days=30)
        
        with patch("src.bot.services.user_service.UserCRUD.update_subscription_expires") as mock_update:
            mock_update.return_value = None

            result = await user_service.update_subscription(mock_session, 999, new_expiry)

            assert result is None
            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_users_by_referrer(self, user_service, mock_session):
        """Test getting users by referrer ID."""
        referred_users = [
            User(id=2, tg_id=222, referred_by=1),
            User(id=3, tg_id=333, referred_by=1),
        ]
        
        with patch("src.bot.services.user_service.UserCRUD.get_by_referrer") as mock_get:
            mock_get.return_value = referred_users

            result = await user_service.get_users_by_referrer(mock_session, 1)

            assert result == referred_users
            assert len(result) == 2
            mock_get.assert_called_once_with(mock_session, 1)

    @pytest.mark.asyncio
    async def test_delete_user(self, user_service, mock_session):
        """Test user deletion."""
        with patch("src.bot.services.user_service.UserCRUD.delete") as mock_delete:
            mock_delete.return_value = True

            result = await user_service.delete_user(mock_session, 1)

            assert result is True
            mock_delete.assert_called_once_with(mock_session, 1)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service, mock_session):
        """Test deleting non-existent user."""
        with patch("src.bot.services.user_service.UserCRUD.delete") as mock_delete:
            mock_delete.return_value = False

            result = await user_service.delete_user(mock_session, 999)

            assert result is False
            mock_session.commit.assert_not_called() 