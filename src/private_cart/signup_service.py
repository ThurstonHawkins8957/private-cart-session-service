from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from .infrai_client import InfraiClient, InfraiError
from .order_workflow import OrderLedger


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    name: str | None = None
    captcha_token: str
    request_id: str


class LoginRequest(BaseModel):
    user_id: str


class CheckoutRequest(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=20)


class OrderResult(BaseModel):
    order_id: str
    state: str


app = FastAPI(title="Private cart session service")
ledger = OrderLedger()


def client() -> InfraiClient:
    return InfraiClient()


@app.post("/signup")
async def signup(body: SignupRequest, request: Request) -> dict[str, str]:
    api = client()
    try:
        await api.verify_captcha(body.captcha_token, request.client.host if request.client else None)
        user = await api.create_user(body.email, body.password, body.name, body.request_id)
        return {"user_id": str(user["id"])}
    except (InfraiError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await api.close()


@app.post("/login")
async def login(body: LoginRequest) -> dict[str, str]:
    api = client()
    try:
        session = await api.create_session(body.user_id)
        return {"session_id": str(session["id"])}
    except (InfraiError, KeyError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    finally:
        await api.close()


@app.post("/checkout", response_model=OrderResult)
async def checkout(body: CheckoutRequest, x_session_id: str = Header()) -> OrderResult:
    api = client()
    try:
        session = await api.verify_session(x_session_id)
        customer_id = str(session["user_id"])
        order = ledger.checkout(customer_id, body.sku, body.quantity)
        return OrderResult(order_id=order.order_id, state=order.state)
    except (InfraiError, KeyError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    finally:
        await api.close()


@app.post("/orders/{order_id}/paid", response_model=OrderResult)
async def paid(order_id: str, x_session_id: str = Header()) -> OrderResult:
    api = client()
    try:
        session = await api.verify_session(x_session_id)
        order = ledger.mark_paid(order_id, str(session["user_id"]))
        order = ledger.fulfill_and_notify(order.order_id)
        return OrderResult(order_id=order.order_id, state=order.state)
    except (InfraiError, KeyError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        await api.close()
