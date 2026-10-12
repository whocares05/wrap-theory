import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import bad_request, conflict, not_found
from app.lib.money import calculate_delivery_fee, calculate_discount, calculate_tax
from app.lib.phone import normalize_pakistani_phone
from app.models.entities import (
    Coupon,
    CouponRedemption,
    Customer,
    DeliveryZone,
    FulfillmentType,
    Ingredient,
    InventoryMovement,
    ModifierGroup,
    ModifierOption,
    ModifierOptionIngredient,
    Notification,
    NotificationStatus,
    Order,
    OrderItem,
    Payment,
    PaymentMethod,
    Product,
    ProductIngredient,
    ProductModifierGroup,
    StoreSettings,
)
from app.schemas.public import CreateOrderInput, OrderLineResponse, OrderResponse


class LineSnapshot(TypedDict):
    product: Product
    quantity: int
    modifier_total: int
    line_total: int
    notes: str | None
    modifiers: list[dict[str, object]]


def _coupon_is_valid(coupon: Coupon, subtotal: int, now: datetime) -> None:
    if not coupon.is_active:
        raise bad_request("This coupon is inactive")
    if coupon.starts_at and coupon.starts_at > now:
        raise bad_request("This coupon is not active yet")
    if coupon.ends_at and coupon.ends_at < now:
        raise bad_request("This coupon has expired")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise bad_request("This coupon has reached its usage limit")
    if subtotal < coupon.minimum_subtotal:
        raise bad_request(f"This coupon requires a minimum subtotal of Rs. {coupon.minimum_subtotal // 100}")


async def serialize_order(session: AsyncSession, order: Order) -> OrderResponse:
    items = (
        await session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.created_at)
        )
    ).all()
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        public_token=order.public_token,
        status=order.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        fulfillment_type=order.fulfillment_type,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        delivery_address=order.delivery_address,
        delivery_area=order.delivery_area,
        subtotal=order.subtotal,
        discount_total=order.discount_total,
        tax_total=order.tax_total,
        delivery_fee=order.delivery_fee,
        total=order.total,
        coupon_code=order.coupon_code,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[OrderLineResponse.model_validate(item) for item in items],
    )


async def create_order(
    session: AsyncSession,
    payload: CreateOrderInput,
    idempotency_key: str,
    settings: Settings,
) -> OrderResponse:
    existing = await session.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
    if existing:
        return await serialize_order(session, existing)

    if payload.payment_method == PaymentMethod.SAFEPAY and not settings.safepay_enabled:
        raise bad_request("Online payment is not currently available")
    if payload.payment_method != PaymentMethod.CASH_ON_DELIVERY:
        raise bad_request("Cash on delivery is the only enabled payment method")

    async with session.begin_nested():
        await session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:idempotency_key, 0))"),
            {"idempotency_key": idempotency_key},
        )
        existing = await session.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing:
            return await serialize_order(session, existing)

        store = await session.scalar(select(StoreSettings).limit(1).with_for_update())
        if store is None:
            raise conflict("Store configuration has not been initialized")
        if store.orders_paused:
            raise conflict("Online ordering is temporarily paused")

        zone: DeliveryZone | None = None
        if payload.fulfillment_type == FulfillmentType.DELIVERY:
            if not store.accepts_delivery:
                raise bad_request("Delivery is not currently available")
            if not payload.delivery_address or not payload.delivery_zone_id or not payload.delivery_area:
                raise bad_request("Delivery zone, area, and address are required")
            zone = await session.scalar(
                select(DeliveryZone)
                .where(DeliveryZone.id == payload.delivery_zone_id, DeliveryZone.is_active.is_(True))
                .with_for_update()
            )
            if zone is None:
                raise bad_request("The selected delivery zone is unavailable")
            if payload.delivery_area.casefold() not in {area.casefold() for area in zone.areas}:
                raise bad_request("The selected area is not in this delivery zone")
        elif not store.accepts_pickup:
            raise bad_request("Pickup is not currently available")

        product_ids = {item.product_id for item in payload.items}
        products = {
            product.id: product
            for product in (
                await session.scalars(
                    select(Product)
                    .where(Product.id.in_(product_ids), Product.is_available.is_(True))
                    .with_for_update()
                )
            ).all()
        }
        if len(products) != len(product_ids):
            raise bad_request("One or more selected products are unavailable")

        requested_modifier_ids = {option for item in payload.items for option in item.modifier_option_ids}
        option_rows: dict[uuid.UUID, tuple[ModifierOption, ModifierGroup]] = {}
        if requested_modifier_ids:
            rows = (
                await session.execute(
                    select(ModifierOption, ModifierGroup)
                    .join(ModifierGroup, ModifierGroup.id == ModifierOption.group_id)
                    .where(
                        ModifierOption.id.in_(requested_modifier_ids),
                        ModifierOption.is_available.is_(True),
                        ModifierGroup.is_active.is_(True),
                    )
                )
            ).all()
            option_rows = {option.id: (option, group) for option, group in rows}
            if len(option_rows) != len(requested_modifier_ids):
                raise bad_request("One or more selected options are unavailable")

        allowed_rows = (
            await session.execute(
                select(ProductModifierGroup.product_id, ModifierGroup)
                .join(ModifierGroup, ModifierGroup.id == ProductModifierGroup.group_id)
                .where(ProductModifierGroup.product_id.in_(product_ids), ModifierGroup.is_active.is_(True))
            )
        ).all()
        allowed_groups = {(product_id, group.id) for product_id, group in allowed_rows}
        groups_by_product: defaultdict[uuid.UUID, list[ModifierGroup]] = defaultdict(list)
        for product_id, group in allowed_rows:
            groups_by_product[product_id].append(group)

        line_snapshots: list[LineSnapshot] = []
        subtotal = 0
        product_quantities: defaultdict[uuid.UUID, int] = defaultdict(int)
        option_quantities: defaultdict[uuid.UUID, int] = defaultdict(int)
        for item in payload.items:
            product = products[item.product_id]
            if len(item.modifier_option_ids) != len(set(item.modifier_option_ids)):
                raise bad_request("A modifier option cannot be selected more than once")
            selections: defaultdict[uuid.UUID, list[tuple[ModifierOption, ModifierGroup]]] = defaultdict(list)
            for option_id in item.modifier_option_ids:
                option, group = option_rows[option_id]
                if (product.id, group.id) not in allowed_groups:
                    raise bad_request(f"{option.name} is not valid for {product.name}")
                selections[group.id].append((option, group))
            for group in groups_by_product[product.id]:
                selected = selections[group.id]
                if len(selected) < group.min_selections or len(selected) > group.max_selections:
                    raise bad_request(
                        f"Choose between {group.min_selections} and {group.max_selections} {group.name} options"
                    )
            modifier_total = sum(
                option.price_delta for selected in selections.values() for option, _ in selected
            )
            line_total = (product.price + modifier_total) * item.quantity
            subtotal += line_total
            product_quantities[product.id] += item.quantity
            for option_id in item.modifier_option_ids:
                option_quantities[option_id] += item.quantity
            line_snapshots.append(
                {
                    "product": product,
                    "quantity": item.quantity,
                    "modifier_total": modifier_total,
                    "line_total": line_total,
                    "notes": item.notes,
                    "modifiers": [
                        {
                            "id": str(option.id),
                            "group": group.name,
                            "name": option.name,
                            "priceDelta": option.price_delta,
                        }
                        for selected in selections.values()
                        for option, group in selected
                    ],
                }
            )

        minimum_order = zone.minimum_order if zone and zone.minimum_order is not None else store.minimum_order
        if subtotal < minimum_order:
            raise bad_request(f"Minimum order is Rs. {minimum_order // 100}")

        coupon: Coupon | None = None
        discount_total = 0
        if payload.coupon_code:
            coupon = await session.scalar(
                select(Coupon).where(func.upper(Coupon.code) == payload.coupon_code.upper()).with_for_update()
            )
            if coupon is None:
                raise bad_request("Coupon not found")
            _coupon_is_valid(coupon, subtotal, datetime.now(UTC))
            discount_total = calculate_discount(subtotal, coupon.type, coupon.value, coupon.maximum_discount)

        discounted_subtotal = subtotal - discount_total
        tax_total = calculate_tax(discounted_subtotal, store.tax_rate_bps)
        base_delivery_fee = zone.delivery_fee if zone else 0
        free_threshold = zone.free_delivery_threshold if zone else None
        delivery_fee = (
            calculate_delivery_fee(discounted_subtotal, base_delivery_fee, free_threshold)
            if payload.fulfillment_type == FulfillmentType.DELIVERY
            else 0
        )
        total = discounted_subtotal + tax_total + delivery_fee
        phone = normalize_pakistani_phone(payload.customer.phone)

        customer = await session.scalar(select(Customer).where(Customer.phone == phone).with_for_update())
        if customer is None:
            customer = Customer(
                name=payload.customer.name,
                phone=phone,
                email=str(payload.customer.email) if payload.customer.email else None,
                marketing_consent=payload.customer.marketing_consent,
            )
            session.add(customer)
            await session.flush()
        else:
            customer.name = payload.customer.name
            customer.email = str(payload.customer.email) if payload.customer.email else customer.email
            customer.marketing_consent = customer.marketing_consent or payload.customer.marketing_consent

        sequence_value = await session.scalar(select(text("nextval('order_number_seq')")))
        order = Order(
            order_number=f"WT-{int(sequence_value):06d}",
            idempotency_key=idempotency_key,
            customer_id=customer.id,
            payment_method=payload.payment_method,
            fulfillment_type=payload.fulfillment_type,
            customer_name=payload.customer.name,
            customer_phone=phone,
            customer_email=str(payload.customer.email) if payload.customer.email else None,
            delivery_address=payload.delivery_address,
            delivery_area=payload.delivery_area,
            delivery_instructions=payload.delivery_instructions,
            delivery_zone_id=zone.id if zone else None,
            subtotal=subtotal,
            discount_total=discount_total,
            tax_total=tax_total,
            delivery_fee=delivery_fee,
            total=total,
            coupon_id=coupon.id if coupon else None,
            coupon_code=coupon.code if coupon else None,
            notes=payload.notes,
        )
        session.add(order)
        await session.flush()

        for line in line_snapshots:
            product = line["product"]
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=line["quantity"],
                    unit_price=product.price,
                    modifier_total=line["modifier_total"],
                    line_total=line["line_total"],
                    notes=line["notes"],
                    modifiers=line["modifiers"],
                )
            )

        recipe_rows = (
            await session.execute(
                select(ProductIngredient, Ingredient)
                .join(Ingredient, Ingredient.id == ProductIngredient.ingredient_id)
                .where(ProductIngredient.product_id.in_(product_ids))
                .with_for_update(of=Ingredient)
            )
        ).all()
        consumption: defaultdict[uuid.UUID, Decimal] = defaultdict(Decimal)
        ingredient_by_id: dict[uuid.UUID, Ingredient] = {}
        for recipe, ingredient in recipe_rows:
            consumption[ingredient.id] += recipe.quantity * product_quantities[recipe.product_id]
            ingredient_by_id[ingredient.id] = ingredient
        if option_quantities:
            option_recipe_rows = (
                await session.execute(
                    select(ModifierOptionIngredient, Ingredient)
                    .join(Ingredient, Ingredient.id == ModifierOptionIngredient.ingredient_id)
                    .where(ModifierOptionIngredient.option_id.in_(option_quantities))
                    .with_for_update(of=Ingredient)
                )
            ).all()
            for recipe, ingredient in option_recipe_rows:
                consumption[ingredient.id] += recipe.quantity * option_quantities[recipe.option_id]
                ingredient_by_id[ingredient.id] = ingredient
        for ingredient_id, quantity in consumption.items():
            ingredient = ingredient_by_id[ingredient_id]
            if ingredient.quantity_on_hand < quantity:
                raise conflict(f"{ingredient.name} is out of stock")
            ingredient.quantity_on_hand -= quantity
            session.add(
                InventoryMovement(
                    ingredient_id=ingredient.id,
                    order_id=order.id,
                    type="order",
                    quantity=-quantity,
                    reason=f"Consumed by {order.order_number}",
                )
            )

        session.add(Payment(order_id=order.id, provider="cash", amount=total))
        if coupon:
            coupon.usage_count += 1
            session.add(
                CouponRedemption(
                    coupon_id=coupon.id,
                    customer_id=customer.id,
                    order_id=order.id,
                    amount=discount_total,
                )
            )
        customer.order_count += 1
        customer.lifetime_value += total
        customer.last_order_at = datetime.now(UTC)
        session.add(
            Notification(
                order_id=order.id,
                channel="whatsapp",
                recipient=phone,
                template=settings.whatsapp_order_template,
                payload={"orderNumber": order.order_number, "customerName": customer.name, "total": total},
                status=NotificationStatus.PENDING
                if settings.whatsapp_enabled
                else NotificationStatus.SKIPPED,
                last_error=None if settings.whatsapp_enabled else "WhatsApp integration is disabled",
            )
        )

    await session.commit()
    await session.refresh(order)
    return await serialize_order(session, order)


async def get_public_order(
    session: AsyncSession, order_number: str, public_token: uuid.UUID
) -> OrderResponse:
    order = await session.scalar(
        select(Order).where(Order.order_number == order_number.upper(), Order.public_token == public_token)
    )
    if order is None:
        raise not_found("Order not found")
    return await serialize_order(session, order)
