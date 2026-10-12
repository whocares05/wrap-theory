import uuid
from collections import defaultdict
from datetime import UTC, datetime
from math import ceil
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from app.api.dependencies import AdminDep, SessionDep, StaffDep
from app.core.errors import bad_request, not_found
from app.models.entities import (
    Ingredient,
    InventoryMovement,
    ModifierOptionIngredient,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    ProductIngredient,
    Refund,
    RefundStatus,
)
from app.schemas.admin import CancelOrderInput, OrderStatusInput, RefundDecisionInput, RefundInput
from app.schemas.public import OrderResponse
from app.services.audit import record_audit
from app.services.orders import serialize_order

router = APIRouter(prefix="/admin/orders", tags=["Staff · Orders"])

TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


async def _order_or_404(session: SessionDep, order_id: uuid.UUID, lock: bool = False) -> Order:
    query = select(Order).where(Order.id == order_id)
    if lock:
        query = query.with_for_update()
    order = await session.scalar(query)
    if order is None:
        raise not_found("Order not found")
    return order


@router.get("")
async def list_orders(
    session: SessionDep,
    _: StaffDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
    status: OrderStatus | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> dict[str, Any]:
    filters = []
    if status:
        filters.append(Order.status == status)
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Order.order_number.ilike(term),
                Order.customer_name.ilike(term),
                Order.customer_phone.ilike(term),
            )
        )
    total = await session.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    rows = list(
        (
            await session.scalars(
                select(Order)
                .where(*filters)
                .order_by(Order.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return {
        "data": [
            {
                "id": row.id,
                "orderNumber": row.order_number,
                "customerName": row.customer_name,
                "customerPhone": row.customer_phone,
                "total": row.total,
                "status": row.status,
                "paymentStatus": row.payment_status,
                "createdAt": row.created_at,
            }
            for row in rows
        ],
        "meta": {"page": page, "pageSize": page_size, "total": total, "pages": ceil(total / page_size)},
    }


@router.get("/{order_id}", response_model=OrderResponse)
async def order_detail(order_id: uuid.UUID, session: SessionDep, _: StaffDep) -> OrderResponse:
    return await serialize_order(session, await _order_or_404(session, order_id))


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_status(
    order_id: uuid.UUID,
    payload: OrderStatusInput,
    request: Request,
    session: SessionDep,
    staff: StaffDep,
) -> OrderResponse:
    order = await _order_or_404(session, order_id, lock=True)
    previous = order.status
    if payload.status not in TRANSITIONS[previous]:
        raise bad_request(f"Order cannot move from {previous.value} to {payload.status.value}")
    if payload.status == OrderStatus.CANCELLED:
        raise bad_request("Use the cancellation endpoint so a reason is recorded and stock is restored")
    order.status = payload.status
    now = datetime.now(UTC)
    if payload.status == OrderStatus.CONFIRMED:
        order.confirmed_at = now
    if payload.status == OrderStatus.DELIVERED:
        order.delivered_at = now
        if order.payment_method == PaymentMethod.CASH_ON_DELIVERY:
            order.payment_status = PaymentStatus.PAID
            payment = await session.scalar(
                select(Payment).where(Payment.order_id == order.id).with_for_update()
            )
            if payment:
                payment.status = PaymentStatus.PAID
                payment.paid_at = now
    record_audit(
        session,
        request,
        staff,
        "order.status_changed",
        "order",
        str(order.id),
        before={"status": previous},
        after={"status": payload.status},
    )
    await session.commit()
    await session.refresh(order)
    return await serialize_order(session, order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: uuid.UUID,
    payload: CancelOrderInput,
    request: Request,
    session: SessionDep,
    staff: StaffDep,
) -> OrderResponse:
    order = await _order_or_404(session, order_id, lock=True)
    if OrderStatus.CANCELLED not in TRANSITIONS[order.status]:
        raise bad_request(f"A {order.status.value} order cannot be cancelled")
    previous = order.status
    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = payload.reason
    order.cancelled_at = datetime.now(UTC)

    already_reversed = await session.scalar(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.order_id == order.id, InventoryMovement.type == "reversal")
    )
    if not already_reversed:
        item_rows = (
            await session.execute(
                select(OrderItem.product_id, OrderItem.quantity, OrderItem.modifiers).where(
                    OrderItem.order_id == order.id
                )
            )
        ).all()
        quantities: defaultdict[uuid.UUID, int] = defaultdict(int)
        option_quantities: defaultdict[uuid.UUID, int] = defaultdict(int)
        for product_id, quantity, modifiers in item_rows:
            if product_id:
                quantities[product_id] += quantity
            for modifier in modifiers:
                option_id = modifier.get("id")
                if isinstance(option_id, str):
                    option_quantities[uuid.UUID(option_id)] += quantity
        recipes = (
            await session.execute(
                select(ProductIngredient, Ingredient)
                .join(Ingredient, Ingredient.id == ProductIngredient.ingredient_id)
                .where(ProductIngredient.product_id.in_(quantities))
                .with_for_update(of=Ingredient)
            )
        ).all()
        for recipe, ingredient in recipes:
            restored = recipe.quantity * quantities[recipe.product_id]
            ingredient.quantity_on_hand += restored
            session.add(
                InventoryMovement(
                    ingredient_id=ingredient.id,
                    order_id=order.id,
                    type="reversal",
                    quantity=restored,
                    reason=f"Cancellation of {order.order_number}",
                    actor_id=staff.user_id,
                )
            )
        if option_quantities:
            option_recipes = (
                await session.execute(
                    select(ModifierOptionIngredient, Ingredient)
                    .join(Ingredient, Ingredient.id == ModifierOptionIngredient.ingredient_id)
                    .where(ModifierOptionIngredient.option_id.in_(option_quantities))
                    .with_for_update(of=Ingredient)
                )
            ).all()
            for recipe, ingredient in option_recipes:
                restored = recipe.quantity * option_quantities[recipe.option_id]
                ingredient.quantity_on_hand += restored
                session.add(
                    InventoryMovement(
                        ingredient_id=ingredient.id,
                        order_id=order.id,
                        type="reversal",
                        quantity=restored,
                        reason=f"Cancellation of {order.order_number}",
                        actor_id=staff.user_id,
                    )
                )
    record_audit(
        session,
        request,
        staff,
        "order.cancelled",
        "order",
        str(order.id),
        before={"status": previous},
        after={"status": order.status, "reason": payload.reason},
    )
    await session.commit()
    await session.refresh(order)
    return await serialize_order(session, order)


@router.post("/{order_id}/refunds", status_code=201)
async def request_refund(
    order_id: uuid.UUID,
    payload: RefundInput,
    request: Request,
    session: SessionDep,
    staff: StaffDep,
) -> dict[str, Any]:
    order = await _order_or_404(session, order_id, lock=True)
    if order.payment_status != PaymentStatus.PAID:
        raise bad_request("Only paid orders can be refunded")
    previous_refunds = await session.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.order_id == order.id,
            Refund.status.in_([RefundStatus.REQUESTED, RefundStatus.APPROVED, RefundStatus.PROCESSED]),
        )
    )
    if int(previous_refunds or 0) + payload.amount > order.total:
        raise bad_request("Refund amount exceeds the unrefunded order total")
    payment = await session.scalar(select(Payment).where(Payment.order_id == order.id))
    refund = Refund(
        order_id=order.id,
        payment_id=payment.id if payment else None,
        amount=payload.amount,
        reason=payload.reason,
        requested_by=staff.user_id,
    )
    session.add(refund)
    await session.flush()
    record_audit(
        session,
        request,
        staff,
        "refund.requested",
        "refund",
        str(refund.id),
        after={"amount": payload.amount, "reason": payload.reason},
    )
    await session.commit()
    return {"id": refund.id, "status": refund.status, "amount": refund.amount}


@router.patch("/{order_id}/refunds/{refund_id}")
async def decide_refund(
    order_id: uuid.UUID,
    refund_id: uuid.UUID,
    payload: RefundDecisionInput,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> dict[str, Any]:
    if payload.status not in {RefundStatus.APPROVED, RefundStatus.PROCESSED, RefundStatus.REJECTED}:
        raise bad_request("Invalid refund decision")
    refund = await session.scalar(
        select(Refund).where(Refund.id == refund_id, Refund.order_id == order_id).with_for_update()
    )
    if refund is None:
        raise not_found("Refund not found")
    previous = refund.status
    refund.status = payload.status
    refund.processed_by = admin.user_id
    refund.processed_at = datetime.now(UTC)
    if payload.status == RefundStatus.PROCESSED:
        order = await _order_or_404(session, order_id, lock=True)
        order.payment_status = PaymentStatus.REFUNDED
    record_audit(
        session,
        request,
        admin,
        "refund.status_changed",
        "refund",
        str(refund.id),
        before={"status": previous},
        after={"status": refund.status},
    )
    await session.commit()
    return {"id": refund.id, "status": refund.status, "amount": refund.amount}
