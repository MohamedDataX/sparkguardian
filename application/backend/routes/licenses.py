"""Public license endpoints — free token generation + activation/validation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import service
from backend.schemas import (
    TokenRequest,
    TokenResponse,
    ValidateRequest,
    ValidateResponse,
)

router = APIRouter(prefix="/api/licenses", tags=["licenses"])


@router.post("/free", response_model=TokenResponse)
def create_free(req: TokenRequest) -> TokenResponse:
    """Issue a free community token (never expires) for a name + email.

    Idempotent: asking twice with the same email returns the same token rather
    than issuing a second one, so a lost token can always be recovered.
    """
    if service.is_revoked(req.email):
        raise HTTPException(status_code=403, detail="This email's license has been revoked.")

    existing = service.existing_license(req.email)
    if existing is not None:
        return TokenResponse(**existing)

    data = service.create_license(req.name, req.email)
    return TokenResponse(**data)


# Legacy path from the pre-open-source builds — same free token now.
@router.post("/trial", response_model=TokenResponse, include_in_schema=False)
def create_trial(req: TokenRequest) -> TokenResponse:
    return create_free(req)


@router.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest) -> ValidateResponse:
    """Validate a token (signature + expiry + revocation). Called by the CLI on activation."""
    return ValidateResponse(**service.validate(req.token))
