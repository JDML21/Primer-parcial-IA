"""Caso 5 — Rutas alternativas.

Dos rutas alcanzan la misma configuración del mundo. El agente las reconoce
como la misma situación física (CLOSED) y conserva la que corresponde a la
estrategia elegida y a la función de costo: la más barata.
"""

from __future__ import annotations

from helpers import load

from agent import solve
from agent.problem import MOVE, Action, result
from agent.search import uniform_cost_search
from agent.state import initial_state
from agent.world import build_world
from simulator import goal_satisfied, simulate


def _walk(world, state, zones):
    for zone in zones:
        state = result(world, state, Action(MOVE, zone, world.corridor_cost(state.zone, zone)))
    return state


def test_both_routes_reach_the_same_world_configuration() -> None:
    """Z1->Z2->Z4 y Z1->Z3->Z4 son la misma situación física con otra batería."""
    world = build_world(load("scenario_alt_routes.json"))
    start = initial_state(world)

    expensive = _walk(world, start, ["Z2", "Z4"])
    cheap = _walk(world, start, ["Z3", "Z4"])

    assert expensive.world_key() == cheap.world_key(), "misma configuracion del mundo"
    assert expensive != cheap, "distinta bateria residual => distinto estado"
    assert cheap.battery > expensive.battery

    assert cheap.battery >= expensive.battery


def test_agent_keeps_the_cheaper_route() -> None:
    scenario = load("scenario_alt_routes.json")
    plan = solve(scenario)

    assert plan["solution_found"] is True
    assert plan["total_cost"] == 8, plan["total_cost"]

    route = [s["to"] for s in plan["steps"] if s["op"] == "MOVE"]
    assert route == ["Z3", "Z4"], route

    final = simulate(scenario, plan["steps"])
    assert goal_satisfied(scenario, final)


def test_closed_does_not_reexplore_the_same_situation() -> None:
    """Con ciclos en el grafo, el numero de expansiones sigue siendo minusculo."""
    world = build_world(load("scenario_alt_routes.json"))
    outcome = uniform_cost_search(world)

    assert outcome.found is True
    assert outcome.expanded <= 10, outcome.expanded


if __name__ == "__main__":
    test_both_routes_reach_the_same_world_configuration()
    test_agent_keeps_the_cheaper_route()
    test_closed_does_not_reexplore_the_same_situation()
    print("Caso 5 (rutas alternativas): OK")
