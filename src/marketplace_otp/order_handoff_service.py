from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .infrai_phone_client import InfraiError, InfraiPhoneClient


class SellerAsset(BaseModel):
    seller_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    title: str = Field(min_length=1)


class BuyerUpdate(BaseModel):
    order_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class BeginLoginRequest(BaseModel):
    phone: str = Field(min_length=8)
    widget_record_id: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    locale: str = "en"
    asset: SellerAsset
    update: BuyerUpdate


class LoginChallenge(BaseModel):
    challenge_id: str
    order_id: str
    next_step: str


class CompleteLoginRequest(BaseModel):
    challenge_id: str = Field(min_length=1)
    phone: str = Field(min_length=8)
    code: str = Field(min_length=1)


class OrderHandoff(BaseModel):
    handoff_id: str
    order_id: str
    seller_asset: SellerAsset
    buyer_update: BuyerUpdate
    status: str


class PendingLogin(BaseModel):
    phone: str
    asset: SellerAsset
    update: BuyerUpdate


class HandoffCoordinator:
    def __init__(self, client: InfraiPhoneClient) -> None:
        self.client = client
        self.pending: dict[str, PendingLogin] = {}
        self.handoffs: dict[str, OrderHandoff] = {}

    async def begin(self, command: BeginLoginRequest, ip: str | None) -> LoginChallenge:
        await self.client.verify_captcha(widget_record_id=command.widget_record_id, token=command.captcha_token, ip=ip)
        await self.client.send_phone_code(phone=command.phone, locale=command.locale)
        challenge_id = uuid4().hex
        self.pending[challenge_id] = PendingLogin(
            phone=command.phone,
            asset=command.asset,
            update=command.update,
        )
        return LoginChallenge(
            challenge_id=challenge_id,
            order_id=command.update.order_id,
            next_step="submit_phone_code",
        )

    async def complete(self, command: CompleteLoginRequest) -> OrderHandoff:
        pending = self.pending.get(command.challenge_id)
        if pending is None or pending.phone != command.phone:
            raise HTTPException(status_code=404, detail="Login challenge was not found")
        await self.client.verify_phone_code(phone=command.phone, code=command.code)

        handoff = OrderHandoff(
            handoff_id=f"handoff_{pending.update.order_id}",
            order_id=pending.update.order_id,
            seller_asset=pending.asset,
            buyer_update=pending.update,
            status="ready_for_buyer",
        )
        self.handoffs[pending.update.order_id] = handoff
        return handoff


def _client_error(error: InfraiError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    )


def get_coordinator(request: Request) -> HandoffCoordinator:
    return request.app.state.coordinator


Coordinator = Annotated[HandoffCoordinator, Depends(get_coordinator)]


def create_app(client: InfraiPhoneClient | None = None) -> FastAPI:
    owned_client = client is None
    phone_client = client or InfraiPhoneClient(api_key=os.environ["INFRAI_API_KEY"])

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.coordinator = HandoffCoordinator(phone_client)
        yield
        if owned_client:
            await phone_client.close()

    app = FastAPI(title="Marketplace phone OTP handoff", lifespan=lifespan)

    @app.post("/login/challenges", response_model=LoginChallenge, status_code=201)
    async def begin_login(body: BeginLoginRequest, request: Request, coordinator: Coordinator) -> Any:
        try:
            return await coordinator.begin(body, request.client.host if request.client else None)
        except InfraiError as error:
            raise _client_error(error) from error

    @app.post("/login/completions", response_model=OrderHandoff)
    async def complete_login(body: CompleteLoginRequest, coordinator: Coordinator) -> Any:
        try:
            return await coordinator.complete(body)
        except InfraiError as error:
            raise _client_error(error) from error

    return app
