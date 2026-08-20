"""Formulación del problema: acciones internas, `Applicable`, `Result` y `Goal`.

`Applicable` es MÁS ESTRICTO que el simulador a propósito: solo genera
acciones que un plan de costo mínimo podría necesitar (ver la justificación
de no pérdida del óptimo en `project/design.md`).

    legal según el simulador  ≠  relevante para buscar
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

from .state import State, canonical, is_alive, material_needs, pending_panels
from .world import World

MOVE = "MOVE"
PICKUP = "PICKUP"
DROP = "DROP"
OPEN_DOOR = "OPEN_DOOR"
REPAIR = "REPAIR"
ACTIVATE = "ACTIVATE"
RECHARGE = "RECHARGE"


@dataclass(frozen=True)
class Action:
    """Acción interna del agente. La traducción visual ocurre en translate.py."""

    kind: str
    target: str
    cost: int
    consumes: Optional[str] = None
    frm: Optional[str] = None


def applicable(world: World, s: State, allow_live_drops: bool = False) -> Iterator[Action]:
    """Sucesores relevantes. Toda acción exige además `battery >= cost`.

    `allow_live_drops=False` (por defecto) es la formulación del agente: solo se
    sueltan objetos que ya no sirven. `True` abre el espacio a los relevos de
    objetos vivos, que el contrato permite pero hacen inviable la búsqueda; se
    usa en las pruebas para medir qué cuesta esa restricción.
    """
    pending = pending_panels(world, s.panels_ok, s.stations_online)
    needs = material_needs(world, pending)
    weight = s.load_weight(world)
    capacity = world.cargo_capacity

    for neighbour, cost, door in world.corridors.get(s.zone, ()):
        if door is not None and door not in s.doors_open:
            continue
        if s.battery >= cost:
            yield Action(MOVE, neighbour, cost, frm=s.zone)

    if s.battery >= world.cost_pickup:
        for item, zone in s.ground_ids:
            if zone != s.zone:
                continue
            if weight + world.item_weight.get(item, 1) <= capacity:
                yield Action(PICKUP, item, world.cost_pickup)

        for (mtype, zone), count in s.ground_materials:
            if zone != s.zone or count <= 0:
                continue
            if s.carried_count(mtype) >= needs.get(mtype, 0):
                continue
            if weight + world.item_weight.get(mtype, 1) <= capacity:
                yield Action(PICKUP, mtype, world.cost_pickup)

    if s.battery >= world.cost_drop and weight >= capacity and _blocked_pickup_here(world, s, needs):
        for item in sorted(s.carried_ids):
            if allow_live_drops or not is_alive(world, item, s.doors_open, pending):
                yield Action(DROP, item, world.cost_drop)
        for mtype, count in s.carried_materials:
            if allow_live_drops or count > needs.get(mtype, 0):
                yield Action(DROP, mtype, world.cost_drop)

    if s.battery >= world.cost_interact:
        for door, (a, b) in world.door_zones.items():
            if door in s.doors_open:
                continue
            if s.zone != a and s.zone != b:
                continue
            if world.door_key.get(door) in s.carried_ids:
                yield Action(OPEN_DOOR, door, world.cost_interact)

    if s.battery >= world.cost_interact:
        for panel in sorted(pending):
            if world.panel_zone.get(panel) != s.zone:
                continue
            if world.panel_tool.get(panel) not in s.carried_ids:
                continue
            mtype = world.panel_material.get(panel)
            if s.carried_count(mtype) <= 0:
                continue
            yield Action(REPAIR, panel, world.cost_interact, consumes=mtype)

    if s.battery >= world.cost_interact:
        for station in sorted(world.needed_stations):
            if station in s.stations_online:
                continue
            if world.station_zone.get(station) != s.zone:
                continue
            if not world.station_needs_panels.get(station, frozenset()) <= s.panels_ok:
                continue
            if not world.station_needs_stations.get(station, frozenset()) <= s.stations_online:
                continue
            yield Action(ACTIVATE, station, world.cost_interact)

    charger = world.recharge_zones.get(s.zone)
    if charger is not None and s.battery < world.battery_max and s.battery >= world.cost_recharge:
        yield Action(RECHARGE, charger, world.cost_recharge)


def _blocked_pickup_here(world: World, s: State, needs) -> bool:
    """¿Hay en esta zona algo útil que solo la capacidad impide recoger?"""
    for item, zone in s.ground_ids:
        if zone == s.zone:
            return True
    for (mtype, zone), count in s.ground_materials:
        if zone == s.zone and count > 0 and s.carried_count(mtype) < needs.get(mtype, 0):
            return True
    return False


def result(world: World, s: State, a: Action) -> State:
    """Transición determinista s --a--> s', devolviendo un estado canónico.

    Nunca muta `s`: el estado padre sigue vivo en OPEN y en CLOSED.
    """
    battery = s.battery - a.cost

    zone = s.zone
    carried_ids = s.carried_ids
    carried_materials = s.carried_materials
    ground_ids = s.ground_ids
    ground_materials = s.ground_materials
    doors_open = s.doors_open
    panels_ok = s.panels_ok
    stations_online = s.stations_online

    if a.kind == MOVE:
        zone = a.target

    elif a.kind == PICKUP:
        if world.is_material(a.target):
            ground_materials = _bag_add(ground_materials, (a.target, s.zone), -1)
            carried_materials = _materials_add(carried_materials, a.target, +1)
        else:
            ground_ids = tuple(pair for pair in ground_ids if pair[0] != a.target)
            carried_ids = carried_ids | {a.target}

    elif a.kind == DROP:
        if world.is_material(a.target):
            carried_materials = _materials_add(carried_materials, a.target, -1)
            ground_materials = _bag_add(ground_materials, (a.target, s.zone), +1)
        else:
            carried_ids = carried_ids - {a.target}
            ground_ids = tuple(sorted(ground_ids + ((a.target, s.zone),)))

    elif a.kind == OPEN_DOOR:
        doors_open = doors_open | {a.target}

    elif a.kind == REPAIR:
        panels_ok = panels_ok | {a.target}
        carried_materials = _materials_add(carried_materials, a.consumes, -1)

    elif a.kind == ACTIVATE:
        stations_online = stations_online | {a.target}

    elif a.kind == RECHARGE:
        battery = world.battery_max

    else:
        raise ValueError("unknown action kind {}".format(a.kind))

    return canonical(
        world,
        State(
            zone=zone,
            battery=battery,
            carried_ids=carried_ids,
            carried_materials=carried_materials,
            ground_ids=ground_ids,
            ground_materials=ground_materials,
            doors_open=doors_open,
            panels_ok=panels_ok,
            stations_online=stations_online,
        ),
    )


def goal_test(world: World, s: State) -> bool:
    """Goal(s) ⟺ goal.stations_online ⊆ s.stations_online.

    Se verifica sobre el estado final del mundo, no sobre haber ejecutado una
    lista de tareas.
    """
    return world.goal_stations <= s.stations_online


def _materials_add(bag, mtype: str, delta: int):
    items = dict(bag)
    items[mtype] = items.get(mtype, 0) + delta
    if items[mtype] <= 0:
        del items[mtype]
    return tuple(sorted(items.items()))


def _bag_add(bag, slot: Tuple[str, str], delta: int):
    items = dict(bag)
    items[slot] = items.get(slot, 0) + delta
    if items[slot] <= 0:
        del items[slot]
    return tuple(sorted(items.items()))
