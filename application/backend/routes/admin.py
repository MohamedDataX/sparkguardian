"""Admin endpoints — list / revoke licenses + stats. Bearer-token protected."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from backend import service
from backend.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(authorization: str = Header(default="")) -> None:
    """Guard: expects ``Authorization: Bearer <ADMIN_TOKEN>``."""
    token = authorization.removeprefix("Bearer ").strip()
    if not token or token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/licenses", dependencies=[Depends(require_admin)])
def list_all() -> dict[str, object]:
    return {"licenses": service.list_licenses(), "stats": service.stats()}


@router.post("/licenses/{jti}/revoke", dependencies=[Depends(require_admin)])
def revoke(jti: str) -> dict[str, str]:
    if not service.revoke(jti):
        raise HTTPException(status_code=404, detail="License not found")
    return {"status": "revoked", "jti": jti}
