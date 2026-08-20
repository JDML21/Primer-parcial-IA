"""Caso 3 — Costos diferentes.

Existe una instancia donde la solución con MENOS acciones NO es la de menor
costo, y el agente devuelve la de menor costo: es lo que se afirmó en
`design.md` al elegir UCS en vez de BFS.
"""

from __future__ import annotations

from helpers import load  # noqa: E402

from agent import solve  # noqa: E402
from simulator import goal_satisfied, simulate  # noqa: E402


def test_agent_prefers_cheaper_plan_with_more_steps() -> None:
    scenario = load("scenario_cost_vs_steps.json")
    plan = solve(scenario)

    assert plan["solution_found"] is True
    assert plan["total_cost"] == 12, plan["total_cost"]
    assert len(plan["steps"]) == 3, plan["steps"]

    # el plan elegido rodea por Z2 en vez de tomar el corredor directo caro
    zones = [s["to"] for s in plan["steps"] if s["op"] == "MOVE"]
    assert zones == ["Z2", "Z3"], zones

    final = simulate(scenario, plan["steps"])
    assert goal_satisfied(scenario, final)


def test_the_shortest_plan_is_more_expensive() -> None:
    """El plan de 2 acciones es legal, llega a la meta y cuesta casi el doble.

    Un agente que minimizara PASOS (BFS) devolveria este.
    """
    scenario = load("scenario_cost_vs_steps.json")
    shortest = [
        {"op": "MOVE", "from": "Z1", "to": "Z3", "cost": 20},
        {"op": "INTERACT", "target": "BEACON", "action": "ACTIVATE", "cost": 2},
    ]

    final = simulate(scenario, shortest)          # es legal...
    assert goal_satisfied(scenario, final)        # ...y alcanza la meta

    cost_shortest = sum(s["cost"] for s in shortest)
    optimal = solve(scenario)

    assert len(shortest) < len(optimal["steps"]), "tiene menos acciones"
    assert cost_shortest > optimal["total_cost"], "pero cuesta mas"
    assert (cost_shortest, optimal["total_cost"]) == (22, 12)


def test_relay_restriction_does_not_change_this_instance() -> None:
    """Permitir relevos de objetos vivos no abarata el plan en esta instancia."""
    from agent.search import uniform_cost_search
    from agent.world import build_world

    world = build_world(load("scenario_cost_vs_steps.json"))
    strict = uniform_cost_search(world, allow_live_drops=False)
    relaxed = uniform_cost_search(world, allow_live_drops=True)

    assert strict.found and relaxed.found
    assert strict.cost == relaxed.cost == 12


if __name__ == "__main__":
    test_agent_prefers_cheaper_plan_with_more_steps()
    test_the_shortest_plan_is_more_expensive()
    test_relay_restriction_does_not_change_this_instance()
    print("Caso 3 (menos pasos != menor costo): OK")
