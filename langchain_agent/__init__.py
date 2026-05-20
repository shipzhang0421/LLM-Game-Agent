"""LangChain-based planners for the LLM Game Agent project."""

from __future__ import annotations

import site
import sys
from pathlib import Path


def _ensure_user_site_packages() -> None:
    candidates: list[str] = []
    project_root = Path(__file__).resolve().parents[1]
    candidates.append(str(project_root / "vendor" / "python"))
    try:
        candidates.append(site.getusersitepackages())
    except Exception:
        pass

    candidates.append(str(Path.home() / "AppData" / "Roaming" / "Python" / "Python39" / "site-packages"))

    for candidate in candidates:
        if not candidate or candidate in sys.path:
            continue
        sys.path.append(candidate)


_ensure_user_site_packages()
