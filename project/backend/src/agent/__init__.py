"""Fachada del agente: escenario -> respuesta de /api/solve.

    solve(scenario) -> {"solution_found", "total_cost", "steps", "message"}

Sin solución: solution_found=False, steps=[] (caso FAILURE del enunciado).
"""

from __future__ import annotations

from typing import Any, Dict

from .search import uniform_cost_search
from .translate import to_contract_steps
from .world import build_world

__all__ = ["solve", "build_world", "uniform_cost_search", "to_contract_steps"]

DEFAULT_MAX_NODES = 500_000


def solve(scenario: Dict[str, Any], max_nodes: int = DEFAULT_MAX_NODES) -> Dict[str, Any]:
    """Construye el mundo, corre UCS y traduce el plan al contrato."""
    world = build_world(scenario)
    outcome = uniform_cost_search(world, max_nodes=max_nodes)

    if not outcome.found:
        if outcome.aborted:
            message = (
                "Search aborted after expanding {} nodes: the node budget was "
                "exhausted before proving anything.".format(outcome.expanded)
            )
        else:
            message = (
                "FAILURE — no plan reaches the mission goal "
                "({} states expanded, {} generated).".format(
                    outcome.expanded, outcome.generated
                )
            )
        return {
            "solution_found": False,
            "total_cost": 0,
            "steps": [],
            "message": message,
        }

    steps = to_contract_steps(world, outcome.plan)
    return {
        "solution_found": True,
        # el costo es el g(n) del nodo meta, no una suma recalculada aparte
        "total_cost": outcome.cost,
        "steps": steps,
        "message": (
            "Optimal plan found by uniform-cost search: {} steps, cost {} "
            "({} states expanded, {} generated).".format(
                len(steps), outcome.cost, outcome.expanded, outcome.generated
            )
        ),
    }
