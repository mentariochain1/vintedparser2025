"""Helper functions to eliminate code duplication across bot handlers."""

from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Union, Any


def _format_date(date: datetime) -> str:
    """Format dates consistently as 'YYYY-MM-DD'.
    
    Args:
        date: DateTime object to format
        
    Returns:
        str: Formatted date string in YYYY-MM-DD format
    """
    return date.strftime('%Y-%m-%d')


def _get_user_status(user: Union[Any, Dict[str, Any]]) -> Dict[str, Any]:
    """Return standardized status info (is_premium, is_trial, days_left, expires_date).
    
    Args:
        user: User object (SQLAlchemy model or dict) containing user data
        
    Returns:
        dict: Dictionary containing standardized status information
    """
    now = datetime.now(timezone.utc)
    
    # Handle both SQLAlchemy objects and dictionaries
    trial_expires = getattr(user, 'trial_expires', None) if hasattr(user, 'trial_expires') else user.get('trial_expires')
    subscription_expires = getattr(user, 'subscription_expires', None) if hasattr(user, 'subscription_expires') else user.get('subscription_expires')
    referrals_count = getattr(user, 'referrals_count', 0) if hasattr(user, 'referrals_count') else user.get('referrals_count', 0)
    
    # Ensure timezone awareness
    if trial_expires and trial_expires.tzinfo is None:
        trial_expires = trial_expires.replace(tzinfo=timezone.utc)
    if subscription_expires and subscription_expires.tzinfo is None:
        subscription_expires = subscription_expires.replace(tzinfo=timezone.utc)
    
    # Check active status
    trial_active = trial_expires and trial_expires > now
    subscription_active = subscription_expires and subscription_expires > now
    
    # Calculate days left and determine primary status
    is_premium = subscription_active
    is_trial = trial_active and not subscription_active
    
    if subscription_active:
        days_left = (subscription_expires - now).days
        expires_date = _format_date(subscription_expires)
    elif trial_active:
        days_left = (trial_expires - now).days
        expires_date = _format_date(trial_expires)
    else:
        days_left = 0
        expires_date = _format_date(trial_expires) if trial_expires else None
    
    return {
        'is_premium': is_premium,
        'is_trial': is_trial,
        'days_left': days_left,
        'expires_date': expires_date,
        'trial_expires': trial_expires,
        'subscription_expires': subscription_expires,
        'referrals_count': referrals_count,
        'has_access': is_premium or is_trial
    }


def _create_status_text(user: Union[Any, Dict[str, Any]], first_name: str) -> str:
    """Generate consistent status messages.
    
    Args:
        user: User object or dict containing user data
        first_name: User's first name for personalization
        
    Returns:
        str: Formatted status text message
    """
    status = _get_user_status(user)
    
    if status['is_premium']:
        return (
            f"💎 **Премиум активен**\n\n"
            f"✅ Активен до {status['expires_date']}\n"
            f"👥 Рефералов: {status['referrals_count']}\n"
            f"🔍 Безлимитный поиск доступен"
        )
    elif status['is_trial']:
        return (
            f"✨ **Пробный период**\n\n"
            f"⏰ Истекает: {status['expires_date']}\n"
            f"👥 Рефералов: {status['referrals_count']}\n"
            f"🔍 Бесплатный поиск доступен"
        )
    else:
        return (
            f"⏰ **Пробный период истёк**\n\n"
            f"❌ Истёк: {status['expires_date'] or 'Неизвестно'}\n"
            f"👥 Рефералов: {status['referrals_count']}\n"
            f"💳 Нужна подписка для поиска"
        )


def _create_payment_status_text(status: str, amount: float, currency: str, payment_id: str) -> str:
    """Format payment status messages.
    
    Args:
        status: Payment status (succeeded, pending, canceled, etc.)
        amount: Payment amount
        currency: Payment currency
        payment_id: Unique payment identifier
        
    Returns:
        str: Formatted payment status message
    """
    status_mapping = {
        'succeeded': {
            'emoji': '✅',
            'text': 'Оплата прошла',
            'message': '🎉 Подписка активирована!\nИспользуйте /start, чтобы увидеть обновлённый статус.'
        },
        'pending': {
            'emoji': '⏳',
            'text': 'Оплата в обработке',
            'message': '⏳ Платёж обрабатывается.\nМы уведомим, когда всё будет готово.'
        },
        'waiting_for_capture': {
            'emoji': '⏳',
            'text': 'Ожидает подтверждения',
            'message': '⏳ Платёж ожидает подтверждения.\nМы уведомим, когда всё будет готово.'
        },
        'canceled': {
            'emoji': '❌',
            'text': 'Платёж отменён',
            'message': '❌ Этот платёж был отменён.\nИспользуйте /pay, чтобы создать новый платёж.'
        }
    }
    
    status_info = status_mapping.get(status, {
        'emoji': '❓',
        'text': f'Статус: {status.title()}',
        'message': f'ℹ️ Статус платежа: {status}'
    })
    
    return (
        f"{status_info['emoji']} **{status_info['text']}**\n\n"
        f"💰 **Сумма**: {amount} {currency}\n"
        f"🆔 **ID платежа**: `{payment_id}`\n\n"
        f"{status_info['message']}"
    )


def _get_plan_details(data: str) -> Tuple[int, str]:
    """Extract days and description from callback data.
    
    Args:
        data: Callback data string (e.g., 'pay_monthly', 'confirm_pay_30')
        
    Returns:
        tuple[int, str]: Number of days and plan description
        
    Raises:
        ValueError: If callback data format is not recognized
    """
    # Handle direct plan selections
    plan_mapping = {
        'pay_monthly': (30, 'Премиум на месяц'),
        'pay_quarterly': (90, 'Премиум на 3 месяца'),
        'pay_yearly': (365, 'Премиум на год'),
        'monthly': (30, 'Премиум на месяц'),
        'quarterly': (90, 'Премиум на 3 месяца'),
        'yearly': (365, 'Премиум на год')
    }
    
    if data in plan_mapping:
        return plan_mapping[data]
    
    # Handle confirm_pay_X format
    if data.startswith('confirm_pay_'):
        try:
            days = int(data.split('_')[-1])
            if days == 30:
                return (days, 'Премиум на месяц')
            elif days == 90:
                return (days, 'Премиум на 3 месяца')
            elif days == 365:
                return (days, 'Премиум на год')
            else:
                return (days, f'Премиум на {days} дней')
        except (ValueError, IndexError):
            pass
    
    # Handle any numeric suffix
    if '_' in data:
        try:
            days = int(data.split('_')[-1])
            return (days, f'Премиум на {days} дней')
        except (ValueError, IndexError):
            pass
    
    raise ValueError(f"Неизвестный формат данных плана: {data}")
