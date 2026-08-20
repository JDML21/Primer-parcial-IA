"""El código hace lo que `design.md` dice que hace.

La rúbrica evalúa la consistencia entre el modelo matemático y la
implementación. En vez de confiar en la lectura, este test recorre estados
alcanzables reales y comprueba, sobre cada acción generada, las precondiciones
escritas en el documento.
"""

from __future__ import annotations

import itertools
from heapq import heappop, heappush

from helpers import load

from agent.problem import (
    ACTIVATE,
    DROP,
    MOVE,
    OPEN_DOOR,
    PICKUP,
    RECHARGE,
    REPAIR,
    applicable,
    goal_test,
    result,
)
from agent.state import initial_state, is_alive, material_needs, pending_panels
from agent.world import build_world

SAMPLE = 4000


def _reachable_states(world, limit=SAMPLE):
    """Muestra de estados alcanzables, en orden de costo (como los ve UCS)."""
    tiebreak = itertools.count()
    frontier = [(0, next(tiebreak), initial_state(world))]
    seen = set()
    while frontier and len(seen) < limit:
        g, _, state = heappop(frontier)
        if state in seen:
            continue
        seen.add(state)
        yield state
        for action in applicable(world, state):
            heappush(frontier, (g + action.cost, next(tiebreak), result(world, state, action)))


def test_every_generated_action_matches_the_documented_preconditions() -> None:
    world = build_world(load("scenario.json"))

    for state in _reachable_states(world):
        pending = pending_panels(world, state.panels_ok, state.stations_online)
        needs = material_needs(world, pending)
        weight = state.load_weight(world)

        for action in applicable(world, state):
            assert state.battery >= action.cost, action

            if action.kind == MOVE:
                edge = [e for e in world.corridors[state.zone] if e[0] == action.target]
                assert edge, action
                _, cost, door = edge[0]
                assert action.cost == cost, "el costo sale del escenario"
                assert door is None or door in state.doors_open, "puerta cerrada"

            elif action.kind == PICKUP:
                assert action.cost == world.cost_pickup
                if world.is_material(action.target):
                    assert state.ground_count(action.target, state.zone) > 0
                    assert state.carried_count(action.target) < needs.get(action.target, 0), (
                        "no se llevan mas unidades de las que exigen los paneles pendientes"
                    )
                else:
                    assert (action.target, state.zone) in state.ground_ids
                    assert is_alive(world, action.target, state.doors_open, pending), (
                        "design.md: nunca se recogen objetos muertos"
                    )
                assert weight + world.item_weight.get(action.target, 1) <= world.cargo_capacity

            elif action.kind == DROP:
                assert action.cost == world.cost_drop
                assert weight >= world.cargo_capacity, "design.md: DROP solo con la carga llena"
                if world.is_material(action.target):
                    assert state.carried_count(action.target) > needs.get(action.target, 0), (
                        "design.md: solo se sueltan unidades sobrantes"
                    )
                else:
                    assert action.target in state.carried_ids
                    assert not is_alive(world, action.target, state.doors_open, pending), (
                        "design.md: nunca se relevan objetos vivos"
                    )

            elif action.kind == OPEN_DOOR:
                assert action.cost == world.cost_interact
                assert action.target not in state.doors_open
                assert state.zone in world.door_zones[action.target]
                assert world.door_key[action.target] in state.carried_ids

            elif action.kind == REPAIR:
                assert action.cost == world.cost_interact
                assert action.target in pending, "design.md: solo paneles pendientes de P*"
                assert world.panel_zone[action.target] == state.zone
                assert world.panel_tool[action.target] in state.carried_ids
                assert state.carried_count(action.consumes) > 0

            elif action.kind == ACTIVATE:
                assert action.cost == world.cost_interact
                assert action.target in world.needed_stations, "design.md: solo estaciones de S*"
                assert action.target not in state.stations_online
                assert world.station_zone[action.target] == state.zone
                assert world.station_needs_panels[action.target] <= state.panels_ok
                assert world.station_needs_stations[action.target] <= state.stations_online

            elif action.kind == RECHARGE:
                assert action.cost == world.cost_recharge
                assert world.recharge_zones.get(state.zone) == action.target
                assert state.battery < world.battery_max

            else:
                raise AssertionError("accion no documentada: %s" % action.kind)


def test_result_never_mutates_the_parent_state() -> None:
    """El estado padre sigue vivo en OPEN y en CLOSED: Result no puede tocarlo."""
    world = build_world(load("scenario.json"))

    for state in _reachable_states(world, limit=400):
        snapshot = (
            state.zone,
            state.battery,
            state.carried_ids,
            state.carried_materials,
            state.ground_ids,
            state.ground_materials,
            state.doors_open,
            state.panels_ok,
            state.stations_online,
        )
        for action in applicable(world, state):
            result(world, state, action)
        assert snapshot == (
            state.zone,
            state.battery,
            state.carried_ids,
            state.carried_materials,
            state.ground_ids,
            state.ground_materials,
            state.doors_open,
            state.panels_ok,
            state.stations_online,
        )


def test_states_are_canonical_and_ground_holds_no_dead_objects() -> None:
    """La canonicalizacion ocurre dentro de Result: nada sin canonicalizar sale."""
    world = build_world(load("scenario.json"))

    for state in _reachable_states(world, limit=1500):
        assert list(state.ground_ids) == sorted(state.ground_ids), "suelo ordenado"
        assert list(state.carried_materials) == sorted(state.carried_materials)
        assert list(state.ground_materials) == sorted(state.ground_materials)

        pending = pending_panels(world, state.panels_ok, state.stations_online)
        for item, _zone in state.ground_ids:
            assert is_alive(world, item, state.doors_open, pending), (
                "design.md: los objetos muertos se borran del suelo"
            )

        carried = {i for i, _z in state.ground_ids} & state.carried_ids
        assert not carried, "un objeto no puede estar a la vez en el suelo y en la carga"

        assert state.load_weight(world) <= world.cargo_capacity, "capacidad respetada"


def test_goal_test_is_exactly_the_documented_predicate() -> None:
    """Goal(s) <=> goal.stations_online ⊆ s.stations_online."""
    world = build_world(load("scenario.json"))
    for state in _reachable_states(world, limit=800):
        assert goal_test(world, state) == (world.goal_stations <= state.stations_online)


if __name__ == "__main__":
    test_every_generated_action_matches_the_documented_preconditions()
    test_result_never_mutates_the_parent_state()
    test_states_are_canonical_and_ground_holds_no_dead_objects()
    test_goal_test_is_exactly_the_documented_predicate()
    print("Consistencia design.md <-> codigo: OK")
