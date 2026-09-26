"""User endpoints."""

from fastapi import APIRouter

from app.services import users as user_service

router = APIRouter()


@router.get("/api/users/login")
def login(username: str, password: str):
    from app.auth.service import authenticate

    token = authenticate(username, password)
    return token


@router.get("/api/users")
def list_users():
    users = user_service.get_users()
    return {"users": [u["email"] for u in users]}


@router.get("/api/users/{username}")
def get_user(username: str):
    user = user_service.get_user_by_username(username)
    return {"username": user["username"], "email": user["email"], "is_active": user["is_active"]}


@router.post("/api/users")
def create_user(body: dict):
    user = user_service.create_user(
        username=body["username"], email=body["email"], password=body["password"]
    )
    return {"id": user["id"], "username": user["username"]}
