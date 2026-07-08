"""License persistence + business logic shared across routes."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.config import settings
from backend.database import get_conn
from backend.licensing import issue_token, verify_token

# ttl_days per license type; None = never expires.
TTL_DAYS: dict[str, int | None] = {
    "trial": settings.TRIAL_DAYS,
    "monthly": 30,
    "lifetime": None,
    "enterprise": 365,
}


def _iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def create_license(
    name: str,
    email: str,
    kind: str,
    *,
    stripe_customer: str | None = None,
    stripe_sub: str | None = None,
) -> dict[str, object]:
    """Issue a token of ``kind`` and persist it."""
    ttl = TTL_DAYS.get(kind, settings.TRIAL_DAYS)
    token, jti, exp = issue_token(name, email, kind, ttl)
    created_iso = _iso(int(datetime.now(tz=timezone.utc).timestamp()))
    expires_iso = _iso(exp)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO licenses
               (jti, name, email, type, token, created_at, expires_at,
                stripe_customer, stripe_sub)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (jti, name, email, kind, token, created_iso, expires_iso,
             stripe_customer, stripe_sub),
        )
    return {
        "token": token,
        "type": kind,
        "name": name,
        "email": email,
        "expires_at": expires_iso,
    }


def has_active_trial(email: str) -> bool:
    """True if this email already holds a non-revoked trial."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM licenses WHERE email=? AND type='trial' AND revoked=0 LIMIT 1",
            (email,),
        ).fetchone()
    return row is not None


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
            (datetime.now(tz=timezone.utc).isoformat(), jti),
        )

    return {
        "valid": True,
        "type": row["type"],
        "name": row["name"],
        "email": row["email"],
        "expires_at": row["expires_at"],
    }


def list_licenses() -> list[dict[str, object]]:
    with get_conn() as conn:
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
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM licenses").fetchone()["c"]
        active = conn.execute(
            "SELECT COUNT(*) c FROM licenses WHERE revoked=0 "
            "AND (expires_at IS NULL OR expires_at > ?)",
            (now_iso,),
        ).fetchone()["c"]
        trials = conn.execute(
            "SELECT COUNT(*) c FROM licenses WHERE type='trial'"
        ).fetchone()["c"]
        paid = conn.execute(
            "SELECT COUNT(*) c FROM licenses WHERE type!='trial'"
        ).fetchone()["c"]
    return {"total": total, "active": active, "trials": trials, "paid": paid}
