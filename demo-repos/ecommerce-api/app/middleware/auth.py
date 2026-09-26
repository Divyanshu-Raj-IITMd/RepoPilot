"""HTTP middleware: verifies the Bearer token on protected routes."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.jwt import decode_token

PUBLIC_PATHS = {"/health", "/api/users/login"}


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or not path.startswith("/api/"):
        return await call_next(request)
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "missing bearer token"})
    try:
        payload = decode_token(auth_header.removeprefix("Bearer ").strip())
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})
    request.state.username = payload.get("sub")
    return await call_next(request)
