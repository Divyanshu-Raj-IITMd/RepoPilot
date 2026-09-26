"""E-commerce API — demo repository for RepoPilot.

A small but realistic FastAPI service. It is intentionally imperfect:
it contains a handful of realistic defects (unhandled None, string-built
SQL, unvalidated discount, hardcoded secrets, missing coverage) that
RepoPilot's agents are expected to find. See the RepoPilot evaluation
dataset for the ground truth.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.middleware.auth import auth_middleware
from app.routes import orders, products, users

app = FastAPI(title="ecommerce-api", version="1.2.0")


@app.middleware("http")
async def request_guard(request: Request, call_next):
    return await auth_middleware(request, call_next)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.get("/health")
def health():
    return {"status": "ok"}
