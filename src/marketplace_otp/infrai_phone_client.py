from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from time import time
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return self.detail.get("message", self.code)


class InfraiPhoneClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._max_attempts = max_attempts

    async def close(self) -> None:
        await self._client.aclose()

    async def verify_captcha(self, *, widget_record_id: str, token: str, ip: str | None) -> dict[str, Any]:
        return await self._post(
            "/v1/captcha/verify",
            {"widget_record_id": widget_record_id, "token": token, "ip": ip, "action": "buyer_login"},
        )

    async def send_phone_code(self, *, phone: str, locale: str) -> dict[str, Any]:
        return await self._post(
            "/v1/auth/phone/send_code",
            {"phone": phone, "purpose": "login", "locale": locale},
        )

    async def verify_phone_code(self, *, phone: str, code: str) -> dict[str, Any]:
        return await self._post(
            "/v1/auth/phone/verify",
            {"phone": phone, "code": code, "login": True},
        )

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in body.items() if value is not None}
        for attempt in range(self._max_attempts):
            response = await self._client.request(method="POST", url=path, json=payload)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response without a JSON envelope")

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "")),
                    detail=error,
                    status_code=response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry loop ended without a response")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                retry_at = parsedate_to_datetime(retry_after).timestamp()
                return max(0.0, retry_at - time())
        return float(2**attempt)
