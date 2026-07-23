"""Tiny SQLite layer — stdlib only, no ORM dependency."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from backend import storage
from backend.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    jti            TEXT    UNIQUE NOT NULL,
    name           TEXT    NOT NULL,
    email          TEXT    NOT NULL,
    type           TEXT    NOT NULL,          -- community (legacy rows: trial | monthly)
    token          TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    expires_at     TEXT,                       -- NULL = never expires (community)
    revoked        INTEGER NOT NULL DEFAULT 0,
    activated_at   TEXT,
    activations    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email);
"""


def init_db() -> None:
    with get_conn(write=True) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def get_conn(*, write: bool = True) -> Iterator[sqlite3.Connection]:
    """Open the database, syncing with S3 when running on Lambda.

    ``write=False`` skips the upload — worth it on read-heavy endpoints, since
    every push re-uploads the whole file.
    """
    storage.pull(settings.DATABASE_PATH)

    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

    if write:
        storage.push(settings.DATABASE_PATH)
