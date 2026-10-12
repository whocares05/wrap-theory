import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import EmailStr, Field, field_validator

from app.models.entities import FulfillmentType, OrderStatus, PaymentMethod, PaymentStatus
from app.schemas.base import APIModel


class StoreResponse(APIModel):
    name: str
    phone: str
    email: str | None
    address: str
    city: str
    timezone: str
    currency: str
    tax_rate_bps: int
    default_delivery_fee: int
    minimum_order: int
    free_delivery_threshold: int
    accepts_delivery: bool
    accepts_pickup: bool
    orders_paused: bool
    opening_hours: dict[str, Any]


class DeliveryZoneResponse(APIModel):
    id: uuid.UUID
    name: str
    areas: list[str]
    delivery_fee: int
    minimum_order: int | None
    free_delivery_threshold: int | None
    estimated_minutes: int


class ModifierOptionResponse(APIModel):
    id: uuid.UUID
    name: str
    price_delta: int


class ModifierGroupResponse(APIModel):
    id: uuid.UUID
    name: str
    min_selections: int
    max_selections: int
    options: list[ModifierOptionResponse]


class ProductResponse(APIModel):
    id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    slug: str
    description: str
    price: int
    compare_at_price: int | None
    tag: str | None
    tone: str | None
    image_url: str | None
    is_featured: bool
    modifier_groups: list[ModifierGroupResponse] = []


class CategoryResponse(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    products: list[ProductResponse]


class MenuResponse(APIModel):
    categories: list[CategoryResponse]


class OrderItemInput(APIModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=20)
    modifier_option_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=300)


class CustomerInput(APIModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=30)
    email: EmailStr | None = None
    marketing_consent: bool = False


class CreateOrderInput(APIModel):
    customer: CustomerInput
    items: list[OrderItemInput] = Field(min_length=1, max_length=30)
    fulfillment_type: FulfillmentType = FulfillmentType.DELIVERY
    delivery_zone_id: uuid.UUID | None = None
    delivery_area: str | None = Field(default=None, max_length=100)
    delivery_address: str | None = Field(default=None, max_length=500)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    coupon_code: str | None = Field(default=None, max_length=40)
    payment_method: PaymentMethod = PaymentMethod.CASH_ON_DELIVERY
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("delivery_address")
    @classmethod
    def address_not_blank(cls, value: str | None) -> str | None:
        if value is not None and len(value.strip()) < 8:
            raise ValueError("Delivery address must be at least 8 characters")
        return value


class OrderLineResponse(APIModel):
    product_name: str
    quantity: int
    unit_price: int
    modifier_total: int
    line_total: int
    modifiers: list[dict[str, Any]]


class OrderResponse(APIModel):
    id: uuid.UUID
    order_number: str
    public_token: uuid.UUID
    status: OrderStatus
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    fulfillment_type: FulfillmentType
    customer_name: str
    customer_phone: str
    delivery_address: str | None
    delivery_area: str | None
    subtotal: int
    discount_total: int
    tax_total: int
    delivery_fee: int
    total: int
    coupon_code: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderLineResponse]


class CouponQuoteInput(APIModel):
    code: str = Field(min_length=2, max_length=40)
    subtotal: int = Field(gt=0)


class CouponQuoteResponse(APIModel):
    valid: Literal[True] = True
    code: str
    discount: int
