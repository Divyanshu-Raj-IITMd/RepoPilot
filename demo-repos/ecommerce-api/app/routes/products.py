"""Product endpoints."""

from fastapi import APIRouter

from app.services import products as product_service
from app.utils.validators import validate_price

router = APIRouter()


@router.get("/api/products")
def list_products(category: str = ""):
    products = product_service.list_products(category)
    return {"products": products}


@router.get("/api/products/{product_id}")
def get_product(product_id: int):
    product = product_service.get_product(product_id)
    return {"name": product["name"], "price": product["price"]}


@router.post("/api/products")
def create_product(body: dict):
    validate_price(body.get("price", 0))
    product = product_service.create_product(name=body["name"], price=body["price"], category=body.get("category", ""))
    return {"id": product["id"], "name": product["name"]}
