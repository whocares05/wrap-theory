from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import cast, func, select
from sqlalchemy.types import Date

from app.api.dependencies import SessionDep, StaffDep
from app.models.entities import Order, OrderItem, OrderStatus

router = APIRouter(prefix="/admin/reports", tags=["Staff · Reports"])


@router.get("/sales")
async def sales_report(
    session: SessionDep,
    _: StaffDep,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> dict[str, Any]:
    if (date_to - date_from).days > 366:
        from app.core.errors import bad_request

        raise bad_request("Report range cannot exceed 366 days")
    start = datetime.combine(date_from, time.min, UTC)
    end = datetime.combine(date_to + timedelta(days=1), time.min, UTC)
    valid_statuses = [
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.READY,
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.DELIVERED,
    ]
    daily = (
        await session.execute(
            select(
                cast(Order.created_at, Date).label("day"),
                func.count(Order.id),
                func.sum(Order.subtotal),
                func.sum(Order.discount_total),
                func.sum(Order.tax_total),
                func.sum(Order.delivery_fee),
                func.sum(Order.total),
            )
            .where(Order.created_at >= start, Order.created_at < end, Order.status.in_(valid_statuses))
            .group_by("day")
            .order_by("day")
        )
    ).all()
    top_products = (
        await session.execute(
            select(OrderItem.product_name, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.created_at >= start, Order.created_at < end, Order.status.in_(valid_statuses))
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(20)
        )
    ).all()
    return {
        "daily": [
            {
                "date": day,
                "orders": count,
                "subtotal": int(subtotal or 0),
                "discounts": int(discounts or 0),
                "tax": int(tax or 0),
                "deliveryFees": int(fees or 0),
                "revenue": int(revenue or 0),
            }
            for day, count, subtotal, discounts, tax, fees, revenue in daily
        ],
        "topProducts": [
            {"name": name, "quantity": int(quantity), "revenue": int(revenue)}
            for name, quantity, revenue in top_products
        ],
    }
