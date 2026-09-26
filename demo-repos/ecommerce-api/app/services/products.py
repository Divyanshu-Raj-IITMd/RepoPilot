"""Product service: business logic for products."""

from typing import Optional

from app.repositories import db

PRODUCT_COLUMNS = "id, name, price, category, is_active"


def list_products(category: str = "") -> list[dict]:
    if category:
        rows = db.query_all(
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE category = ? ORDER BY id", (category,)
        )
    else:
        rows = db.query_all(f"SELECT {PRODUCT_COLUMNS} FROM products ORDER BY id")
    return [dict(r) for r in rows]


def get_product(product_id: int) -> Optional[dict]:
    row = db.query_one(
        f"SELECT {PRODUCT_COLUMNS} FROM products WHERE id = ?", (product_id,)
    )
    if row is None:
        return None
    return dict(row)


def create_product(name: str, price: float, category: str = "") -> dict:
    cursor = db.execute(
        "INSERT INTO products (name, price, category) VALUES (?, ?, ?)",
        (name, price, category),
    )
    return {"id": cursor.lastrowid, "name": name, "price": price, "category": category}


def deactivate_product(product_id: int) -> None:
    db.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
