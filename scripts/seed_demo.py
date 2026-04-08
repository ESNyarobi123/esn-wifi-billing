#!/usr/bin/env python3
"""Run ``python -m app.seed`` from repo root (idempotent).

Respects ``SEED_DEMO_DATA`` in the monorepo ``.env`` (merged into the subprocess
environment): use ``false`` for minimal bootstrap, ``true`` for the full demo dataset.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _merge_repo_dotenv(repo_root: Path, base: dict[str, str]) -> dict[str, str]:
    """Fill missing keys from ``repo_root/.env``. Existing OS env always wins."""
    path = repo_root / ".env"
    if not path.is_file():
        return base
    out = dict(base)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        out[key] = val
    return out


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    api_root = repo_root / "services" / "api"
    if not api_root.is_dir():
        print(f"Expected API root at {api_root}", file=sys.stderr)
        sys.exit(1)
    env = _merge_repo_dotenv(repo_root, os.environ.copy())
    env["PYTHONPATH"] = str(api_root)
    subprocess.check_call([sys.executable, "-m", "app.seed"], cwd=str(api_root), env=env)


if __name__ == "__main__":
    main()
