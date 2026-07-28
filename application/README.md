# SparkGuardian — Landing Page & Token Portal

Landing page + free-token portal for [SparkGuardian](https://github.com/MohamedDataX/sparkguardian).
Single Python stack (FastAPI) serving a no-build static frontend — few dependencies, easy to maintain.

SparkGuardian is **open source and free**. Tokens exist only to identify users
and let the CLI work offline — there is no paid tier and no billing.

```
application/
├── backend/            # FastAPI app
│   ├── main.py         # app + routing + static mount
│   ├── config.py       # env-driven settings
│   ├── database.py     # SQLite (stdlib, no ORM)
│   ├── licensing.py    # HS256 signed tokens (SG-…)
│   ├── service.py      # license CRUD + business logic
│   ├── schemas.py      # pydantic models
│   └── routes/         # licenses / admin
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

**AWS Lambda (what the public portal runs on)** — `lambda_handler.py` wraps the
FastAPI app with Mangum and API Gateway sits in front. Lambda only lets you write
to `/tmp`, and that disappears between invocations, so `backend/storage.py` keeps
the SQLite file in S3: pulled on cold start, pushed after every write.

**Docker (any host)**:

```bash
cd application
docker build -t sparkguardian-portal .
docker run -p 8000:8000 --env-file .env sparkguardian-portal
```

**Fly.io**: `application/fly.toml` (Paris region, health check, and a volume
mounted at `/data` for the database).

**Railway / Heroku-style**: `application/Procfile` runs
`uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

> Outside Lambda, SQLite lives on local disk — attach a persistent volume so
> issued licenses survive restarts.

## License tokens

Signed JWTs (HS256, stdlib HMAC — no crypto dep) prefixed `SG-`. Claims: `sub`
(email), `name`, `type`, `iat`, `exp`, `jti`. The secret never leaves the
server; the CLI **activates online once** then caches locally and checks expiry
offline (keeps SparkGuardian's "100% offline" analysis).

| Endpoint | Purpose |
|---|---|
| `POST /api/licenses/free` | Issue a free community token (`{name,email}`) |
| `POST /api/licenses/validate` | Verify token — used by CLI activation |
| `GET  /api/admin/licenses` | List + stats (Bearer `ADMIN_TOKEN`) |
| `POST /api/admin/licenses/{jti}/revoke` | Revoke a token |

`/api/licenses/free` is **idempotent**: repeating it with the same email returns
the token already issued, so a user who lost theirs can get it back. A revoked
email gets `403` instead of a fresh token.

## License types

`community` — free, never expires. That's the only type issued; see
`backend/service.py::TTL_DAYS` if you self-host and want more.

Tokens issued before the project went open source (`trial`, `monthly`) still
validate until they lapse; their holders just request a free one afterwards.

## CLI integration

The `sparkguardian` package asks for a token on first use:

```bash
sparkguardian activate            # paste your SG-… token (validates online, caches)
sparkguardian license             # show current license status
sparkguardian analyze app.py      # runs once activated
```

By default the CLI talks to the public portal. Set `SPARKGUARDIAN_API_URL` to
point it at your own instance instead (`http://localhost:8000` when running the
commands above). The cache lives at `~/.sparkguardian/license.json`.
