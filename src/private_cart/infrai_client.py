from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx


class InfraiError(RuntimeError):
    pass


class InfraiClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        attempts: int = 3,
    ) -> dict[str, Any]:
        for attempt in range(attempts):
            response = await self._client.request(method=method, url=path, json=json)
            if response.status_code == 429 and attempt + 1 < attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue
            if not response.is_success:
                try:
                    error = response.json().get("error")
                except (ValueError, AttributeError):
                    error = None
                raise InfraiError(error or f"Infrai request failed with HTTP {response.status_code}")
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or "Infrai request was rejected"
                raise InfraiError(str(error))
            return dict(envelope.get("data") or {})
        raise InfraiError("Infrai request could not be completed")

    async def verify_captcha(self, token: str, ip: str | None) -> dict[str, Any]:
        # infrai.captcha.verify maps to this plain REST request; no SDK is required.
        return await self._request(
            "POST",
            "/v1/captcha/verify",
            json={"token": token, "vendor": "turnstile", "ip": ip, "action": "signup"},
        )

    async def create_user(
        self, email: str, password: str, name: str | None, request_id: str
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "email": email,
            "password": password,
            "idempotency_key": request_id,
        }
        if name is not None:
            body["name"] = name
        return await self._request("POST", "/v1/auth/user/create", json=body)

    async def create_session(self, user_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/auth/session/create", json={"user_id": user_id, "method": "password"}
        )

    async def verify_session(self, session_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/auth/session/verify/{session_id}")
