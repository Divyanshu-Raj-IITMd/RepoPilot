"""Tests for invoice calculation (deliberately incomplete)."""

from app.utils.invoice import calculate_invoice


def test_normal_invoice():
    assert calculate_invoice([{"price": 10, "quantity": 2}], 0.1) == 18.0


def test_single_item_no_discount():
    assert calculate_invoice([{"price": 5, "quantity": 3}]) == 15.0
