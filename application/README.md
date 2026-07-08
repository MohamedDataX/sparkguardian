# SparkGuardian — Marketing & Licensing App

Landing page + license portal + billing for [SparkGuardian](https://github.com/MohamedDataX/sparkguardian).
Single Python stack (FastAPI) serving a no-build static frontend — few dependencies, easy to maintain.

```
application/
├── backend/            # FastAPI app
│   ├── main.py         # app + routing + static mount
│   ├── config.py       # env-driven settings
│   ├── database.py     # SQLite (stdlib, no ORM)
│   ├── licensing.py    # HS256 signed tokens (SG-…)
│   ├── service.py      # license CRUD + business logic
│   ├── billing.py      # Stripe checkout + webhook
│   ├── schemas.py      # pydantic models
│   └── routes/         # licenses / billing / admin
└── frontend/           # static landing + admin dashboard
    ├── index.html
    ├── admin.html
    └── static/         # css / js / img (logo)
```

## Run

```bash
cd application
./run.sh                       # venv + deps + server on :8000
# or manually:
pip install -r requirements.txt
cp .env.example .env           # then edit SECRET_KEY / ADMIN_TOKEN
uvicorn backend.main:app --reload
```

- Landing page: <http://localhost:8000>
- Admin dashboard: <http://localhost:8000/admin> (use `ADMIN_TOKEN`)
- API docs: <http://localhost:8000/docs>

## Deploy

The app needs a Python runtime (FastAPI backend) — **GitHub Pages cannot host it**
(static-only, no `/api/*`). Deploy the whole app to any container/Python host.

**Render (one click)** — `render.yaml` at the repo root is a ready blueprint:
New → Blueprint → pick this repo. It provisions the service, a 1 GB disk for the
SQLite DB, and generates `SECRET_KEY`/`ADMIN_TOKEN`. After the first deploy set
`PUBLIC_URL` to the Render URL (and `STRIPE_*` for billing).

**Docker (any host)**:
```bash
cd application
docker build -t sparkguardian-portal .
docker run -p 8000:8000 --env-file .env sparkguardian-portal
```

**Railway / Fly / Heroku-style**: `application/Procfile` runs
`uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

> SQLite lives on local disk — attach a persistent volume (Render disk above) so
> issued licenses survive restarts.

## License tokens

Signed JWTs (HS256, stdlib HMAC — no crypto dep) prefixed `SG-`. Claims: `sub`
(email), `name`, `type`, `iat`, `exp`, `jti`. The secret never leaves the
server; the CLI **activates online once** then caches locally and checks expiry
offline (keeps SparkGuardian's "100% offline" analysis).

| Endpoint | Purpose |
|---|---|
| `POST /api/licenses/trial` | Issue a 7-day trial (`{name,email}`) |
| `POST /api/licenses/validate` | Verify token — used by CLI activation |
| `POST /api/billing/checkout` | Start Stripe subscription → returns URL |
| `POST /api/billing/webhook` | Issue Pro license when payment completes |
| `GET  /api/admin/licenses` | List + stats (Bearer `ADMIN_TOKEN`) |
| `POST /api/admin/licenses/{jti}/revoke` | Revoke a token |

## Stripe (test mode)

1. Set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` (a $10/mo recurring price), `STRIPE_WEBHOOK_SECRET` in `.env`.
2. Forward webhooks locally: `stripe listen --forward-to localhost:8000/api/billing/webhook`.
3. Subscribe from the Pricing section → Stripe Checkout → on success a Pro license is issued.

Without keys the billing routes return `501` — the rest of the app still works.

## License types

`trial` (7d), `monthly` (30d), `lifetime` (never), `enterprise` (365d) — add
more in `backend/service.py::TTL_DAYS`.

## CLI integration

The `sparkguardian` package gates its commands behind a license:

```bash
sparkguardian activate            # paste your SG-… token (validates online, caches)
sparkguardian license             # show current license status
sparkguardian analyze app.py      # runs once licensed
```

Point the CLI at this server with `SPARKGUARDIAN_API_URL` (default `http://localhost:8000`).
Cache lives at `~/.sparkguardian/license.json`.
