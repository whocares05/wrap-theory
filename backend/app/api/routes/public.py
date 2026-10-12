import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query
from sqlalchemy import func, select

from app.api.dependencies import SessionDep, SettingsDep
from app.core.errors import bad_request, conflict
from app.lib.money import calculate_discount
from app.models.entities import Coupon, DeliveryZone, StoreSettings
from app.schemas.public import (
    CouponQuoteInput,
    CouponQuoteResponse,
    CreateOrderInput,
    DeliveryZoneResponse,
    MenuResponse,
    OrderResponse,
    StoreResponse,
)
from app.services.catalog import get_public_menu
from app.services.orders import _coupon_is_valid, create_order, get_public_order

router = APIRouter(prefix="/public", tags=["Storefront"])


@router.get("/store", response_model=StoreResponse)
async def store(session: SessionDep) -> StoreSettings:
    settings = await session.scalar(select(StoreSettings).limit(1))
    if settings is None:
        raise conflict("Store configuration has not been initialized")
    return settings


@router.get("/delivery-zones", response_model=list[DeliveryZoneResponse])
async def delivery_zones(session: SessionDep) -> list[DeliveryZone]:
    return list(
        (
            await session.scalars(
                select(DeliveryZone).where(DeliveryZone.is_active.is_(True)).order_by(DeliveryZone.name)
            )
        ).all()
    )


@router.get("/menu", response_model=MenuResponse)
async def menu(session: SessionDep) -> MenuResponse:
    return await get_public_menu(session)


@router.post("/coupons/quote", response_model=CouponQuoteResponse)
async def quote_coupon(payload: CouponQuoteInput, session: SessionDep) -> CouponQuoteResponse:
    coupon = await session.scalar(select(Coupon).where(func.upper(Coupon.code) == payload.code.upper()))
    if coupon is None:
        raise bad_request("Coupon not found")
    _coupon_is_valid(coupon, payload.subtotal, datetime.now(UTC))
    return CouponQuoteResponse(
        code=coupon.code,
        discount=calculate_discount(payload.subtotal, coupon.type, coupon.value, coupon.maximum_discount),
    )


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def place_order(
    payload: CreateOrderInput,
    session: SessionDep,
    settings: SettingsDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=100)],
) -> OrderResponse:
    return await create_order(session, payload, idempotency_key, settings)


@router.get("/orders/{order_number}", response_model=OrderResponse)
async def track_order(
    order_number: str,
    session: SessionDep,
    token: Annotated[uuid.UUID, Query()],
) -> OrderResponse:
    return await get_public_order(session, order_number, token)
