"""S3-backed persistence for the SQLite database.

Lambda's filesystem is ephemeral and only ``/tmp`` is writable, so the database
lives in S3 and is pulled into ``/tmp`` on cold start, then pushed back after
every write.

When ``S3_BUCKET`` is unset this module does nothing at all and the app keeps
using a plain local file — that's the local-dev and self-hosting path.
"""
from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger(__name__)

S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_DB_KEY = os.getenv("S3_DB_KEY", "sparkguardian.db")

# Guards the download/upload pair. Lambda is pinned to one concurrent execution
# (see deploy_aws.sh) so this only has to serialise threads inside one sandbox.
_lock = threading.Lock()
_pulled = False


def enabled() -> bool:
    return bool(S3_BUCKET)


def _client():  # type: ignore[no-untyped-def]
    import boto3  # provided by the Lambda runtime

    return boto3.client("s3")


def pull(local_path: str) -> None:
    """Fetch the database from S3 once per cold start.

    A missing object is not an error: the first ever deploy has no database
    yet, and ``init_db`` will create one that the next push uploads.
    """
    global _pulled
    if not enabled() or _pulled:
        return

    with _lock:
        if _pulled:
            return
        try:
            _client().download_file(S3_BUCKET, S3_DB_KEY, local_path)
            log.info("pulled s3://%s/%s -> %s", S3_BUCKET, S3_DB_KEY, local_path)
        except Exception as exc:  # noqa: BLE001 - any failure means "start empty"
            log.info("no database in S3 yet (%s) — starting fresh", exc)
        _pulled = True


def push(local_path: str) -> None:
    """Upload the database back to S3 after a write."""
    if not enabled():
        return
    with _lock:
        try:
            _client().upload_file(local_path, S3_BUCKET, S3_DB_KEY)
        except Exception:  # noqa: BLE001
            # Losing the upload would silently lose an issued token, so make it
            # loud rather than returning a token that won't survive.
            log.exception("failed to push database to s3://%s/%s", S3_BUCKET, S3_DB_KEY)
            raise
