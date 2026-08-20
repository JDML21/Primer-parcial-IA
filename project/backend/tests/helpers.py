"""Utilidades compartidas por los tests de validación."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCENARIOS = ROOT.parent / "scenarios"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load(name: str) -> Dict[str, Any]:
    """Carga un escenario de `project/scenarios` por nombre de archivo."""
    with (SCENARIOS / name).open(encoding="utf-8") as handle:
        return json.load(handle)
