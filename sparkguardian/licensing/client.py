"""Local license activation, caching and offline expiry checks."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Where the validated license is cached locally.
LICENSE_DIR = Path(os.getenv("SPARKGUARDIAN_HOME", str(Path.home() / ".sparkguardian")))
LICENSE_FILE = LICENSE_DIR / "license.json"

# Licensing server (the `application/` backend). Override for self-hosting.
API_URL = os.getenv("SPARKGUARDIAN_API_URL", "https://sparkguardian-portal.fly.dev").rstrip("/")

EXPIRED_MSG = (
    "Your license has expired.\n\n"
    "SparkGuardian is open source and free — grab a new token:\n\n"
    "  " + API_URL + "/#token"
)


class LicenseError(Exception):
    """Raised when licensing fails (expired, invalid, unreachable)."""


def _parse_expiry(iso: str | None) -> datetime | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso)


def load_license() -> dict[str, Any] | None:
    """Return cached license dict, or None if absent/corrupt."""
    if not LICENSE_FILE.exists():
        return None
    try:
        return json.loads(LICENSE_FILE.read_text())
    except (ValueError, OSError):
        return None


def _save_license(data: dict[str, Any]) -> None:
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(json.dumps(data, indent=2))
    try:
        LICENSE_FILE.chmod(0o600)
    except OSError:
        pass


def is_expired(data: dict[str, Any]) -> bool:
    exp = _parse_expiry(data.get("expires_at"))
    if exp is None:  # lifetime / no expiry
        return False
    return datetime.now(tz=timezone.utc) >= exp


def activate(token: str) -> dict[str, Any]:
    """Validate a token against the server and cache it. Returns license data."""
    token = token.strip()
    try:
        resp = httpx.post(
            f"{API_URL}/api/licenses/validate", json={"token": token}, timeout=10.0
        )
    except httpx.HTTPError as exc:
        raise LicenseError(f"Could not reach licensing server at {API_URL}: {exc}") from exc

    if resp.status_code != 200:
        raise LicenseError(f"Activation failed (HTTP {resp.status_code}).")

    body = resp.json()
    if not body.get("valid"):
        reason = body.get("reason", "invalid")
        raise LicenseError(f"Token rejected: {reason}.")

    data = {
        "token": token,
        "name": body.get("name"),
        "email": body.get("email"),
        "type": body.get("type"),
        "expires_at": body.get("expires_at"),
        "activated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    _save_license(data)
    return data


def status_line(data: dict[str, Any] | None = None) -> str:
    """Human-readable one-liner about the current license."""
    data = data or load_license()
    if not data:
        return "No license activated. Run: sparkguardian activate"
    exp = data.get("expires_at")
    when = "never" if not exp else exp[:10]
    state = "EXPIRED" if is_expired(data) else "active"
    return f"{data.get('type', 'unknown')} license · {state} · expires {when} · {data.get('email', '')}"


def ensure_licensed(console: Any = None, *, prompt: Any = None) -> dict[str, Any]:
    """Gate CLI commands. Activates on first run, blocks when expired.

    ``console`` is an optional rich Console for output; ``prompt`` an optional
    callable (e.g. ``typer.prompt``) used to ask for a token interactively.
    """
    def _echo(msg: str) -> None:
        if console is not None:
            console.print(msg)
        else:  # pragma: no cover - fallback
            print(msg)

    data = load_license()

    if data is None:
        _echo("[yellow]No license found.[/yellow]")
        if prompt is None:
            raise LicenseError("No license. Run: sparkguardian activate")
        token = prompt("Enter your license token")
        data = activate(token)
        _echo("[green]License activated.[/green]")
        return data

    if is_expired(data):
        _echo(f"[yellow]{EXPIRED_MSG}[/yellow]")
        raise LicenseError("License expired.")

    return data
