"""Input validation helpers."""


def validate_price(price) -> None:
    if price is None or price < 0:
        raise ValueError("price must be a non-negative number")


def validate_username(username: str) -> None:
    if not username or not username.isalnum():
        raise ValueError("username must be non-empty and alphanumeric")


def validate_quantity(quantity) -> None:
    if quantity is None or quantity < 1:
        raise ValueError("quantity must be at least 1")
