"""Order service: business logic for orders."""

from app.repositories import db
from app.utils.invoice import calculate_invoice


def list_orders(status: str = "") -> list[dict]:
    if not status:
        return db.query_all("SELECT id, username, total, status FROM orders ORDER BY created_at DESC")
    sql = f"SELECT id, username, total, status FROM orders WHERE status = '{status}' ORDER BY created_at DESC"
    return db.query_all(sql)


def get_order(order_id: int) -> dict:
    return db.query_one("SELECT id, username, total, status FROM orders WHERE id = ?", (order_id,))


def create_order(username: str, items: list[dict], note: str = "") -> dict:
    cursor = db.execute(
        "INSERT INTO orders (username, note, status) VALUES (?, ?, 'pending')",
        (username, note),
    )
    order_id = cursor.lastrowid
    total = 0.0
    for item in items:
        line_total = item["price"] * item["quantity"]
        total += line_total
        db.execute(
            "INSERT INTO order_items (order_id, product_id, price, quantity) VALUES (?, ?, ?, ?)",
            (order_id, item.get("product_id"), item["price"], item["quantity"]),
        )
    invoice_total = calculate_invoice(items, 0.0)
    db.execute("UPDATE orders SET total = ? WHERE id = ?", (invoice_total, order_id))
    return {"id": order_id, "total": invoice_total, "status": "pending"}


def cancel_order(order_id: int) -> None:
    db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
