"""Tiny SQLite layer — stdlib only, no ORM dependency."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from backend.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    jti            TEXT    UNIQUE NOT NULL,
    name           TEXT    NOT NULL,
    email          TEXT    NOT NULL,
    type           TEXT    NOT NULL,          -- trial | monthly | lifetime | enterprise
    token          TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    expires_at     TEXT,                       -- NULL = never expires (lifetime)
    revoked        INTEGER NOT NULL DEFAULT 0,
    activated_at   TEXT,
    activations    INTEGER NOT NULL DEFAULT 0,
    stripe_customer TEXT,
    stripe_sub      TEXT
);
CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
