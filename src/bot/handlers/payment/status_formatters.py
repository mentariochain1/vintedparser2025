from datetime import datetime, timezone
from typing import Optional

def _to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def check_user_status(user) -> dict:
    now = datetime.now(timezone.utc)
    trial_expires = _to_utc_aware(user.trial_expires)
    subscription_expires = _to_utc_aware(user.subscription_expires)
    
    return {
        'trial_active': trial_expires and trial_expires > now,
        'subscription_active': subscription_expires and subscription_expires > now,
        'trial_expires': trial_expires,
        'subscription_expires': subscription_expires
    }

def format_premium_status(expires: datetime) -> str:
    return (
        f"💎 **Статус:** Премиум активен\n"
        f"📅 **Действует до:** {expires.strftime('%Y-%m-%d')}\n\n"
        f"🔄 Продлите подписку ниже."
    )

def format_trial_status(expires: datetime) -> str:
    return (
        f"✨ **Статус:** Пробный период\n"
        f"📅 **Доступ до:** {expires.strftime('%Y-%m-%d')}\n\n"
        f"💎 Оформите Премиум, чтобы открыть все возможности."
    )

def format_expired_status(trial_expires: Optional[datetime]) -> str:
    expire_date = trial_expires.strftime('%Y-%m-%d') if trial_expires else '—'
    return (
        f"⏰ **Статус:** Доступ истёк\n"
        f"📅 **Пробный период закончился:** {expire_date}\n\n"
        f"💳 Подпишитесь на Премиум, чтобы продолжить."
    )

def build_payment_status_message(user, first_name: str) -> str:
    status = check_user_status(user)
    status_text = f"💳 **Оплата и подписка**, {first_name}!\n\n"
    
    if status['subscription_active']:
        status_text += format_premium_status(status['subscription_expires'])
    elif status['trial_active']:
        status_text += format_trial_status(status['trial_expires'])
    else:
        status_text += format_expired_status(status['trial_expires'])
        
    return status_text

def get_user_status_info(user) -> dict:
    now = datetime.now(timezone.utc)
    trial_expires = _to_utc_aware(user.trial_expires)
    subscription_expires = _to_utc_aware(user.subscription_expires)
    
    return {
        'trial_active': trial_expires and trial_expires > now,
        'subscription_active': subscription_expires and subscription_expires > now
    }

def calculate_days_remaining(expires_date: datetime) -> int:
    now = datetime.now(timezone.utc)
    return (expires_date - now).days

def build_detailed_status_text(user, status_info: dict) -> str:
    trial_active = status_info['trial_active']
    subscription_active = status_info['subscription_active']
    
    if subscription_active:
        return (
            f"💎 **Премиум активен**\n\n"
            f"📅 **Действует до:** {user.subscription_expires.strftime('%Y-%m-%d')}\n"
            f"👥 **Рефералы:** {user.referrals_count}\n\n"
            f"✅ Доступ открыт ко всем функциям."
        )
    elif trial_active:
        return (
            f"✨ **Пробный период активен**\n\n"
            f"📅 **Доступ до:** {user.trial_expires.strftime('%Y-%m-%d')}\n"
            f"👥 **Рефералы:** {user.referrals_count}\n\n"
            f"💡 Оформите Премиум для безлимитного доступа."
        )
    else:
        return (
            f"⏰ **Доступ истёк**\n\n"
            f"📅 **Пробный закончился:** {user.trial_expires.strftime('%Y-%m-%d')}\n"
            f"👥 **Рефералы:** {user.referrals_count}\n\n"
            f"💳 Оформите Премиум, чтобы продолжить."
        )

def build_subscription_status_text(user, status_info: dict) -> str:
    trial_active = status_info['trial_active']
    subscription_active = status_info['subscription_active']
    
    if subscription_active:
        days_left = calculate_days_remaining(user.subscription_expires)
        return (
            f"💎 **Премиум**\n\n"
            f"✅ **Статус:** Активен\n"
            f"📅 **Действует до:** {user.subscription_expires.strftime('%Y-%m-%d')}\n"
            f"⏰ **Осталось дней:** {days_left}\n"
            f"👥 **Рефералы:** {user.referrals_count}\n\n"
            f"🎉 Доступ открыт ко всем функциям!"
        )
    elif trial_active:
        days_left = calculate_days_remaining(user.trial_expires)
        return (
            f"✨ **Пробный период**\n\n"
            f"✅ **Статус:** Активен\n"
            f"📅 **Доступ до:** {user.trial_expires.strftime('%Y-%m-%d')}\n"
            f"⏰ **Осталось дней:** {days_left}\n"
            f"👥 **Рефералы:** {user.referrals_count}\n\n"
            f"💡 Используйте /pay, чтобы оформить Премиум."
        )
    else:
        return (
            f"⏰ **Доступ истёк**\n\n"
            f"❌ **Статус:** Нет доступа\n"
            f"📅 **Пробный закончился:** {user.trial_expires.strftime('%Y-%m-%d')}\n"
            f"👥 **Рефералы:** {user.referrals_count}\n\n"
            f"💳 Используйте /pay, чтобы оформить Премиум!"
        )
