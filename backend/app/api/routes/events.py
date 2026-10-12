import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.dependencies import StaffDep
from app.db.session import Database
from app.models.entities import Order

router = APIRouter(prefix="/admin/events", tags=["Staff · Live updates"])


@router.get("/orders")
async def order_events(request: Request, _: StaffDep) -> StreamingResponse:
    database: Database = request.app.state.database

    async def stream() -> AsyncIterator[str]:
        cursor = datetime.now(UTC)
        yield "event: connected\ndata: {}\n\n"
        while not await request.is_disconnected():
            async with database.sessions() as session:
                changed = list(
                    (
                        await session.scalars(
                            select(Order)
                            .where(Order.updated_at > cursor)
                            .order_by(Order.updated_at)
                            .limit(100)
                        )
                    ).all()
                )
            if changed:
                cursor = max(order.updated_at for order in changed)
                for order in changed:
                    payload = json.dumps(
                        {
                            "id": str(order.id),
                            "orderNumber": order.order_number,
                            "status": order.status.value,
                            "paymentStatus": order.payment_status.value,
                            "updatedAt": order.updated_at.isoformat(),
                        }
                    )
                    yield f"event: order.updated\ndata: {payload}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
