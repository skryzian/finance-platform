from decimal import Decimal

import pytest

from app.utils.currency import quantize_amount


def test_currency_precision_supports_zero_and_two_decimal_currencies():
    assert quantize_amount(Decimal("126.75"), 0) == Decimal("127")
    assert quantize_amount("126.756", 2) == Decimal("126.76")


def test_money_input_does_not_accept_binary_float():
    with pytest.raises(TypeError):
        quantize_amount(1.1, 2)
