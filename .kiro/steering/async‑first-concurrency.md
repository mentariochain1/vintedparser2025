Async‑first concurrency layer for the Vinted search service
===========================================================

Target
- About 10k monthly users. That is 300–600 searches per day with short bursts.
- Answer fast at the API. Crawl, hydrate, and store in the background.

Components
----------

HTTP client
- httpx.AsyncClient with a shared pool and sane timeouts.
- Alternative: aiohttp.ClientSession with a connector limit.

Concurrency control
- aiometer for max_at_once and max_per_second throttles.
- For heavy CPU work, use aiomultiprocess.Pool.

Task runner
- Celery with Redis for cross‑service reliability.
- Kew for a light async queue inside FastAPI.

API front end
- FastAPI with async endpoints.
- Fire a background job right after you send 200 or 202.

Runtime
- gunicorn with uvicorn workers.
- Workers: about 2 × CPU + 1.
- Worker connections: 1,500–2,000 on an 8‑core host gives about 15,000 sockets.

Execution flow
--------------

- Client hits GET /search.
- FastAPI returns in under 100 ms and queues a crawl job.
- The crawl job fetches search pages, then hydrates item details.
- The job writes items and photos in batches.

Background job sketch
---------------------

```python
import asyncio, httpx, aiometer
from typing import Iterable

API_BASE = "https://www.vinted.at/api/v2"
MAX_PAGES = 5
MAX_AT_ONCE = 10
MAX_PER_SECOND = 8
TIMEOUT = httpx.Timeout(10.0, connect=10.0)

async def fetch_page(client: httpx.AsyncClient, params: dict, page: int) -> list[dict]:
    r = await client.get(f"{API_BASE}/catalog/items", params={**params, "page": page})
    r.raise_for_status()
    return r.json().get("items", [])

async def fetch_item(client: httpx.AsyncClient, item_id: int) -> dict:
    r = await client.get(f"{API_BASE}/items/{item_id}")
    r.raise_for_status()
    return r.json()

async def crawl_search(client: httpx.AsyncClient, params: dict) -> list[dict]:
    pages: Iterable[int] = range(1, MAX_PAGES + 1)
    page_results = await aiometer.run_on_each(
        lambda p: fetch_page(client, params, p),
        pages,
        max_at_once=MAX_AT_ONCE,
        max_per_second=MAX_PER_SECOND,
    )
    items = [i for page in page_results for i in page]  # flatten

    detail_ids = [i["id"] for i in items]
    details = await aiometer.run_on_each(
        lambda item_id: fetch_item(client, item_id),
        detail_ids,
        max_at_once=MAX_AT_ONCE,
        max_per_second=MAX_PER_SECOND,
    )
    return details
```

FastAPI glue
------------

```python
from fastapi import FastAPI, BackgroundTasks
import httpx, hashlib

app = FastAPI()
client: httpx.AsyncClient | None = None

@app.on_event("startup")
async def startup():
    global client
    client = httpx.AsyncClient(
        timeout=TIMEOUT,
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        headers={"user-agent": "your-service/1.0"},
    )

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()  # type: ignore

async def crawl_vinted(params: dict):
    assert client is not None
    details = await crawl_search(client, params)
    # write to DB in batches here

@app.get("/search")
async def search(q: str, background: BackgroundTasks):
    params = {"search_text": q, "country_ids": 14, "per_page": 100}
    job_key = hashlib.md5(str(params).encode()).hexdigest()
    background.add_task(crawl_vinted, params.copy())
    return {"status": "scheduled", "job": job_key}
```

Tuning and guardrails
---------------------

Connection and rate limits
- httpx limits: max_connections=50, max_keepalive_connections=20.
- Start with max_at_once=10 and max_per_second=8 at aiometer.
- Tighten rate if you see 429 or 503 spikes.

Session reuse
- Keep one AsyncClient per worker and close it on shutdown.
- One‑shot sessions waste time and sockets.

CPU fallback
- Offload heavy parsing to aiomultiprocess.Pool.
- Set maxtasksperchild to recycle workers and cap leaks.

Workers and memory
- Start with workers = 2 × CPU + 1.
- Each FastAPI worker uses about 60–90 MB at idle.
- Load test and then adjust.

Idempotency
- Use Redis SETNX on (query_hash, page) with a 2‑minute TTL.
- Drop duplicate jobs at enqueue time.

Observability
- Expose /metrics for Prometheus.
- Track request count, crawl_jobs, crawl_errors, crawl_latency.
- Add X‑Request‑ID. Emit spans from both API and worker.

Retry and backoff
- Back off on 429 and 503 with jitter.
- Cap retries per URL to three attempts.

Hydration notes
---------------

- Search returns one preview image in photo.
- Item details return the full photos array.
- Fetch details only once per item id and cache for a short time.

Store model
-----------

- Item: id, title, price, currency, url, created_ts, updated_ts, preview_img, ships_to_AT flag.
- Photo: item_id, order_no, url, local_path if downloaded.

Queue choices
-------------

- BackgroundTasks is fine under 1 request per second.
- Switch to Celery or Kew when bursts grow or you need retries across nodes.

Safety and compliance
---------------------

- Respect Vinted rate limits and TOS.
- Cap per‑IP requests at about 30 per minute.
- Protect secrets and proxy creds in env vars.

Production checklist
--------------------

- [ ] Pin httpx>=0.27, aiometer~=0.5, aiomultiprocess~=0.10.
- [ ] Env: MAX_CONCURRENCY, MAX_RPS, WORKERS, DB_POOL_SIZE.
- [ ] Return 503 when the in‑memory queue exceeds worker × 4.
- [ ] Health check hits DB and a canary Vinted endpoint.
- [ ] Graceful shutdown drains tasks and then closes the client.
- [ ] Tests cover pagination, 429 backoff, and concurrency caps.
- [ ] Load test at 100 rps for 5 minutes. Target p95 under 500 ms and CPU under 65%.