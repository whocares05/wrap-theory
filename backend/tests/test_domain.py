import pytest

from app.core.errors import AppError
from app.lib.money import calculate_delivery_fee, calculate_discount, calculate_tax
from app.lib.phone import normalize_pakistani_phone
from app.models.entities import DiscountType


def test_percentage_discount_is_capped() -> None:
    assert calculate_discount(100_000, DiscountType.PERCENTAGE, 2_000, 15_000) == 15_000


def test_fixed_discount_cannot_make_total_negative() -> None:
    assert calculate_discount(5_000, DiscountType.FIXED, 9_000) == 5_000


def test_tax_and_free_delivery_use_integer_paisa() -> None:
    assert calculate_tax(99_900, 1_600) == 15_984
    assert calculate_delivery_fee(250_000, 15_000, 250_000) == 0
    assert calculate_delivery_fee(249_999, 15_000, 250_000) == 15_000


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("0300 1234567", "+923001234567"),
        ("+92-300-1234567", "+923001234567"),
        ("0092 300 1234567", "+923001234567"),
    ],
)
def test_phone_normalization(input_value: str, expected: str) -> None:
    assert normalize_pakistani_phone(input_value) == expected


def test_invalid_phone_is_rejected() -> None:
    with pytest.raises(AppError) as error:
        normalize_pakistani_phone("123")
    assert error.value.status_code == 400
