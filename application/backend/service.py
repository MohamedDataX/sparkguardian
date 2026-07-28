"""License persistence + business logic shared across routes."""
from __future__ import annotations

from datetime import UTC, datetime

from backend.database import get_conn
from backend.licensing import issue_token, verify_token

# ttl_days per license type; None = never expires.
#
# SparkGuardian is open source: the only type ever issued is the free
# `community` license, which never expires. Older `trial`/`monthly` rows from
# the pre-open-source builds still validate normally until they lapse.
TTL_DAYS: dict[str, int | None] = {"community": None}

FREE_TYPE = "community"


def _iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def create_license(name: str, email: str, kind: str = FREE_TYPE) -> dict[str, object]:
    """Issue a token of ``kind`` and persist it."""
    ttl = TTL_DAYS.get(kind)
    token, jti, exp = issue_token(name, email, kind, ttl)
    created_iso = _iso(int(datetime.now(tz=UTC).timestamp()))
    expires_iso = _iso(exp)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO licenses
               (jti, name, email, type, token, created_at, expires_at)
               VALUES (?,?,?,?,?,?,?)""",
            (jti, name, email, kind, token, created_iso, expires_iso),
        )
    return {
        "token": token,
        "type": kind,
        "name": name,
        "email": email,
        "expires_at": expires_iso,
    }


def existing_license(email: str) -> dict[str, object] | None:
    """Return this email's live community token, if any.

    Lets a user who lost their token get the same one back instead of piling up
    duplicates. Revoked rows are ignored on purpose — see ``is_revoked``.
    """
    with get_conn(write=False) as conn:
        row = conn.execute(
            "SELECT token, type, name, email, expires_at FROM licenses "
            "WHERE email=? AND type=? AND revoked=0 ORDER BY id DESC LIMIT 1",
            (email, FREE_TYPE),
        ).fetchone()
    return dict(row) if row else None


def is_revoked(email: str) -> bool:
    """True if every community license this email holds has been revoked."""
    with get_conn(write=False) as conn:
        revoked = conn.execute(
            "SELECT 1 FROM licenses WHERE email=? AND type=? AND revoked=1 LIMIT 1",
            (email, FREE_TYPE),
        ).fetchone()
    return revoked is not None and existing_license(email) is None


def validate(token: str) -> dict[str, object]:
    """Verify signature+expiry, cross-check DB (revocation), record activation."""
    result = verify_token(token)
    if not result.valid:
        return {"valid": False, "reason": result.reason}

    claims = result.claims or {}
    jti = str(claims.get("jti", ""))

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE jti=?", (jti,)).fetchone()
        if row is None:
            return {"valid": False, "reason": "unknown"}
        if row["revoked"]:
            return {"valid": False, "reason": "revoked"}
        conn.execute(
            "UPDATE licenses SET activations=activations+1, activated_at=? WHERE jti=?",
            (datetime.now(tz=UTC).isoformat(), jti),
        )

    return {
        "valid": True,
        "type": row["type"],
        "name": row["name"],
        "email": row["email"],
        "expires_at": row["expires_at"],
    }


def list_licenses() -> list[dict[str, object]]:
    with get_conn(write=False) as conn:
        rows = conn.execute(
            "SELECT jti, name, email, type, created_at, expires_at, revoked, "
            "activations, activated_at FROM licenses ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def revoke(jti: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE licenses SET revoked=1 WHERE jti=?", (jti,))
        return cur.rowcount > 0


def stats() -> dict[str, int]:
    now_iso = datetime.now(tz=UTC).isoformat()
    with get_conn(write=False) as conn:
        total = conn.execute("SELECT COUNT(*) c FROM licenses").fetchone()["c"]
        active = conn.execute(
            "SELECT COUNT(*) c FROM licenses WHERE revoked=0 "
            "AND (expires_at IS NULL OR expires_at > ?)",
            (now_iso,),
        ).fetchone()["c"]
        activated = conn.execute(
            "SELECT COUNT(*) c FROM licenses WHERE activations > 0"
        ).fetchone()["c"]
        revoked = conn.execute(
            "SELECT COUNT(*) c FROM licenses WHERE revoked=1"
        ).fetchone()["c"]
    return {"total": total, "active": active, "activated": activated, "revoked": revoked}
