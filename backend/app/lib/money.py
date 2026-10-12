from app.models.entities import DiscountType


def calculate_discount(
    subtotal: int,
    discount_type: DiscountType | None = None,
    value: int = 0,
    maximum_discount: int | None = None,
) -> int:
    if discount_type is None:
        return 0
    raw = subtotal * value // 10_000 if discount_type == DiscountType.PERCENTAGE else value
    if maximum_discount is not None:
        raw = min(raw, maximum_discount)
    return max(0, min(subtotal, raw))


def calculate_tax(taxable_amount: int, tax_rate_bps: int) -> int:
    return max(0, round(taxable_amount * tax_rate_bps / 10_000))


def calculate_delivery_fee(subtotal_after_discount: int, base_fee: int, free_threshold: int | None) -> int:
    if free_threshold is not None and subtotal_after_discount >= free_threshold:
        return 0
    return base_fee
