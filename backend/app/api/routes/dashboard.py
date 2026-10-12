from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from sqlalchemy import desc, func, select

from app.api.dependencies import SessionDep, StaffDep
from app.models.entities import Ingredient, Order, OrderItem, OrderStatus

router = APIRouter(prefix="/admin/dashboard", tags=["Staff · Dashboard"])


@router.get("")
async def dashboard(session: SessionDep, _: StaffDep) -> dict[str, Any]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fulfilled = [
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.READY,
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.DELIVERED,
    ]
    revenue, count = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0), func.count(Order.id)).where(
                Order.created_at >= day_start, Order.status.in_(fulfilled)
            )
        )
    ).one()
    recent = list((await session.scalars(select(Order).order_by(Order.created_at.desc()).limit(8))).all())
    top_rows = (
        await session.execute(
            select(OrderItem.product_name, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.created_at >= day_start, Order.status != OrderStatus.CANCELLED)
            .group_by(OrderItem.product_name)
            .order_by(desc(func.sum(OrderItem.quantity)))
            .limit(5)
        )
    ).all()
    low_stock = list(
        (
            await session.scalars(
                select(Ingredient)
                .where(
                    Ingredient.is_active.is_(True), Ingredient.quantity_on_hand <= Ingredient.reorder_level
                )
                .order_by(Ingredient.quantity_on_hand)
                .limit(10)
            )
        ).all()
    )
    return {
        "today": {
            "revenue": int(revenue),
            "orders": count,
            "averageOrderValue": int(revenue) // count if count else 0,
            "averagePrepMinutes": None,
        },
        "recentOrders": [
            {
                "id": order.id,
                "orderNumber": order.order_number,
                "customerName": order.customer_name,
                "total": order.total,
                "status": order.status,
                "createdAt": order.created_at,
            }
            for order in recent
        ],
        "topProducts": [
            {"name": name, "quantity": int(quantity), "revenue": int(product_revenue)}
            for name, quantity, product_revenue in top_rows
        ],
        "lowStock": [
            {
                "id": item.id,
                "name": item.name,
                "quantityOnHand": item.quantity_on_hand,
                "reorderLevel": item.reorder_level,
                "unit": item.unit,
            }
            for item in low_stock
        ],
    }
