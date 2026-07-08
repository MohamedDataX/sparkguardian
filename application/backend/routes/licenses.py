"""Public license endpoints — trial generation + activation/validation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import service
from backend.schemas import (
    TokenResponse,
    TrialRequest,
    ValidateRequest,
    ValidateResponse,
)

router = APIRouter(prefix="/api/licenses", tags=["licenses"])


@router.post("/trial", response_model=TokenResponse)
def create_trial(req: TrialRequest) -> TokenResponse:
    """Generate a 7-day free-trial token for the given name + email."""
    if service.has_active_trial(req.email):
        raise HTTPException(status_code=409, detail="A trial already exists for this email.")
    data = service.create_license(req.name, req.email, "trial")
    return TokenResponse(**data)


@router.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest) -> ValidateResponse:
    """Validate a token (signature + expiry + revocation). Called by the CLI on activation."""
    return ValidateResponse(**service.validate(req.token))
