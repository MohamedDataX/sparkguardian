"""Client-side licensing for the SparkGuardian CLI.

First run activates a token online (once), caches it locally, then verifies
expiry offline on every subsequent run — keeping analysis 100% offline.
"""
from sparkguardian.licensing.client import (
    LicenseError,
    activate,
    ensure_licensed,
    load_license,
    status_line,
)

__all__ = [
    "LicenseError",
    "activate",
    "ensure_licensed",
    "load_license",
    "status_line",
]
