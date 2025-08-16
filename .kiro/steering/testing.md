Testing strategy for the Telegram‑first stack (Bot API 8.3, August 2025)
=======================================================================

Mission
- Ship a fast test suite that a senior developer can extend.
- Keep CI under 5 minutes.
- Reach ≥ 90% branch coverage for bot and business logic.
- Cover three layers: unit, integration with mocks, and optional end‑to‑end.

Core tooling
------------

- pytest 7 and pytest‑asyncio 0.23 for async tests.
- aiogram 4.x at runtime. Use aiogram‑tests or aiogram‑unittest for handlers.
- respx to mock outgoing HTTPX calls to Vinted, Supabase, and YooKassa.
- pytest‑xdist and pytest‑cov for parallel runs and coverage.
- tox for a Python 3.10 to 3.12 matrix.

We do not use PTB’s harness. We run aiogram. PTB docs still help with patterns.

Test pyramid
------------

| Layer | Purpose | Tooling | Target duration |
|---|---|---|---|
| Unit (~80%) | Pure Python logic and each handler in isolation | pytest, aiogram‑tests, monkeypatch | Under 1 s per 100 tests |
| Integration (~15%) | Dispatcher with mocked Bot API and mocked HTTPX | aiogram‑tests, respx | Under 3 s per test class |
| E2E smoke (~5%) | Real test bot and staging Supabase | pytest markers, Ngrok or Cloudflare Tunnel | Nightly only |

Fixtures and helpers
--------------------

conftest.py
```python
import pytest, os, httpx, respx
from aiogram_tests import MockedBot
from aiogram_tests.handler import MessageHandler, CallbackQueryHandler
from mybot.main import router  # your Router

@pytest.fixture(scope="session")
def bot():
    return MockedBot(dispatcher=router, token="TEST_TOKEN")

@pytest.fixture
def respx_mock():
    with respx.mock(base_url="https://www.vinted.at") as mock:
        yield mock

@pytest.fixture
def supabase_stub(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test.local/db")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test_key")
    # patch supabase client factory if needed
```

Add this line to tests to import canned Update objects:
```python
# tests/__init__.py or conftest.py
pytest_plugins = ["aiogram_tests.fixtures"]
```

Speed tips
- Switch the event loop to uvloop when available.
- Reuse MockedBot and the loop across tests.

Unit tests for handlers
-----------------------

Command that returns a deep link and updates the DB
```python
import pytest
from aiogram_tests.types.dataset import MESSAGE
from aiogram_tests.handler import MessageHandler
from mybot.handlers import invite

@pytest.mark.asyncio
async def test_invite_link(bot, supabase_stub, monkeypatch):
    # patch DB call
    request = MessageHandler(invite)
    calls = await bot.query(request, message=MESSAGE.as_object(text="/invite"))
    answer = calls.send_message.fetchone()
    assert "https://t.me/" in answer.text
```

Inline keyboard callback
```python
import pytest
from aiogram_tests.types.dataset import CALLBACK_QUERY
from aiogram_tests.handler import CallbackQueryHandler
from mybot.main import router

@pytest.mark.asyncio
async def test_next_page(bot):
    cb = CALLBACK_QUERY.as_object(data="next:2")
    request = CallbackQueryHandler(router)
    calls = await bot.query(request, callback_query=cb)
    assert calls.answer_callback_query.called
    edit = calls.edit_message_text.fetchone()
    assert "Page 2" in edit.text
```

Mocking outbound HTTP
---------------------

```python
import httpx, respx, pytest

@respx.mock
@pytest.mark.asyncio
async def test_vinted_detail_fetch():
    respx.get("https://www.vinted.at/api/v2/items/1234").mock(
        return_value=httpx.Response(200, json={"item": {"id": 1234}})
    )
    data = await fetch_item(1234)  # your crawler function
    assert data["id"] == 1234
    assert respx.calls.call_count == 1
```

Retry paths and errors
```python
@respx.mock
@pytest.mark.asyncio
async def test_retry_on_429(monkeypatch):
    route = respx.get("https://www.vinted.at/api/v2/items/1")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, json={"item": {"id": 1}})
    ]
    item = await fetch_item_with_retry(1)
    assert item["id"] == 1
    assert route.call_count == 2
```

Keep common JSON fixtures in tests/data/*.json.

Integration tests
-----------------

Run Dispatcher, DB, and Bot API mock in one process. Seed Supabase’s local Docker with supabase start before the session.

pytest config
```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = ["integration", "e2e"]
addopts = "-m 'not e2e' --cov=mybot --cov-report=term-missing"
```

CI step
```yaml
- name: Integration tests
  run: pytest -m integration -n auto
```

End‑to‑end smoke tests
----------------------

- Create a test bot token and a test chat id.
- Expose the webhook with Ngrok or Cloudflare Tunnel.
- Gate E2E with a marker. Run it nightly.

Telethon example
```python
import pytest, asyncio
from telethon import TelegramClient
from telethon.tl.functions.messages import SendMessageRequest

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_start_flow_e2e():
    async with TelegramClient("e2e", api_id, api_hash) as client:
        await client(SendMessageRequest(bot_username, "/start"))
        # wait for bot reply
        @client.on(events.NewMessage(from_users=bot_username))
        async def handler(event):
            assert "Welcome" in event.message.message
            await client.disconnect()
```

Continuous Integration
----------------------

Pipeline
1. Lint and type check with ruff and mypy. Use mypy --strict.
2. Run unit and integration tests in parallel.
   ```
   pytest -n auto --dist=worksteal
   ```
3. Enforce coverage.
   ```
   [tool.coverage.report]
   fail_under = 90
   ```
4. Run E2E nightly.
5. Send failures to Slack or Telegram with a CI notifier.

Practical tips
- Cache pip and tox environments in CI.
- Set PYTEST_ADDOPTS="-q --maxfail=1" for fast feedback on PRs.
- Record test durations with --durations=10.

Best‑practice checklist
-----------------------

- [ ] Each new handler has at least one unit test and one happy‑path integration test.
- [ ] All outbound HTTP calls pass through one http_client layer for easy mocking.
- [ ] No test hits real Telegram or Vinted in CI. Use the e2e marker for real calls.
- [ ] Control time with freezegun for expiry logic.
- [ ] Reuse the event loop and MockedBot across tests to cut runtime.
- [ ] Keep callback_data builders in one module. Share between prod and tests.
- [ ] Fail CI if coverage drops or if a single test exceeds 200 ms in the durations report.

Do we need real Telegram traffic in CI? No. Keep CI hermetic. Run E2E on a schedule.