Security blueprint: production‑grade Telegram bot and micro‑services
===================================================================

This playbook lists the decisions we ship today. Follow it verbatim to reach a baseline production security level. Add hardening later.

Threat model at a glance
------------------------

Attack surface
- Telegram Bot API (webhook or long‑poll)
- FastAPI JSON endpoints (/search, /payments, and more)
- Supabase Postgres and REST/GraphQL edge
- Outbound scrapers (Vinted) and inbound payment webhooks (YooKassa)

Main risks
- Token leakage and MitM
- Fake webhooks
- SQLi and IDOR
- Secrets in repos or images
- DoS bursts
- Supply‑chain exploits

Transport‑level encryption
--------------------------

TLS everywhere
- Terminate TLS 1.3 at Cloudflare or Nginx with Let’s Encrypt.
- Set HSTS to block downgrade.

Headers
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'none'; frame-ancestors 'none';
```

Telegram
- Use webhook mode at https://<bot>.yourdomain.tld/telegram.
- Keep TLS under your control.
- Do not place the token in URLs.
- Set a secret header and verify it on each POST.
  - Header: X-Telegram-Bot-Api-Secret-Token

Database
- Supabase forces SSL. Keep “SSL Enforcement” on.

Secrets and key management
--------------------------

- Do not commit tokens or keys. Add .env to .gitignore.
- Load secrets at runtime with Docker or K8s secrets. Vault or KMS is fine.
- Keys to manage: TELEGRAM_TOKEN, YOOKASSA_SECRET_KEY, SUPABASE_SERVICE_KEY, proxy creds.
- Rotate the bot token and YooKassa secret every quarter or right after a leak.

Application‑layer defenses
--------------------------

FastAPI
- Add fastapi‑limiter with Redis. Start with 10 requests per minute per IP on public routes.
- Validate every payload with Pydantic models.
- Run pip‑audit in CI on each push.
- Return JSON errors with no stack traces in prod.

Security headers
- Add the header set shown in the TLS section.
- Serve only HTTPS. Redirect HTTP to HTTPS.

Telegram bot logic
- HMAC‑sign deep‑link payloads. Use base64url(hmac_sha256(user_id|ts, BOT_SECRET)).
- Verify the signature before any credit or state change.
- Sanitize all user text before you echo it or write it.
- Log audits for /start, /pay, and all admin commands.

YooKassa webhooks
```python
import hmac, time
from hashlib import sha256
from fastapi import HTTPException

MAX_SKEW = 300  # 5 minutes

def verify_yk(request, secret: str):
    body = request.body()
    signature = request.headers.get("Yookassa-Signature", "")
    ts = int(request.headers.get("Yookassa-Timestamp", "0"))
    if abs(time.time() - ts) > MAX_SKEW:
        raise HTTPException(401, "Stale webhook")
    expected = hmac.new(secret.encode(), body, sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Bad signature")
```

Supabase
- Enable Row Level Security on every table.
- Let the backend bypass RLS with the service role key only.
- Restrict network access to Cloudflare and backend IPs.
- Enforce MFA on the Supabase org. Keep at least two owners.

Data at rest
------------

- Supabase disks use AES‑256. No extra action needed.
- For sensitive columns, add pgcrypto or client‑side AES‑GCM.

Container and CI/CD hygiene
---------------------------

- Base image: python:3.12‑slim. Run as a non‑root user.
- Use multi‑stage builds. Keep build secrets out of the runtime image.
- Sign images with cosign. Enable Docker Content Trust.
- Run trivy image in CI.
- Run Supabase migrations in CI with OIDC short‑lived tokens. Avoid long‑lived PATs.

Edge protection and WAF
-----------------------

- Put all public endpoints behind Cloudflare.
- Turn on API Shield with the OWASP Core Ruleset in block mode.
- Require mTLS client certs on internal callback endpoints.

Do you need mTLS on day one? Use it on staff‑only or cross‑region callbacks. Add it later on low‑risk paths.

Monitoring and incident response
--------------------------------

Metrics
- Expose Prometheus counters: auth failures, 4xx, 5xx, webhook verify failures.
- Track rate‑limit hits and queue depth.

Logs
- Ship logs to Loki or Cloudflare Logs for 30 days.
- Mask tokens with regex before shipping.

Alerts
- More than 20 failed webhook checks in 5 minutes.
- More than 5 Supabase connection errors per minute.
- More than 100 rate‑limit hits per minute.

Backups and disaster recovery
-----------------------------

- Keep Supabase PITR on.
- Run a monthly restore test into a shadow project.
- Dump the database nightly to S3 with SSE‑KMS.

Hardening checklist
-------------------

- [ ] TLS 1.3 passes SSL Labs with A+
- [ ] Bot token in KMS or env only, never in logs
- [ ] RLS on every table, policies reviewed
- [ ] fastapi‑limiter returns 429 on flood tests
- [ ] Cloudflare OWASP rules in block mode
- [ ] All secrets rotated after prod cutover
- [ ] Dependency scan and image scan are green
- [ ] PITR restore proven under 30 minutes
- [ ] Incident runbook stored in the repo and Notion

This baseline gives encryption in transit and at rest, strict keys, strong access rules, and layered filters that fit this stack.