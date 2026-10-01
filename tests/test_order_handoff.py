from __future__ import annotations

import json

import httpx
import pytest

from marketplace_otp.infrai_phone_client import InfraiPhoneClient
from marketplace_otp.order_handoff_service import (
    BeginLoginRequest,
    BuyerUpdate,
    CompleteLoginRequest,
    HandoffCoordinator,
    SellerAsset,
)


@pytest.mark.asyncio
async def test_verified_buyer_receives_seller_asset_and_update() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "data": {"accepted": True}, "error": None})

    client = InfraiPhoneClient(
        api_key="test-key",
        transport=httpx.MockTransport(respond),
    )
    coordinator = HandoffCoordinator(client)
    begin = await coordinator.begin(
        BeginLoginRequest(
            phone="+14155550123",
            widget_record_id="widget_test",
            captcha_token="browser-proof",
            asset=SellerAsset(seller_id="seller_42", sku="CAM-7", title="Rangefinder camera"),
            update=BuyerUpdate(order_id="order_901", message="Packed and ready at counter 3"),
        ),
        ip="203.0.113.8",
    )
    handoff = await coordinator.complete(
        CompleteLoginRequest(challenge_id=begin.challenge_id, phone="+14155550123", code="482913")
    )

    assert [path for path, _ in calls] == [
        "/v1/captcha/verify",
        "/v1/auth/phone/send_code",
        "/v1/auth/phone/verify",
    ]
    assert calls[0][1] == {"widget_record_id": "widget_test", "token": "browser-proof", "ip": "203.0.113.8", "action": "buyer_login"}
    assert calls[2][1] == {"phone": "+14155550123", "code": "482913", "login": True}
    assert handoff.handoff_id == "handoff_order_901"
    assert handoff.status == "ready_for_buyer"
    assert handoff.seller_asset.sku == "CAM-7"
    assert handoff.buyer_update.message == "Packed and ready at counter 3"
    await client.close()
