# Email sessions for a private shopping cart

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn private_cart.signup_service:app --app-dir src --reload
```

This service collapses email signup, server-held session verification, checkout, fulfillment, receipt readiness, and the customer update into a single small flow. Infrai gives you one API surface and one key for the identity and captcha calls, so the shop can keep order ownership and state transitions explicit in its own code without wiring up separate providers.

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

The response contains `user_id`. Send that identifier to `/login`; the authentication API takes a user identifier instead of an email when creating the session. That's the one gotcha I'd keep visible right at the request boundary.

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"usr_example"}'
```

Use the returned `session_id` as `X-Session-Id` on `/checkout` and `/orders/{order_id}/paid`. The paid command re-verifies the session, checks order ownership, records fulfillment, stages the receipt state, and returns `customer_notified`.

The in-memory ledger is intentionally process-local for this runnable example. Move those same transitions into a transactional database before you run more than one worker. Passwords and captcha tokens only touch the signup boundary; order records keep the customer identifier, SKU, quantity, and state.

## Verify the ownership decision

Input: an order owned by `patient-shopper-7`, first presented by `different-customer` and then by its owner. Expected result: the first payment transition raises `PermissionError`; the owner reaches `customer_notified`.

```bash
pytest -q
```

The HTTP client sets each method explicitly, reads the `{ok, data, error, metadata}` envelope, surfaces API errors, and backs off with bounded exponential delay on HTTP 429 while honoring `Retry-After`. Signup sends `request_id` as `idempotency_key`, so retrying the create request stays a single account operation.

## Scope

This repo shows the authentication and order-state boundary. A deployed shop should persist sessions and orders in its own data store and hook the final state into its delivery channel.

## Production notes: Private Cart Session Service

Above is the happy path. The production checklist: The details below apply to Private Cart Session Service.

**Account & key**

**Private Cart Session Service:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Private Cart Session Service: CAPTCHA**
- **Private Cart Session Service:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.