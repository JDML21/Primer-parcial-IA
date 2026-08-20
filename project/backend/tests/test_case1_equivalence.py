"""Caso 1 — Estados equivalentes.

Dos configuraciones físicamente equivalentes producen el MISMO estado lógico
aunque se hayan generado por historias distintas.
"""

from __future__ import annotations

from helpers import load

from agent.problem import PICKUP, Action, result
from agent.state import State, initial_state
from agent.world import build_world


def _state_in_storage(world) -> State:
    """Estado auxiliar: robot en Z2 (donde conviven KEY2, FUSE, CHIP y CABLE)."""
    base = initial_state(world)
    return State(
        zone="Z2",
        battery=base.battery,
        carried_ids=frozenset(),
        carried_materials=(),
        ground_ids=base.ground_ids,
        ground_materials=base.ground_materials,
        doors_open=base.doors_open,
        panels_ok=base.panels_ok,
        stations_online=base.stations_online,
    )


def test_pickup_order_does_not_matter() -> None:
    """PICKUP KEY2 -> FUSE y PICKUP FUSE -> KEY2 son el mismo estado."""
    world = build_world(load("scenario.json"))
    start = _state_in_storage(world)

    pick_key = Action(PICKUP, "KEY2", world.cost_pickup)
    pick_fuse = Action(PICKUP, "FUSE", world.cost_pickup)

    a = result(world, result(world, start, pick_key), pick_fuse)
    b = result(world, result(world, start, pick_fuse), pick_key)

    assert a == b, "el orden de recogida no es informacion fisica"
    assert hash(a) == hash(b), "el hash debe coincidir con la equivalencia fisica"
    assert len({a, b}) == 1, "CLOSED debe verlos como un solo estado"


def test_materials_are_equivalent_by_type() -> None:
    """Las dos unidades de FUSE son intercambiables: no hay ids individuales."""
    world = build_world(load("scenario.json"))
    start = _state_in_storage(world)

    pick_fuse = Action(PICKUP, "FUSE", world.cost_pickup)
    carrying = result(world, start, pick_fuse)

    assert carrying.carried_materials == (("FUSE", 1),), carrying.carried_materials
    for slot, count in carrying.ground_materials:
        assert isinstance(count, int)


def test_state_is_hashable_and_usable_as_closed_key() -> None:
    world = build_world(load("scenario.json"))
    start = initial_state(world)
    closed = {start.world_key(): [(start.battery, 0)]}
    assert start.world_key() in closed


if __name__ == "__main__":
    test_pickup_order_does_not_matter()
    test_materials_are_equivalent_by_type()
    test_state_is_hashable_and_usable_as_closed_key()
    print("Caso 1 (estados equivalentes): OK")
