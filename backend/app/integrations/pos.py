from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class POSOrder:
    external_id: str
    order_number: str


class POSAdapter(Protocol):
    async def push_order(self, order_id: str) -> POSOrder: ...

    async def update_order_status(self, external_id: str, status: str) -> None: ...


class DisabledPOSAdapter:
    """Stable integration seam for a future POS without coupling orders to a vendor."""

    async def push_order(self, order_id: str) -> POSOrder:
        del order_id
        raise RuntimeError("POS integration is disabled")

    async def update_order_status(self, external_id: str, status: str) -> None:
        del external_id, status
        raise RuntimeError("POS integration is disabled")
