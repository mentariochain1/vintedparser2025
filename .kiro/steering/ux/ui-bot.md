Telegram bot UI and interaction layer — August 2025 playbook
=============================================================

Scope
- Bot API 8.3 (Feb 12, 2025).
- Python examples for aiogram 4 and python‑telegram‑bot 21.
- Use these patterns as defaults and adapt to your domain.

Keyboard types
--------------

- Reply keyboard. Replaces the system keyboard at the bottom.
- Inline keyboard. Lives inside a message. Taps create a callback in chat.
- Web App button. Opens a secure web view for rich screens.
- Attachment‑menu button. Long‑lived shortcut the user adds. Not covered here.

Reply keyboards
---------------

Constructor flags
- resize. Shrinks to content.
- single_use. Hides after one tap.
- persistent. Keeps the keyboard visible across messages.
- placeholder. Grey hint in the input field.
- selective. Shows to a subset of users in a group.

Common buttons
- KeyboardButton(text). Sends plain text.
- KeyboardButtonRequestPhone. Shares contact.
- KeyboardButtonRequestGeoLocation. Shares location.
- KeyboardButtonRequestPoll. Creates a poll or a quiz.
- KeyboardButtonRequestPeer. Lets a user pick users or chats under filters.

aiogram 4
```python
from aiogram import Router, F, types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

router = Router()
KB_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Search"),
         KeyboardButton(text="👤 Invite", request_users={"max_quantity": 3})],
        [KeyboardButton(text="📍 Share location", request_location=True)],
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="Choose an action…",
)

@router.message(F.text == "/menu")
async def show_menu(msg: types.Message):
    await msg.answer("What do you need?", reply_markup=KB_MENU)

@router.message(F.text == "/done")
async def hide_menu(msg: types.Message):
    await msg.answer("Done ✔️", reply_markup=ReplyKeyboardRemove())
```

python‑telegram‑bot 21
```python
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes

KB_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Search"),
         KeyboardButton("👤 Invite", request_users={"max_quantity": 3})],
        [KeyboardButton("📍 Share location", request_location=True)],
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="Choose an action…",
)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What do you need?", reply_markup=KB_MENU)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Done ✔️", reply_markup=ReplyKeyboardRemove())

app = Application.builder().token("TOKEN").build()
app.add_handler(CommandHandler("menu", menu))
app.add_handler(CommandHandler("done", done))
```

Tips
- Keep three buttons or fewer in each row.
- Prebuild static menus. Use builders for dynamic layouts.
- Treat single_use as a hint. Do not rely on it for access control.

Inline keyboards
----------------

Button map
- InlineKeyboardButton(url=...). Opens a link with a confirm dialog.
- InlineKeyboardButton(callback_data=...). Sends CallbackQuery to the bot.
- InlineKeyboardButton(switch_inline_query=...). Inserts @bot query into a chat.
- InlineKeyboardButton(url_auth=...). OAuth with the login widget.
- InlineKeyboardButton(game_short_name=...). Launches an HTML5 game.
- InlineKeyboardButton(pay=True). Starts a payment via sendInvoice.

aiogram 4 callbacks
```python
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, F, types

router = Router()
ikb = InlineKeyboardBuilder()
ikb.button(text="Next ▶️", callback_data="next")
ikb.button(text="Open site", url="https://example.com")
ikb.adjust(2)

@router.callback_query(F.data == "next")
async def paginate(cb: types.CallbackQuery):
    await cb.answer(cache_time=5)
    await cb.message.edit_text("Page 2 of 5", reply_markup=ikb.as_markup())
```

python‑telegram‑bot 21 callbacks
```python
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

IKB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Next ▶️", callback_data="next"),
     InlineKeyboardButton("Open site", url="https://example.com")],
])

async def on_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer(cache_time=5)
    await q.edit_message_text("Page 2 of 5", reply_markup=IKB)

app = Application.builder().token("TOKEN").build()
app.add_handler(CallbackQueryHandler(on_next, pattern="^next$"))
```

Notes
- callback_data must be 64 bytes or less. Pack short keys.
- Prefer edit_message_* over sending new messages for paging.
- Business messages. All send methods accept business_connection_id when you post on a Business account.

Dynamic layouts with builders
-----------------------------

aiogram 4
```python
from aiogram.utils.keyboard import InlineKeyboardBuilder

builder = InlineKeyboardBuilder()
for i in range(1, 11):
    builder.button(text=str(i), callback_data=f"pg:{i}")
builder.adjust(3, 2)  # first row 3 buttons, then rows of 2
await msg.answer("Pick a page", reply_markup=builder.as_markup())
```

Web App buttons
---------------

- Add keyboardButtonSimpleWebView to a reply keyboard.
- The client opens a sandboxed web view. Your JS posts data back with Telegram.WebApp.sendData.
- The bot receives a message with web_app_data.

aiogram 4
```python
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

KB_WEBAPP = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Open dashboard",
                        web_app={"url": "https://your.app/webapp"})],
    ],
    resize_keyboard=True,
)

@router.message(F.text == "/dashboard")
async def open_webapp(msg: types.Message):
    await msg.answer("Opening…", reply_markup=KB_WEBAPP)

@router.message(F.web_app_data)
async def webapp_data(msg: types.Message):
    payload = msg.web_app_data.data  # JSON string from sendData
    # parse and act
    await msg.answer("Received")
```

Message reactions and bulk actions
----------------------------------

- Bots receive message_reaction and message_reaction_count updates.
- Reward users for emoji reactions without polling.
- Use deleteMessages, forwardMessages, and copyMessages for batches.

PTB 21 bulk example
```python
await context.bot.delete_messages(chat_id=chat_id, message_ids=[m1, m2, m3])
```

UX and performance checklist
----------------------------

- Keep all navigation in one inline keyboard. Edit in place.
- For callbacks, call answer with cache_time to suppress duplicate taps.
- Use persistent only for global menus. Hide the rest after use.
- Localize button text with gettext or aiogram i18n middleware.
- Encode complex callback_data with a short opaque id. Resolve on the server.
- Do not place secrets or order ids in callback_data.
- Rate‑limit edit_message_* to one or two per second for each chat.
- Track tap rates and failure rates in metrics.

These patterns give a clean, fast chat UI. They follow current Bot API rules and scale well under load.