"""Order endpoints."""

from fastapi import APIRouter

from app.services import orders as order_service

router = APIRouter()


@router.get("/api/orders")
def list_orders(status: str = ""):
    orders = order_service.list_orders(status)
    return {"orders": orders}


@router.post("/api/orders")
def create_order(body: dict):
    order = order_service.create_order(
        username=body["username"], items=body["items"], note=body.get("note", "")
    )
    return {"id": order["id"], "total": order["total"]}


@router.delete("/api/orders/{order_id}")
def cancel_order(order_id: int):
    order_service.cancel_order(order_id)
    return {"cancelled": True}
