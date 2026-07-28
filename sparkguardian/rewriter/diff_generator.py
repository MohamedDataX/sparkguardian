"""Unified diff between the original and rewritten source, for --dry-run."""
from __future__ import annotations

import difflib


def unified_diff(original: str, modified: str, filepath: str) -> str:
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, mod_lines, fromfile=f"a/{filepath}", tofile=f"b/{filepath}")
    return "".join(diff)
