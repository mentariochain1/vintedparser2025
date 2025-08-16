Python Telegram bot referral system: technical survey and design notes
=====================================================================

Overview
- Give each user a personal invite link inside Telegram.
- Extend a user’s trial when a new user joins through that link.
- No landing pages. Fit the flow into your current bot stack.

Deep linking basics
-------------------

- Use links like https://t.me/<bot_username>?start=<payload>
- Telegram delivers the payload to the /start handler after the user taps Start.
- Payload may use base64 URL characters and must stay under 64 characters.
- Encode the inviter’s id or a signed alias in the payload.
- For groups, use startgroup, but most referral flows live in private chats.

Open-source references
----------------------

- Telegram-Referral-System
  - python-telegram-bot, SQLite, single file.
  - Links like t.me/bot?start={uid}. Tables for referrals and points.

- altaffoc/telebot and svtcore/telegram-referral-bot
  - Pyrogram or Telethon scripts.
  - Show deep-link parsing, .env, and rate spacing. Not production logic.

- chat01 “Бот с реферальной системой”
  - Aiogram and SQLAlchemy.
  - Model User with referrer_id and balance. One-time credit to parent.

- Telegram-Subscription-bot
  - Subscription template with trial_days in config.
  - Cron that downgrades when expires_at is in the past. Easy to adapt.

Architecture
------------

Data model
- users
  - id PK
  - tg_id UNIQUE
  - joined_at TIMESTAMP
  - referred_by FK users.id NULL
  - trial_expires TIMESTAMP
  - referrals_count INT DEFAULT 0
  - bonus_days INT DEFAULT 0

- referrals
  - id PK
  - inviter_id FK users.id
  - invitee_id FK users.id UNIQUE
  - created_at TIMESTAMP
  - bonus_awarded BOOLEAN

Indexes and constraints
- UNIQUE on referrals.invitee_id to block double credit.
- INDEX on users.referred_by for reports.
- CHECK that users.trial_expires does not exceed a hard cap if you need one.

Flow
- User sends /start with no args
  - Create user. Set trial_expires to now plus DEFAULT_TRIAL.
  - Show link: t.me/YourBot?start=<payload>

- Friend opens link and triggers /start <payload>
  - Decode payload to inviter id.
  - Block self invites and repeat credit.
  - Insert referrals row.
  - Increment inviter.referrals_count.
  - Add REFERRAL_BONUS_DAYS to inviter.trial_expires.
  - Commit once. Then notify both users.

- A daily job scans users with trial_expires before now and downgrades them.

Payload design
--------------

- Keep it short and signed. Use base64 URL and drop padding.
- Add an expiry to the token to limit replay.

Example
```python
import base64, hmac, time, os
from hashlib import sha256

SECRET = os.environ.get("REFERRAL_SECRET", "change-me").encode()
TTL_SECONDS = 14 * 24 * 3600

def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def encode_payload(inviter_id: int) -> str:
    ts = int(time.time())
    body = f"{inviter_id}:{ts}".encode()
    sig = hmac.new(SECRET, body, sha256).digest()[:9]
    return b64u(body + b":" + sig)

def decode_payload(token: str) -> int | None:
    raw = b64u_decode(token)
    try:
        body, sig = raw.rsplit(b":", 1)
    except ValueError:
        return None
    good = hmac.new(SECRET, body, sha256).digest()[:9]
    if not hmac.compare_digest(sig, good):
        return None
    inviter_str, ts_str = body.decode().split(":")
    ts = int(ts_str)
    if time.time() - ts > TTL_SECONDS:
        return None
    return int(inviter_str)
```

Framework choices
-----------------

- python-telegram-bot v21
  - Mature sync API. Wide examples. Good for WSGI stacks.
- aiogram v4
  - Async first. Good fit for ASGI and async databases.

Handler example with Aiogram
----------------------------

```python
from aiogram import Router, types
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta, datetime

router = Router()
BONUS_DAYS = 3
DEFAULT_TRIAL_DAYS = 7
MAX_TRIAL_DAYS = 90

async def get_or_create_user(session: AsyncSession, tg_id: int):
    from models import User
    row = await session.execute(select(User).where(User.tg_id == tg_id))
    user = row.scalar_one_or_none()
    if user:
        return user, False
    user = User(tg_id=tg_id, joined_at=datetime.utcnow())
    user.trial_expires = datetime.utcnow() + timedelta(days=DEFAULT_TRIAL_DAYS)
    session.add(user)
    await session.commit()
    return user, True

def cap_trial(dt: datetime) -> datetime:
    cap = datetime.utcnow() + timedelta(days=MAX_TRIAL_DAYS)
    return min(dt, cap)

@router.message(CommandStart(deep_link=True))
async def start(message: types.Message, command: CommandStart, session: AsyncSession):
    from models import User, Referral
    me, _ = await get_or_create_user(session, message.from_user.id)

    inviter = None
    if command.args:
        inviter_id = decode_payload(command.args)
        if inviter_id:
            inviter = await session.execute(select(User).where(User.id == inviter_id))
            inviter = inviter.scalar_one_or_none()

    award = False
    if inviter and inviter.id != me.id and not me.referred_by:
        exists = await session.execute(
            select(Referral).where(Referral.invitee_id == me.id)
        )
        if not exists.scalar_one_or_none():
            me.referred_by = inviter.id
            inviter.referrals_count += 1
            new_expiry = inviter.trial_expires + timedelta(days=BONUS_DAYS)
            inviter.trial_expires = cap_trial(new_expiry)
            session.add_all([me, inviter, Referral(inviter_id=inviter.id, invitee_id=me.id, bonus_awarded=True)])
            await session.commit()
            award = True

    if award:
        await message.bot.send_message(
            inviter.tg_id,
            f"🎉 {message.from_user.first_name} joined through your link. "
            f"Your trial ends on {inviter.trial_expires:%Y-%m-%d}."
        )

    await message.answer(
        f"Welcome. Your trial is active until {me.trial_expires:%Y-%m-%d}."
    )
```

Fraud control and reliability
-----------------------------

- Credit only when the invitee is a new user in your database.
- Block self referrals.
- One bonus per invitee. Enforce with a UNIQUE constraint.
- Add a max total bonus. Cap trial at MAX_TRIAL_DAYS.
- Add a token TTL to limit replay.
- Delay credit until a conversion step if you need stronger proof.
- Watch spikes per inviter and shared device patterns.
- Log tokens and referral ids for audits.

Operations
----------

- Use a daily job to revoke expired trials.
- Make award paths idempotent. Wrap in a single transaction.
- Keep a retry on transient DB errors.
- Localize all messages. Avoid leaking full names to referrers if that matters.
- Track key events: referral_link_shown, start_with_args, referral_awarded.

Environment
-----------

- REFERRAL_BONUS_DAYS=3
- DEFAULT_TRIAL_DAYS=7
- MAX_TRIAL_DAYS=90
- REFERRAL_SECRET=base64 or hex secret
- BOT_TOKEN=...
- DATABASE_URL=postgresql://...

Checklist
---------

- [ ] Add aiogram>=4.2 or python-telegram-bot>=21 and SQLAlchemy>=2.0.
- [ ] Create users and referrals tables with constraints from this spec.
- [ ] Implement encode_payload and decode_payload with base64 URL and HMAC.
- [ ] Add /invite to show the user’s link and current trial end date.
- [ ] Pick webhook or long poll. For webhooks, handle TLS and a health check.
- [ ] Schedule a daily expiry job with Celery beat or APScheduler.
- [ ] Tests for self referral, double credit, cap, and expiry.
- [ ] Dashboards for referral rate, award count, and fraud flags.

Link builder
------------

```python
def invite_link(bot_username: str, inviter_id: int) -> str:
    token = encode_payload(inviter_id)
    return f"https://t.me/{bot_username}?start={token}"
```

With these parts in place, you can ship a clean referral program in one sprint. It will work end to end inside Telegram and will not need a website.