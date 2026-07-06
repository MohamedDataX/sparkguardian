from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path


def backup_file(filepath: str) -> str:
    src = Path(filepath)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = src.with_suffix(f".{ts}.bak{src.suffix}")
    shutil.copy2(src, dest)
    return str(dest)


def collect_python_files(path: str) -> list[str]:
    p = Path(path)
    if p.is_file():
        return [str(p)]
    return [str(f) for f in p.rglob("*.py")]
