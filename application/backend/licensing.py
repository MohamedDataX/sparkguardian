"""License token creation & verification.

Tokens are signed JWTs (HS256, HMAC-SHA256) prefixed with ``SG-``. Signing uses
only the stdlib (``hmac``/``hashlib``) so no crypto dependency is required.

Payload claims::

    sub  -> email
    name -> holder name
    type -> trial | monthly | lifetime | enterprise
    iat  -> issued-at   (unix seconds)
    exp  -> expiry      (unix seconds; omitted for lifetime)
    jti  -> unique id
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

from backend.config import settings

PREFIX = "SG-"
_ALG = "HS256"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


def _sign(signing_input: bytes) -> str:
    sig = hmac.new(settings.SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    return _b64url(sig)


def issue_token(name: str, email: str, kind: str, ttl_days: int | None) -> tuple[str, str, int | None]:
    """Create a signed token. Returns ``(token, jti, exp)`` — ``exp`` is None for lifetime."""
    now = int(time.time())
    jti = uuid.uuid4().hex
    payload: dict[str, object] = {
        "sub": email,
        "name": name,
        "type": kind,
        "iat": now,
        "jti": jti,
    }
    exp: int | None = None
    if ttl_days is not None:
        exp = now + ttl_days * 86_400
        payload["exp"] = exp

    header = {"alg": _ALG, "typ": "JWT"}
    segments = [
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode()
    segments.append(_sign(signing_input))
    return PREFIX + ".".join(segments), jti, exp


@dataclass
class VerifiedToken:
    valid: bool
    reason: str = ""
    claims: dict[str, object] | None = None


def verify_token(token: str) -> VerifiedToken:
    """Verify signature and expiry. Does NOT check DB revocation (caller's job)."""
    if not token.startswith(PREFIX):
        return VerifiedToken(False, "bad_prefix")
    raw = token[len(PREFIX):]
    try:
        h_seg, p_seg, sig_seg = raw.split(".")
    except ValueError:
        return VerifiedToken(False, "malformed")

    expected = _sign(f"{h_seg}.{p_seg}".encode())
    if not hmac.compare_digest(expected, sig_seg):
        return VerifiedToken(False, "bad_signature")

    try:
        claims = json.loads(_b64url_decode(p_seg))
    except (ValueError, json.JSONDecodeError):
        return VerifiedToken(False, "bad_payload")

    exp = claims.get("exp")
    if exp is not None and int(time.time()) >= int(exp):
        return VerifiedToken(False, "expired", claims)

    return VerifiedToken(True, "", claims)
