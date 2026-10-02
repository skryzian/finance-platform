from decimal import Decimal


def decimal_amount(value: int | str | Decimal) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("Boolean values are not monetary amounts")
    if isinstance(value, float):
        raise TypeError("Binary floating-point values are not accepted for monetary amounts")
    return value if isinstance(value, Decimal) else Decimal(value)


def quantize_amount(value: int | str | Decimal, decimal_places: int) -> Decimal:
    if not 0 <= decimal_places <= 8:
        raise ValueError("Currency precision must be between zero and eight decimal places")
    quantum = Decimal(1).scaleb(-decimal_places)
    return decimal_amount(value).quantize(quantum)
