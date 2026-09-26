"""Domain models (typed aliases over the row dicts persisted in SQLite)."""

from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    role: str = "user"
    is_active: bool = True


@dataclass
class Product:
    id: int
    name: str
    price: float
    category: str = ""
    is_active: bool = True


@dataclass
class Order:
    id: int
    username: str
    total: float
    status: str = "pending"
    note: str = ""


@dataclass
class OrderItem:
    id: int
    order_id: int
    product_id: int
    price: float
    quantity: int
