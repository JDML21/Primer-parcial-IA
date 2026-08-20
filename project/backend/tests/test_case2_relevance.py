"""Caso 2 — Información relevante.

Dos configuraciones que difieren en algo capaz de cambiar las acciones futuras
deben permanecer como estados DISTINTOS.
"""

from __future__ import annotations

import dataclasses

from helpers import load

from agent.problem import OPEN_DOOR, PICKUP, Action, applicable, result
from agent.state import initial_state
from agent.world import build_world


def test_battery_distinguishes_states() -> None:
    """Misma zona y misma carga, distinta batería => estados distintos.

    Y la diferencia es real: con bateria insuficiente el MOVE caro desaparece
    del conjunto de acciones aplicables.
    """
    world = build_world(load("scenario.json"))
    full = initial_state(world)
    drained = dataclasses.replace(full, battery=5)

    assert full != drained, "la bateria es parte de la situacion fisica"
    assert full.world_key() == drained.world_key(), (
        "pero la configuracion del mundo es la misma: eso es lo que permite "
        "la poda por dominancia"
    )

    moves_full = [a.target for a in applicable(world, full) if a.kind == "MOVE"]
    moves_drained = [a.target for a in applicable(world, drained) if a.kind == "MOVE"]
    assert moves_full != moves_drained, "menos bateria => menos acciones legales"
    assert moves_drained == [], moves_drained


def test_open_door_changes_the_state_and_the_future() -> None:
    """Una puerta abierta cambia el estado y habilita corredores."""
    world = build_world(load("scenario.json"))
    start = initial_state(world)

    with_key = result(world, start, Action(PICKUP, "KEY1", world.cost_pickup))
    opened = result(world, with_key, Action(OPEN_DOOR, "DOOR1", world.cost_interact))

    assert with_key != opened
    assert "DOOR1" not in with_key.doors_open and "DOOR1" in opened.doors_open

    before = {a.target for a in applicable(world, with_key) if a.kind == "MOVE"}
    after = {a.target for a in applicable(world, opened) if a.kind == "MOVE"}
    assert "Z2" not in before, "con DOOR1 cerrada no se puede cruzar a Z2"
    assert "Z2" in after, "abrirla habilita el corredor"


def test_carrying_a_tool_changes_the_future() -> None:
    """Llevar la herramienta o no llevarla no es el mismo estado."""
    world = build_world(load("scenario.json"))
    start = initial_state(world)
    with_key = result(world, start, Action(PICKUP, "KEY1", world.cost_pickup))

    assert start != with_key
    assert start.carried_ids != with_key.carried_ids


if __name__ == "__main__":
    test_battery_distinguishes_states()
    test_open_door_changes_the_state_and_the_future()
    test_carrying_a_tool_changes_the_future()
    print("Caso 2 (informacion relevante): OK")
