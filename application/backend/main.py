"""SparkGuardian licensing portal — FastAPI app.

Serves the static landing page and the license/admin JSON API from a single
process. Run with::

    uvicorn backend.main:app --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.routes import admin, licenses

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="SparkGuardian Licensing", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    init_db()


app.include_router(licenses.router)
app.include_router(admin.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "admin.html")


# Static assets (css/js/img) — mounted last so it doesn't shadow API routes.
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
