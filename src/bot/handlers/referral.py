"""Referral command handler for invite links and statistics."""

from aiogram import Router ,types
from aiogram .filters import Command
from sqlalchemy .ext .asyncio import AsyncSession

from src.bot.services.user_service import UserService
from src.db.base import get_db_session

router =Router ()
user_service =UserService ()

@router .message (Command ("invite"))
async def invite_handler (message :types .Message )->None :
    """
    Handle /invite command to show referral link and statistics.

    Generates signed deep links and displays referral statistics.
    """
    user_id =message .from_user .id
    first_name =message .from_user .first_name or "there"

    async with get_db_session ()as session :

        user =await user_service .get_user (session ,user_id )

        if not user :
            await message .answer (
            "❌ You need to start the bot first. Use /start to create your account."
            )
            return

        bot_info =await message .bot .get_me ()

        referral_link =user_service .generate_referral_link (bot_info .username ,user .id )

        stats =await user_service .get_referral_stats (session ,user .id )

        from datetime import datetime
        now =datetime .utcnow ()

        trial_active =user .trial_expires >now
        subscription_active =user .subscription_expires and user .subscription_expires >now

        if subscription_active :
            status_text =f"💎 Premium until {user .subscription_expires .strftime ('%Y-%m-%d')}"
        elif trial_active :
            days_left =(user .trial_expires -now ).days
            status_text =f"✨ Trial: {days_left } days left (expires {user .trial_expires .strftime ('%Y-%m-%d')})"
        else :
            status_text =f"⏰ Trial expired on {user .trial_expires .strftime ('%Y-%m-%d')}"

        response_text =(
        f"👥 **Your Referral Link**\n\n"
        f"🔗 `{referral_link }`\n\n"
        f"📊 **Statistics**\n"
        f"• Referred users: **{stats ['referrals_count']}**\n"
        f"• Status: {status_text }\n\n"
        f"🎁 **How it works:**\n"
        f"• Share your link with friends\n"
        f"• Get **{user_service .referral_bonus_days } bonus days** for each new user\n"
        f"• Your friends get a **{user_service .default_trial_days }-day trial**\n\n"
        f"💡 **Tip:** Copy the link above and share it on social media, "
        f"messaging apps, or with friends directly!"
        )

        await message .answer (response_text ,parse_mode ="Markdown")

@router .message (Command ("referrals"))
async def referrals_stats_handler (message :types .Message )->None :
    """
    Handle /referrals command to show detailed referral statistics.

    Shows comprehensive referral information and status.
    """
    user_id =message .from_user .id
    first_name =message .from_user .first_name or "there"

    async with get_db_session ()as session :

        user =await user_service .get_user (session ,user_id )

        if not user :
            await message .answer (
            "❌ You need to start the bot first. Use /start to create your account."
            )
            return

        stats =await user_service .get_referral_stats (session ,user .id )

        bonus_days_earned =stats ['referrals_count']*user_service .referral_bonus_days

        from datetime import datetime
        now =datetime .utcnow ()

        trial_active =user .trial_expires >now
        subscription_active =user .subscription_expires and user .subscription_expires >now

        if subscription_active :
            account_status =f"💎 **Premium Subscriber**\nExpires: {user .subscription_expires .strftime ('%Y-%m-%d')}"
        elif trial_active :
            days_left =(user .trial_expires -now ).days
            account_status =f"✨ **Trial User**\nExpires: {user .trial_expires .strftime ('%Y-%m-%d')} ({days_left } days left)"
        else :
            account_status =f"⏰ **Trial Expired**\nExpired: {user .trial_expires .strftime ('%Y-%m-%d')}"

        response_text =(
        f"📊 **Referral Statistics for {first_name }**\n\n"
        f"{account_status }\n\n"
        f"👥 **Referral Summary**\n"
        f"• Total referrals: **{stats ['referrals_count']}**\n"
        f"• Bonus days earned: **{bonus_days_earned }** days\n"
        f"• Bonus per referral: **{user_service .referral_bonus_days }** days\n\n"
        f"🎯 **Referral Program Benefits**\n"
        f"• Each friend gets a **{user_service .default_trial_days }-day trial**\n"
        f"• You get **{user_service .referral_bonus_days } bonus days** per referral\n"
        f"• No limit on referrals!\n"
        f"• Bonus days extend your current trial/subscription\n\n"
        f"💡 Use /invite to get your referral link!"
        )

        await message .answer (response_text ,parse_mode ="Markdown")