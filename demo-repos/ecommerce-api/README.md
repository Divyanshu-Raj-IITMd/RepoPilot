# ecommerce-api

A small e-commerce REST API used as the demo target repository for RepoPilot.

- **Framework:** FastAPI
- **Database:** SQLite (stdlib `sqlite3`)
- **Auth:** HMAC-signed JWT-style tokens (stdlib `hmac`/`hashlib`)

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Layout

```
app/
  main.py            entry point
  auth/              token creation + verification, login service
  middleware/        bearer-token middleware
  routes/            HTTP endpoints (users, products, orders)
  services/          business logic
  repositories/      SQLite data access
  models/            domain dataclasses
  utils/             invoice math + validation helpers
tests/               pytest suite
```
