import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class StrEnum(enum.StrEnum):
    pass


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class StaffRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    CASH_ON_DELIVERY = "cash_on_delivery"
    SAFEPAY = "safepay"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class FulfillmentType(StrEnum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class DiscountType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class RefundStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSED = "processed"
    REJECTED = "rejected"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class StaffProfile(TimestampMixin, Base):
    __tablename__ = "staff_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[StaffRole] = mapped_column(
        Enum(StaffRole, name="staff_role", values_callable=enum_values), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StoreSettings(TimestampMixin, Base):
    __tablename__ = "store_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, server_default="Lahore")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Asia/Karachi")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="PKR")
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    default_delivery_fee: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15000")
    minimum_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50000")
    free_delivery_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="250000")
    accepts_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    accepts_pickup: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    orders_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    opening_hours: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DeliveryZone(TimestampMixin, Base):
    __tablename__ = "delivery_zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    areas: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    delivery_fee: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_order: Mapped[int | None] = mapped_column(Integer)
    free_delivery_threshold: Mapped[int | None] = mapped_column(Integer)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="45")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_category", "category_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    compare_at_price: Mapped[int | None] = mapped_column(Integer)
    tag: Mapped[str | None] = mapped_column(String(50))
    tone: Mapped[str | None] = mapped_column(String(30))
    image_url: Mapped[str | None] = mapped_column(Text)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ModifierGroup(TimestampMixin, Base):
    __tablename__ = "modifier_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_selections: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_selections: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ModifierOption(TimestampMixin, Base):
    __tablename__ = "modifier_options"
    __table_args__ = (Index("ix_modifier_options_group", "group_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modifier_groups.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_delta: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ProductModifierGroup(Base):
    __tablename__ = "product_modifier_groups"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modifier_groups.id", ondelete="CASCADE"), primary_key=True
    )


class Ingredient(TimestampMixin, Base):
    __tablename__ = "ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sku: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, server_default="0")
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class ProductIngredient(Base):
    __tablename__ = "product_ingredients"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"), primary_key=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)


class ModifierOptionIngredient(Base):
    __tablename__ = "modifier_option_ingredients"

    option_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modifier_options.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"), primary_key=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_last_order", "last_order_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lifetime_value: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discount_type", values_callable=enum_values), nullable=False
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_subtotal: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    maximum_discount: Mapped[int | None] = mapped_column(Integer)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_customer", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    public_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=enum_values),
        nullable=False,
        server_default="pending",
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=enum_values)
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=enum_values),
        nullable=False,
        server_default="pending",
    )
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        Enum(FulfillmentType, name="fulfillment_type", values_callable=enum_values),
        nullable=False,
        server_default="delivery",
    )
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(320))
    delivery_address: Mapped[str | None] = mapped_column(Text)
    delivery_area: Mapped[str | None] = mapped_column(String(100))
    delivery_instructions: Mapped[str | None] = mapped_column(Text)
    delivery_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("delivery_zones.id", ondelete="SET NULL")
    )
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tax_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    delivery_fee: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    coupon_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("coupons.id", ondelete="SET NULL"))
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order", "order_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    product_name: Mapped[str] = mapped_column(String(140), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    modifier_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    line_total: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    modifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_order", "order_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(200), unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=enum_values, create_type=False),
        nullable=False,
        server_default="pending",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coupon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coupons.id", ondelete="RESTRICT"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (Index("ix_inventory_movements_ingredient", "ingredient_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Refund(TimestampMixin, Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status", values_callable=enum_values),
        nullable=False,
        server_default="requested",
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    processed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, server_default="whatsapp")
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status", values_callable=enum_values),
        nullable=False,
        server_default="draft",
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_pending", "status", "next_attempt_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    template: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status", values_callable=enum_values),
        nullable=False,
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeamTask(TimestampMixin, Base):
    __tablename__ = "team_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=enum_values),
        nullable=False,
        server_default="todo",
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_email: Mapped[str | None] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100))
    before: Mapped[Any | None] = mapped_column(JSONB)
    after: Mapped[Any | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
