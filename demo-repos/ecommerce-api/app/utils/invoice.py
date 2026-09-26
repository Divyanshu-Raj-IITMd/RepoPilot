"""Invoice calculation utilities.

Pure functions with no I/O — the main target for RepoPilot's test
generation + verification loop.
"""


def calculate_invoice(items: list[dict], discount: float = 0.0) -> float:
    """Calculate the final invoice total for a list of items.

    Each item is a dict with "price" and "quantity". `discount` is a
    fraction between 0 and 1 (0.1 = 10% off) applied to the subtotal.

    >>> calculate_invoice([{"price": 10, "quantity": 2}], 0.1)
    18.0
    """
    subtotal = 0
    for item in items:
        subtotal += item["price"] * item["quantity"]
    return round(subtotal * (1 - discount), 2)
