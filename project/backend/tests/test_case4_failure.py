"""Caso 4 — Sin solución.

El agente termina y devuelve FAILURE cuando la misión no se puede completar.
No se acepta una ejecución que quede atrapada explorando el espacio.
"""

from __future__ import annotations

import time

from helpers import load  # noqa: E402

from agent import solve  # noqa: E402
from agent.search import uniform_cost_search  # noqa: E402
from agent.world import build_world  # noqa: E402


def test_impossible_mission_returns_failure() -> None:
    """PANEL_A exige BOLT, que no existe en el escenario."""
    scenario = load("scenario_no_solution.json")

    started = time.time()
    plan = solve(scenario)
    elapsed = time.time() - started

    assert plan["solution_found"] is False
    assert plan["steps"] == []
    assert plan["total_cost"] == 0
    assert "FAILURE" in plan["message"]
    assert elapsed < 5, "debe terminar, no quedarse explorando: %.1fs" % elapsed


def test_failure_is_exhaustion_not_a_node_budget_abort() -> None:
    """La frontera se vacía: es una demostración de que no hay plan.

    Agotar la cota de nodos seria distinto — `aborted` — y no probaria nada.
    """
    world = build_world(load("scenario_no_solution.json"))
    outcome = uniform_cost_search(world)

    assert outcome.found is False
    assert outcome.aborted is False, "la busqueda se agoto por si sola, sin tocar la cota"
    assert outcome.expanded > 0


def test_reachable_space_is_finite_and_closed_prevents_cycles() -> None:
    """El mapa tiene ciclos (Z1->Z2->Z1) y aun asi la busqueda termina."""
    world = build_world(load("scenario_no_solution.json"))
    outcome = uniform_cost_search(world, max_nodes=10_000)

    assert outcome.aborted is False
    assert outcome.expanded < 10_000


if __name__ == "__main__":
    test_impossible_mission_returns_failure()
    test_failure_is_exhaustion_not_a_node_budget_abort()
    test_reachable_space_is_finite_and_closed_prevents_cycles()
    print("Caso 4 (FAILURE): OK")
