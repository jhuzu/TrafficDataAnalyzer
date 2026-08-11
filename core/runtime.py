"""Runtime discovery shared by command-line and web entry points."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


NODE_CANDIDATES = (
    Path("/opt/homebrew/bin/node"),
    Path("/usr/local/bin/node"),
    Path("/usr/bin/node"),
)


def find_node() -> Path | None:
    """Return an executable Node.js path across common macOS installations."""
    configured = os.environ.get("NODE_BIN", "").strip()
    candidates = [Path(configured)] if configured else []
    discovered = shutil.which("node")
    if discovered:
        candidates.append(Path(discovered))
    candidates.extend(NODE_CANDIDATES)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None
