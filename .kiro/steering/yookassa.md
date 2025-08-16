Python YooKassa integration: technology survey and developer notes
==================================================================

Overview
- Add online payments with YooKassa next to your Vinted import.
- Support bank cards and SBP now. Keep room for Apple Pay, Google Pay, and instalments.

Open-source SDKs
----------------

| Package | Latest version | Released | Sync/Async | Maintainer | Extras |
|---|---:|---|---|---|---|
| yookassa | 3.6.0 | 2025‑07‑24 | sync (requests) | YooMoney | Full v3 API, receipts, refunds, webhooks, Python ≥ 3.7 |
| async_yookassa | 0.4.x | 2025 | async (httpx, Pydantic) | community | Mirrors official models, coroutine friendly |
| yookassa_api | 0.3.x | 2024–2025 | both | community | Thin wrapper for simple flows |
| yookassa-payout | 1.2.x | 2024 | payouts | YooMoney | Mass payments only |

Recommendation
- Use yookassa==3.6.0 for the default path.
- Pick async_yookassa if your stack is ASGI and fully async.
- Both expose near‑identical domain models, so swapping is easy.

API overview (v3, Aug 2025)
---------------------------

Base URL: https://api.yookassa.ru/v3

| Endpoint | Purpose |
|---|---|
| POST /payments | Create a payment and get id and confirmation_url |
| GET /payments/{id} | Read payment status when webhooks lag |
| POST /payments/{id}/capture | Capture an auth for two‑stage flow |
| POST /payments/{id}/cancel | Void an unpaid payment |
| POST /refunds | Full or partial refund |
| POST /receipts | Fiscal receipts for 54‑FZ |
| POST /webhooks | Register callback URLs for events |

Required headers
```
Authorization: Basic base64(<shop_id>:<secret_key>)
Idempotence-Key: <uuid4>
Content-Type: application/json
```

Currency
- RUB only. YooKassa converts for the payer when needed.

Minimal code (official SDK)
---------------------------

Setup
```python
from yookassa import Configuration, Payment
Configuration.configure(account_id='123456', secret_key='pVao...')  # live creds
```

Create a payment (single stage, redirect)
```python
from uuid import uuid4

payment = Payment.create({
    "amount": {"value": "2500.00", "currency": "RUB"},
    "description": "Order #42",
    "payment_method_data": {"type": "bank_card"},
    "confirmation": {
        "type": "redirect",
        "return_url": "https://yourshop.at/payments/42/return"
    },
    "metadata": {"order_id": 42}
}, uuid4())  # Idempotence-Key

redirect_url = payment.confirmation.confirmation_url
```

Webhook handler (Flask)
```python
@app.post("/payments/webhook")
def yk_webhook():
    event = request.json
    if event["event"] == "payment.succeeded":
        p = Payment.find_one(event["object"]["id"])
        mark_order_paid(p.metadata["order_id"])
    return "", 200
```

Confirmation types
------------------

| Type | UX |
|---|---|
| redirect | Hosted payment page |
| embedded | Iframe JS widget |
| mobile_application | iOS or Android SDK tokenization |
| qr | Static or dynamic QR for SBP |
| external | SberPay deep link or app switch for SBP and others |

Two‑stage capture
-----------------

- Set "capture": false in Payment.create.
- YooKassa will place an auth hold and return status waiting_for_capture.
- Later call POST /payments/{id}/capture or cancel.

Receipts and 54‑FZ
------------------

Russian legal entities must send itemized receipts.

```python
from yookassa import Receipt
Receipt.create({
    "type": "payment",
    "payment_id": payment.id,
    "send": True,
    "customer": {"email": "a@example.com"},
    "items": [{
        "description": "Vintage sneakers",
        "amount": {"value": "2500.00", "currency": "RUB"},
        "quantity": "1.0",
        "vat_code": 2,
        "payment_mode": "full_payment",
        "payment_subject": "commodity"
    }]
})
```

Async option
------------

```python
from async_yookassa import Configuration, Payment
import asyncio, uuid

Configuration.configure('123456', 'sk_test...')

async def main():
    async with Payment() as api:
        pay = await api.create({
            "amount": {"value": "2500.00", "currency": "RUB"},
            "description": "Order #42",
            "payment_method_data": {"type": "bank_card"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://yourshop.at/payments/42/return"
            },
            "metadata": {"order_id": 42}
        }, uuid.uuid4())
        print(pay.confirmation.confirmation_url)

asyncio.run(main())
```

Security and operations
-----------------------

- Generate a fresh Idempotence-Key for each POST.
- Host webhooks on HTTPS. Add basic auth on the endpoint and verify it.
- Store only payment id, status, and minimal metadata. Never store card data.
- Respect 429. Add retry with backoff. Target about 30 requests per minute per IP.
- Use test keys with the test_ prefix in sandbox mode.
- Switch webhook DNS to production before live traffic.

Status model and events
-----------------------

- Common statuses: pending, waiting_for_capture, succeeded, canceled.
- Common events: payment.succeeded, payment.canceled, refund.succeeded.
- Always reload the payment by id in the webhook to trust server state.

Implementation checklist
------------------------

- [ ] Pin yookassa==3.6.0. Add async_yookassa if you run ASGI.
- [ ] ENV: YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_TEST_MODE.
- [ ] Service method create_payment(order) that returns a redirect URL.
- [ ] Webhook consumer that sets order.paid and saves payment_id and status.
- [ ] Fallback job that polls GET /payments/{id} for orders still pending after 15 minutes.
- [ ] Add capture(amount) and refund(amount) for partial shipments.
- [ ] Tests that mock Payment.create and find_one.
- [ ] Document Apple Pay and Google Pay enablement in your runbook.

Do you need one stage or two stages for capture? Use two stages when you must check stock or split fulfillment.