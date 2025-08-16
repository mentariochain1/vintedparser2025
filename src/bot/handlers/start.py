from aiogram import Router, types, F
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.user_service import UserService
from bot.keyboards import ReplyKeyboards
from db.base import get_db_session

router = Router()
user_service = UserService()

@router.message(CommandStart())
async def start_handler(message: types.Message, command: CommandStart) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        try:
            async with get_db_session() as session:
                existing_user = await user_service.get_user(session, user_id)

                if existing_user:
                    await _show_existing_user_status(message, existing_user)
                    return

                referrer_id = None
                referral_message = ""

                if command.args:
                    referrer_id = user_service.decode_referral_payload(command.args)
                    if referrer_id:
                        referrer = await user_service.get_user_by_id(session, referrer_id)
                        if not referrer:
                            referrer_id = None
                        elif referrer_id == user_id:
                            referrer_id = None
                            referral_message = "\n\n⚠️ Ты не можешь пригласить сам себя!"

                new_user = await user_service.create_user(
                    session=session,
                    tg_id=user_id,
                    username=username,
                    first_name=first_name,
                    referrer_id=referrer_id
                )

                if referrer_id:
                    success, ref_message = await user_service.process_referral(
                        session=session,
                        inviter_id=referrer_id,
                        invitee_id=new_user.id
                    )

                    if success:
                        referrer = await user_service.get_user_by_id(session, referrer_id)
                        if referrer:
                            try:
                                await message.bot.send_message(
                                    referrer.tg_id,
                                    f"🎉 {first_name or 'Кто-то'} присоединился по твоей реферальной ссылке!\n"
                                    f"Ты получил {user_service.referral_bonus_days} бонусных дней.\n"
                                    f"Твой пробный период теперь истекает {referrer.trial_expires.strftime('%d.%m.%Y')}."
                                )
                            except Exception:
                                pass

                        referral_message = f"\n\n🎁 Добро пожаловать! Тебя пригласил друг."
                    else:
                        referral_message = f"\n\n⚠️ Реферал не удалось обработать: {ref_message}"

                welcome_text = (
                    f"Привет, {first_name or 'друг'}! Добро пожаловать в AMD Parsex.\n\n"
                    f"✨ Я открыл для тебя бесплатный доступ на {user_service.default_trial_days} дней. "
                    f"Твой пробный период закончится {new_user.trial_expires.strftime('%d.%m.%Y')}.\n\n"
                    f"Теперь ты можешь искать лучшие предложения на Vinted.\n\n"
                    f"🔍 Просто отправь мне название товара, и я начну поиск."
                    f"{referral_message}"
                )

                await message.answer(welcome_text, reply_markup=ReplyKeyboards.main_menu())
                return

        except Exception:
            from bot.services.user_service_asyncpg import user_service_asyncpg
            
            existing_user = await user_service_asyncpg.get_user_asyncpg(user_id)

            if existing_user:
                await _show_existing_user_status_asyncpg(message, existing_user)
                return

            referrer_id = None
            referral_message = ""

            if command.args:
                referrer_id = user_service_asyncpg.decode_referral_payload(command.args)
                if referrer_id:
                    referrer = await user_service_asyncpg.get_user_by_id_asyncpg(referrer_id)
                    if not referrer:
                        referrer_id = None
                    elif referrer_id == user_id:
                        referrer_id = None
                        referral_message = "\n\n⚠️ Ты не можешь пригласить сам себя!"

            new_user = await user_service_asyncpg.create_user_asyncpg(
                tg_id=user_id,
                username=username,
                first_name=first_name,
                referrer_id=referrer_id
            )

            if referrer_id:
                success, ref_message = await user_service_asyncpg.process_referral_asyncpg(
                    inviter_id=referrer_id,
                    invitee_id=new_user['id']
                )

                if success:
                    referrer = await user_service_asyncpg.get_user_by_id_asyncpg(referrer_id)
                    if referrer:
                        try:
                            await message.bot.send_message(
                                referrer['tg_id'],
                                f"🎉 {first_name or 'Кто-то'} присоединился по твоей реферальной ссылке!\n"
                                f"Ты получил {user_service_asyncpg.referral_bonus_days} бонусных дней.\n"
                                f"Твой пробный период теперь истекает {referrer['trial_expires'].strftime('%d.%m.%Y')}."
                            )
                        except Exception:
                            pass

                    referral_message = f"\n\n🎁 Добро пожаловать! Тебя пригласил друг."
                else:
                    referral_message = f"\n\n⚠️ Реферал не удалось обработать: {ref_message}"

            welcome_text = (
                f"Привет, {first_name or 'друг'}! Добро пожаловать в AMD Parsex.\n\n"
                f"✨ Я открыл для тебя бесплатный доступ на {user_service_asyncpg.default_trial_days} дней. "
                f"Твой пробный период закончится {new_user['trial_expires'].strftime('%d.%m.%Y')}.\n\n"
                f"Теперь ты можешь искать лучшие предложения на Vinted.\n\n"
                f"🔍 Просто отправь мне название товара, и я начну поиск."
                f"{referral_message}"
            )

            await message.answer(welcome_text, reply_markup=ReplyKeyboards.main_menu())

    except Exception as error:
        from error_handlers import error_handler
        from exceptions import DatabaseError, ReferralError
        
        # Supabase REST fallback removed; rely on search-only mode if DB is down
        
        if "referral" in str(error).lower():
            bot_error = ReferralError(f"Referral processing failed: {str(error)}")
        else:
            bot_error = DatabaseError(f"Database connection failed: {str(error)}")
        
        error_handler.log_error(bot_error, {
            "user_id": user_id,
            "command": "/start",
            "has_referral": bool(command.args)
        })
        
        fallback_message = (
            f"👋 Добро пожаловать, {first_name or 'друг'}!\n\n"
            f"⚠️ Сервис временно недоступен. Попробуйте позже.\n\n"
            f"🔍 Поиск товаров доступен без ограничений."
        )
        
        await message.answer(fallback_message, reply_markup=ReplyKeyboards.main_menu())

async def _show_existing_user_status(message: types.Message, user) -> None:
    first_name = message.from_user.first_name or "друг"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    trial_active = user.trial_expires > now
    subscription_active = user.subscription_expires and user.subscription_expires > now

    if trial_active:
        status_text = (
            f"👋 С возвращением, {first_name}!\n\n"
            f"✨ Напоминаю, твой пробный доступ активен до {user.trial_expires.strftime('%d.%m.%Y')}.\n"
            f"🤝 Приглашённых друзей: {user.referrals_count}.\n\n"
            f"🔍 Что будем искать сегодня на Vinted?"
        )
    elif subscription_active:
        status_text = (
            f"👋 С возвращением, {first_name}!\n\n"
            f"💎 Твоя премиум подписка активна до {user.subscription_expires.strftime('%d.%m.%Y')}.\n\n"
            f"👥 У тебя {user.referrals_count} приглашённых друзей.\n\n"
            f"🔍 Поищем что-нибудь на Vinted?"
        )
    else:
        status_text = (
            f"👋 С возвращением, {first_name}!\n\n"
            f"⏰ Твой пробный период истёк {user.trial_expires.strftime('%d.%m.%Y')}.\n\n"
            f"👥 У тебя {user.referrals_count} приглашённых друзей.\n\n"
            f"💳 Оформи премиум для продолжения использования бота.\n"
            f"👥 Или поделись реферальной ссылкой для получения бонусных дней!"
        )

    await message.answer(status_text, reply_markup=ReplyKeyboards.main_menu())

async def _show_existing_user_status_asyncpg(message: types.Message, user: dict) -> None:
    first_name = message.from_user.first_name or "друг"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    trial_active = user['trial_expires'] > now
    subscription_active = user['subscription_expires'] and user['subscription_expires'] > now

    if trial_active:
        status_text = (
            f"👋 С возвращением, {first_name}!\n\n"
            f"✨ Напоминаю, твой пробный доступ активен до {user['trial_expires'].strftime('%d.%m.%Y')}.\n"
            f"🤝 Приглашённых друзей: {user['referrals_count']}.\n\n"
            f"🔍 Что будем искать сегодня на Vinted?"
        )
    elif subscription_active:
        status_text = (
            f"👋 С возвращением, {first_name}!\n\n"
            f"💎 Твоя премиум подписка активна до {user['subscription_expires'].strftime('%d.%m.%Y')}.\n\n"
            f"👥 У тебя {user['referrals_count']} приглашённых друзей.\n\n"
            f"🔍 Поищем что-нибудь на Vinted?"
        )
    else:
        status_text = (
            f"👋 С возвращением, {first_name}!\n\n"
            f"⏰ Твой пробный период истёк {user['trial_expires'].strftime('%d.%m.%Y')}.\n\n"
            f"👥 У тебя {user['referrals_count']} приглашённых друзей.\n\n"
            f"💳 Оформи премиум для продолжения использования бота.\n"
            f"👥 Или поделись реферальной ссылкой для получения бонусных дней!"
        )

    await message.answer(status_text, reply_markup=ReplyKeyboards.main_menu())


# Removed start test callback handler