import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import EmailStr, Field

from app.models.entities import (
    CampaignStatus,
    DiscountType,
    OrderStatus,
    RefundStatus,
    StaffRole,
    TaskStatus,
)
from app.schemas.base import APIModel


class StaffResponse(APIModel):
    user_id: uuid.UUID
    email: EmailStr
    display_name: str
    role: StaffRole
    is_active: bool


class StaffInviteInput(APIModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    role: StaffRole


class UpdateStaffInput(APIModel):
    role: StaffRole | None = None
    is_active: bool | None = None


class OrderStatusInput(APIModel):
    status: OrderStatus


class CancelOrderInput(APIModel):
    reason: str = Field(min_length=3, max_length=500)


class RefundInput(APIModel):
    amount: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)


class RefundDecisionInput(APIModel):
    status: RefundStatus


class ProductInput(APIModel):
    category_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=140)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    description: str = Field(default="", max_length=1000)
    price: int = Field(gt=0)
    compare_at_price: int | None = Field(default=None, gt=0)
    tag: str | None = Field(default=None, max_length=50)
    tone: str | None = Field(default=None, max_length=30)
    image_url: str | None = Field(default=None, max_length=1000)
    is_available: bool = True
    is_featured: bool = False
    sort_order: int = 0


class ProductPatch(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=1000)
    price: int | None = Field(default=None, gt=0)
    compare_at_price: int | None = Field(default=None, gt=0)
    tag: str | None = Field(default=None, max_length=50)
    image_url: str | None = Field(default=None, max_length=1000)
    is_available: bool | None = None
    is_featured: bool | None = None
    sort_order: int | None = None


class StockAdjustmentInput(APIModel):
    quantity_delta: Decimal
    reason: str = Field(min_length=3, max_length=300)


class CouponInput(APIModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=40)
    description: str | None = Field(default=None, max_length=500)
    type: DiscountType
    value: int = Field(gt=0)
    minimum_subtotal: int = Field(default=0, ge=0)
    maximum_discount: int | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True


class CampaignInput(APIModel):
    name: str = Field(min_length=2, max_length=140)
    message: str = Field(min_length=2, max_length=1000)
    audience: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime | None = None


class TaskInput(APIModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    assigned_to: uuid.UUID | None = None
    due_at: datetime | None = None


class TaskPatch(APIModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    assigned_to: uuid.UUID | None = None
    due_at: datetime | None = None
    status: TaskStatus | None = None


class StorePatch(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=5, max_length=500)
    tax_rate_bps: int | None = Field(default=None, ge=0, le=10000)
    default_delivery_fee: int | None = Field(default=None, ge=0)
    minimum_order: int | None = Field(default=None, ge=0)
    free_delivery_threshold: int | None = Field(default=None, ge=0)
    accepts_delivery: bool | None = None
    accepts_pickup: bool | None = None
    orders_paused: bool | None = None
    opening_hours: dict[str, Any] | None = None


class DashboardMetric(APIModel):
    revenue: int
    orders: int
    average_order_value: int
    average_prep_minutes: int | None


class DashboardResponse(APIModel):
    today: DashboardMetric
    recent_orders: list[dict[str, Any]]
    top_products: list[dict[str, Any]]
    low_stock: list[dict[str, Any]]


class CampaignResponse(APIModel):
    id: uuid.UUID
    name: str
    message: str
    status: CampaignStatus
    scheduled_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
