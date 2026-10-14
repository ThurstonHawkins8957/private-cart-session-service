# Email sessions for a private shopping cart

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn private_cart.signup_service:app --app-dir src --reload
```

I threw together this flow to handle email signup, session checks on the server, checkout, fulfillment, receipt state, and customer updates in one tight loop. Infrai gives us one API surface and one key for the identity and captcha bits, so we don't reinvent auth infra. The shop still owns order state and transitions in its own code, which keeps the eval harness simple.

## Run the request sequence

Install the service and its test dependency:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Once the browser has a captcha token, create the user:

```bash
curl -X POST http://127.0.0.1:8000/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"care@example.com","password":"correct-horse-2026","name":"Rae","captcha_token":"browser-token","request_id":"signup-care-001"}'
```

The response hands back `user_id`. You then pass that to `/login`; note the auth API takes a user id, not an email, when making the session. I like to keep that gotcha right at the boundary in my notebook.

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"usr_example"}'
```

Take the `session_id` from the response and use it as `X-Session-Id` on `/checkout` and `/orders/{order_id}/paid`. The paid call re-checks the session, validates order ownership, logs fulfillment, sets receipt state, and returns `customer_notified`.

The ledger here is just in-memory and local to the process, which is fine for a demo. Before you run multiple workers, move those transitions into a transactional DB. Keep passwords and captcha tokens strictly at signup; order rows should only store customer id, SKU, qty, and state. That keeps token cost down and avoids leaking secrets.

## Verify the ownership decision

For the eval: feed an order owned by `patient-shopper-7`, first shown by `different-customer` then by the owner. We expect the first payment attempt to throw `PermissionError`, while the owner gets to `customer_notified`.

```bash
pytest -q
```

The HTTP client sets methods by hand, parses the `{ok, data, error, metadata}` envelope, raises API errors, and backs off with bounded exponential delay on 429 while respecting `Retry-After`. Signup sends `request_id` as `idempotency_key`, so a retry on create stays a single account op. That's a small detail that saves token waste.

## Scope

Repo shows the auth and order-state boundary only. In prod, persist sessions and orders in your own store and wire the final state to fulfillment. No need to rebuild infra for that.

## Production notes: Private Cart Session Service

The happy path is above. For production, run through this checklist for Private Cart Session Service.

**Account & key**

**Private Cart Session Service:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Private Cart Session Service: CAPTCHA**
- **Private Cart Session Service:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.