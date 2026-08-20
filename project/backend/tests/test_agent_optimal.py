"""El plan del agente sobre la instancia demo: contrato, costos y legalidad.

`simulator.py` actúa como validador independiente: re-ejecuta el plan con las
reglas del mundo, igual que hace el frontend con el suyo.
"""

from __future__ import annotations

import time

from helpers import load

from agent import solve
from simulator import goal_satisfied, simulate

VISUAL_OPS = {"MOVE", "PICKUP", "DROP", "INTERACT"}
INTERACT_ACTIONS = {"OPEN_DOOR", "REPAIR", "ACTIVATE", "RECHARGE"}


def _plan():
    scenario = load("scenario.json")
    return scenario, solve(scenario)


def test_plan_is_legal_and_reaches_the_goal() -> None:
    scenario, plan = _plan()
    assert plan["solution_found"] is True

    final = simulate(scenario, plan["steps"])
    assert goal_satisfied(scenario, final), final["stations"]
    assert final["energy_spent"] == plan["total_cost"]


def test_plan_respects_the_closed_contract() -> None:
    """Solo 4 op, y OPEN_DOOR/REPAIR/ACTIVATE/RECHARGE van dentro de INTERACT."""
    _scenario, plan = _plan()

    for step in plan["steps"]:
        assert step["op"] in VISUAL_OPS, step
        if step["op"] == "INTERACT":
            assert step["action"] in INTERACT_ACTIONS, step
            if step["action"] == "REPAIR":
                assert "consumes" in step, step
        else:
            assert "action" not in step, step


def test_step_costs_match_the_official_scenario_costs() -> None:
    """CONTRATO §5: los costos no se inventan, salen del escenario."""
    scenario, plan = _plan()
    costs = scenario["action_costs"]
    corridors = {(c["from"], c["to"]): c["cost"] for c in scenario["corridors"]}

    zone = scenario["robot"]["start"]
    for step in plan["steps"]:
        if step["op"] == "MOVE":
            assert step["from"] == zone, step
            assert step["cost"] == corridors[(step["from"], step["to"])], step
            zone = step["to"]
        elif step["op"] == "PICKUP":
            assert step["cost"] == costs["pickup"], step
        elif step["op"] == "DROP":
            assert step["cost"] == costs["drop"], step
        elif step["action"] == "RECHARGE":
            assert step["cost"] == costs["recharge"], step
        else:
            assert step["cost"] == costs["interact"], step

    assert plan["total_cost"] == sum(s["cost"] for s in plan["steps"])


def test_materials_travel_by_type_not_by_id() -> None:
    """§2.2: los materiales se referencian por tipo (FUSE), sin ids artificiales."""
    scenario, plan = _plan()
    material_types = {m["type"] for m in scenario["materials"]}
    key_and_tool_ids = {k["id"] for k in scenario["keys"]} | {t["id"] for t in scenario["tools"]}

    for step in plan["steps"]:
        if step["op"] in ("PICKUP", "DROP"):
            assert step["item"] in material_types | key_and_tool_ids, step


def test_search_finishes_in_exam_time() -> None:
    scenario = load("scenario.json")
    started = time.time()
    solve(scenario)
    elapsed = time.time() - started
    assert elapsed < 30, "la busqueda tardo %.1fs" % elapsed


def test_optimal_cost_is_stable() -> None:
    """Regresion: el optimo de la instancia demo es 88."""
    _scenario, plan = _plan()
    assert plan["total_cost"] == 88, plan["total_cost"]


if __name__ == "__main__":
    test_plan_is_legal_and_reaches_the_goal()
    test_plan_respects_the_closed_contract()
    test_step_costs_match_the_official_scenario_costs()
    test_materials_travel_by_type_not_by_id()
    test_search_finishes_in_exam_time()
    test_optimal_cost_is_stable()
    print("Plan del agente (contrato, costos, legalidad): OK")
