"""Ejecuta toda la validación del parcial de una vez.

    python3 tests/run_all.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TESTS = [
    "test_demo_plan.py",
    "test_agent_optimal.py",
    "test_design_consistency.py",
    "test_case1_equivalence.py",
    "test_case2_relevance.py",
    "test_case3_cost_vs_steps.py",
    "test_case4_failure.py",
    "test_case5_routes.py",
]

here = Path(__file__).resolve().parent
failed = []

for name in TESTS:
    print("\n--- {} ---".format(name))
    outcome = subprocess.run([sys.executable, str(here / name)], cwd=str(here))
    if outcome.returncode != 0:
        failed.append(name)

print("\n" + "=" * 52)
if failed:
    print("FALLARON: {}".format(", ".join(failed)))
    sys.exit(1)
print("Todos los tests pasaron ({} archivos).".format(len(TESTS)))
