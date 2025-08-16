Telegram‑bot project setup and repository flow (Bot API 8.3, August 2025)
=======================================================================

Scope
- One opinionated baseline that works in production.
- Copy it, then change only where your product needs it.

Tech stack
----------

- Python 3.12
- aiogram 4.x for bot logic
- FastAPI 1.4 for webhooks and REST
- httpx 0.27 with a shared AsyncClient
- Supabase PostgreSQL in the cloud
- Redis ≤ 6 for rate limits, FSM state, and Celery or Kew
- Docker and docker‑compose for local parity
- GitHub Actions for CI and CD
- pytest 7 with aiogram‑tests and respx for mocks

Repository layout
-----------------

Mirrors public templates that have shipped to prod.

```
.
├── docker-compose.yml
├── Dockerfile
├── gunicorn_conf.py
├── pyproject.toml
├── .env.example
├── alembic.ini
├── supabase/
│   └── migrations/                 # SQL files tracked by Supabase CLI
├── Makefile
├── .pre-commit-config.yaml
└── src/
    ├── config.py                   # Pydantic-settings reads ENV
    ├── main.py                     # FastAPI + aiogram webhook startup
    ├── bot/
    │   ├── keyboards/              # reply and inline builders
    │   ├── handlers/               # start.py, payments.py, referrals.py, ...
    │   ├── middlewares/
    │   ├── services/               # Vinted, YooKassa, Supabase wrappers
    │   └── utils/
    ├── db/
    │   ├── base.py                 # SQLAlchemy engine and session
    │   └── crud.py
    └── tasks/                      # Celery or Kew async jobs (crawl_vinted, ...)
tests/
```

Local bootstrap
---------------

1. Clone the repo and pick Python 3.12.
2. make venv && source .venv/bin/activate
3. cp .env.example .env and fill BOT_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY, YOOKASSA_SECRET_KEY, REDIS_URL.
4. supabase start to run Postgres, Auth, and Storage in Docker. You can point at a cloud project instead.
5. poetry install or pip install -r requirements.txt
6. supabase db push to apply the initial schema.
7. uvicorn src.main:app --reload to start FastAPI. aiogram sets the webhook at http://localhost:8000/telegram.

Runtime flow
------------

Telegram → HTTPS webhook (FastAPI) → aiogram Router
- /start runs referral logic.
- Callback data routes to inline handlers.
- /pay webhook verifies YooKassa and writes DB status.

User HTTP → GET /search
- FastAPI returns 202.
- Background task enqueues crawl_vinted. See the async concurrency note.

Supabase real‑time and REST stay off by default. Turn them on later if you add an admin panel.

Environment variables
---------------------

Use the same names as live templates.

```
BOT_TOKEN=...
WEBHOOK_DOMAIN=https://bot.example.com
WEBHOOK_PATH=/telegram
WEBHOOK_SECRET=random32
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_SERVICE_KEY=********
SUPABASE_ANON_KEY=********
REDIS_URL=redis://redis:6379/1
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_****
DEFAULT_TRIAL_DAYS=7
REFERRAL_BONUS_DAYS=3
```

Commit .env.example. Never commit .env.

Docker and compose
------------------

docker-compose.yml

```yaml
services:
  bot:
    build: .
    env_file: .env
    depends_on: [redis]
    command: >
      gunicorn -k uvicorn.workers.UvicornWorker
               -c gunicorn_conf.py
               src.main:app
    ports:
      - "8000:8000"
  redis:
    image: redis:6-alpine
  supabase:
    image: supabase/postgres:16
    # local only; production uses Supabase cloud
```

Dockerfile

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN adduser --disabled-password --gecos "" app
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false \
 && poetry install --only main --no-root
COPY src ./src
COPY gunicorn_conf.py .
USER app
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-c", "gunicorn_conf.py", "src.main:app"]
```

gunicorn_conf.py

```python
import multiprocessing

workers = 2 * multiprocessing.cpu_count() + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1500
timeout = 60
keepalive = 5
```

CI and CD
---------

GitHub Actions

- lint-and-test.yml
  - ruff
  - mypy --strict
  - pytest -n auto with coverage upload
  - fail under 90% branch coverage

- deploy.yml on main
  1. Build and push the Docker image to GHCR.
  2. supabase db push to the prod project with OIDC. No long token in the repo.
  3. Deploy the image on your host or Fly.io.
  4. Run supabase functions deploy only when WebApp assets changed.

Webhook and domain
------------------

1. Point bot.example.com to your entry with Cloudflare proxy on.
2. Issue a TLS cert with Caddy or a Cloudflare origin cert.
3. Set the webhook on startup.

```python
await bot.set_webhook(
    url=f"{settings.WEBHOOK_DOMAIN}{settings.WEBHOOK_PATH}",
    secret_token=settings.WEBHOOK_SECRET,
    drop_pending_updates=True,
)
```

4. Expose only 443 on the firewall. Do not expose Postgres or Redis.

Local DX boosters
-----------------

- make targets
  - make venv, make run, make test, make fmt, make lint
- inv shell loads .env and opens a poetry shell.
- make tunnel runs cloudflared tunnel so Telegram reaches your localhost.
- .pre-commit-config.yaml runs ruff, black, and mypy on commit.
- VS Code devcontainer includes Supabase CLI and mkcert.

Repository flow
---------------

- Branches
  - main is protected. Merge with PR and one review.
  - Use short feature branches: feat/…, fix/…, chore/…
- Commits
  - Conventional commits: feat:, fix:, refactor:, test:, docs:, chore:
- Versions and releases
  - Tag images and Git refs with semver, for example v0.6.3.
  - Release notes list schema changes and rollout steps.
- Migrations
  - All DDL lives in supabase/migrations.
  - Migrate in CI before image rollout.
- Secrets
  - Use GitHub OIDC to get a short‑lived token for Supabase.
  - Store bot and payment keys in the host secret store.

Do you need webhooks during local work? Use cloudflared or Ngrok to tunnel https to your laptop.

Launch‑day checklist
--------------------

- [ ] docker‑compose up -d works from a clean clone
- [ ] /healthz returns 200 and checks DB and Redis
- [ ] Webhook set and /start replies in a real client
- [ ] Supabase PITR on and daily backups verified
- [ ] CI green on main and blue‑green deploy flips in under 30 seconds
- [ ] README lists all env vars and make targets
- [ ] Rate limits set at the edge and at FastAPI
- [ ] Logs ship to your sink with token masks
- [ ] Alerts fire on 5xx spikes and webhook failures

This setup gives a fast async bot, a clean repo, and a direct path from a laptop to Supabase‑backed production without later rewrites.