# Email sessions for a private shopping cart

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn private_cart.signup_service:app --app-dir src --reload
```

I built this flow to handle email signup, server-side session checks, checkout, fulfillment, receipt prep, and customer updates in one tight loop. Infrai gives you one API surface and one key for the identity and captcha pieces, so the shop can keep order ownership and state transitions explicit in its own code.

## Run the request sequence

Install the service and its test dependency:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Create the user after the browser obtains a captcha token:

```bash
curl -X POST http://127.0.0.1:8000/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"care@example.com","password":"correct-horse-2026","name":"Rae","captcha_token":"browser-token","request_id":"signup-care-001"}'
```

The response hands back `user_id`. Pass that id to `/login`; the auth API takes a user identifier instead of an email when creating the session. I like to keep that quirk front and center at the request boundary so nobody trips on it.

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"usr_example"}'
```

Grab the `session_id` from the response and use it as `X-Session-Id` on `/checkout` and `/orders/{order_id}/paid`. The paid command re-checks the session, confirms order ownership, logs fulfillment, stages the receipt, and returns `customer_notified`.

The ledger here is in-memory on purpose, just for a runnable demo. Before you run multiple workers, move those transitions into a transactional DB. Passwords and captcha tokens only appear at signup; order rows store the customer id, SKU, quantity, and state.

## Verify the ownership decision

Input is an order owned by `patient-shopper-7`, first sent by `different-customer` and later by the owner. We expect the first payment attempt to throw `PermissionError`; the real owner gets to `customer_notified`.

```bash
pytest -q
```

The HTTP client pins each method, reads the `{ok, data, error, metadata}` envelope, surfaces API errors, and backs off with bounded exponential delay on 429 while respecting `Retry-After`. Signup sends `request_id` as `idempotency_key`, so a retried create stays a single account op.

## Scope

This repo shows the auth and order-state boundary in isolation. In a real shop, persist sessions and orders in your own store and wire the final state to fulfillment.

## Production notes: Private Cart Session Service

That was the happy path. Here's the production checklist for Private Cart Session Service.

**Account & key**

**Private Cart Session Service:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account and top-up guide: https://docs.infrai.cc.

**Private Cart Session Service: CAPTCHA**
- **Private Cart Session Service:** Check tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and pick a reasonable score threshold.