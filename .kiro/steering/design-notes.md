Python Vinted-to-AT parser: technical survey and design notes
=============================================================

Overview
- Goal: pull listings visible on vinted.at and items on other domains that ship to Austria.
- Reuse open-source clients for cookies, Cloudflare bypass, paging, and JSON parsing.

Open‑source clients and tools
-----------------------------

| Project / PyPI name | Last release | AT domain switch? | Images exposed | Notes |
|---|---|---|---|---|
| vinted-api-wrapper (PyPI) | 0.3.9 (Jul 16 2025) | yes (Vinted(domain="at")) | item.photo in search, full photos[] in item_info() | Most current. Typed data classes. No full JavaScript rendering. Under 20 kB. Use as the core client. |
| pyVinted (aka herissondev/vinted-api-wrapper) | 0.2.4 (2024) | yes | only photo | Older fork. Use the newer wrapper unless license blocks it. |
| VintedAPIClient | 0.1.3 (2024) | domain follows the URL | download_images_by_url saves all pictures | Handy helper when you only have an item URL. |
| vinted_downloader | 0.3.0 (2023) | any URL | CLI and Python. Downloads item.json, every photo, and seller avatar | Good for batch export or for multi-image logic. |
| vinted_scraper | 0.2.x (2024) | pass base URL "https://www.vinted.at" | photos exposed in item() | Lightweight but uses HTML and a legacy API. It breaks more often. |
| Pynted (Scrapy) | 2019 | feed URL param can point at AT | saves all pics to S3 | French focus. Works after small fixes. Runs on a Scrapy cluster. |
| Gertje823/Vinted-Scraper | 2024 | any domain | stores picture paths and downloads files | Ships with a local SQLite DB. |

HTTP endpoints that matter
--------------------------

Public endpoints, no auth, working in August 2025
- Search
  - GET https://www.vinted.at/api/v2/catalog/items
  - Key params
    - search_text, catalog_ids, brand_ids, and more
    - country_ids=14 for Austria. This returns only items that ship to Austria, no matter where sellers listed them.
    - per_page, page, order
- Item details
  - GET https://www.vinted.at/api/v2/items/{id}
  - Returns photos[] with all original URLs and shipping options

Wrappers handle cookies and user agent for Cloudflare. Rotate proxies if you scrape at volume.

Vinted Pro API (authenticated)
- POST and PATCH for your own items and orders.
- HMAC signature and access key required.
- Not needed for read-only imports.

Service design for Vinted → AT import
-------------------------------------

Step 0 - pick the SDK
- Use vinted-api-wrapper for reads.
- Drop to requests if the wrapper does not expose a field.

Install
```
pip install vinted-api-wrapper
```

Step 1 - search feed builder
```python
from vinted import Vinted

v = Vinted(domain="at")  # gets cookies from vinted.at

items = v.search(
    query="*",            # or pass brand_ids, catalog_ids, keywords
    country_ids=14,       # ship-to Austria
    page=1,
    per_page=100,
    order="newest_first"
)
```
items contains basic fields and one preview image.

Step 2 - hydrate to full detail and all images
```python
for lite in items.items:
    full = v.item_info(lite.id)
    imgs = [p.url for p in full.item.photos]  # full photo set
```
Need files on disk
- Use VintedAPIClient.download_images_by_url, or stream each URL with requests.
- Image URLs are direct HTTPS links with no signed tokens.

Step 3 - storage
- Item table
  - id PK, title, price, currency, brand, size, condition, description, seller_id, url, created_ts, updated_ts, ships_from_country, ships_to_AT BOOLEAN, preview_img
- Photo table
  - item_id FK, order_no, url, local_path

Step 4 - rate limit and anti-bot
- Cap at about 30 requests per minute per IP.
- Add jitter and backoff.
- Retry 503 and Cloudflare 1020 with exponential backoff.
- Rotate residential proxies if needed.

Known pitfalls
--------------

- Search returns at most 2000 results. Use paging. Slice by date or price to cover more.
- You see only one image if you skip the detail call. Search returns only photo.
- Sold items can redirect. Append ?noredirect=1 or use the item API.
- Use country_ids=14. Do not use shipping_country=AT. The legacy param was removed in mid 2024.
- The Austrian site returns EUR. Foreign items that ship to Austria are converted on the server. Treat item.price as final.

Developer checklist
-------------------

- [ ] Pin vinted-api-wrapper==0.3.9 in requirements.
- [ ] Add fallback import for VintedAPIClient to grab images in bulk.
- [ ] Support env var VINTED_PROXY for an HTTP proxy.
- [ ] Build a search module that yields (item_id, domain) pairs.
- [ ] Build a detail fetcher that writes Item and Photo rows.
- [ ] Use a worker or async queue. Target under 2 requests per second as a baseline.
- [ ] Unit tests with JSON fixtures for search and item endpoints.
- [ ] Schedule the search crawler every 30 minutes. The detail fetcher can lag and remain safe to run twice.
- [ ] Review robots.txt and the TOS. Vinted forbids commercial scraping.

Notes
- Start with vinted-api-wrapper and a small hydrator. You can ingest multi-image listings that ship to Austria in under 200 lines of Python.