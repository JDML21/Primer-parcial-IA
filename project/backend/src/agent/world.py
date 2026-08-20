"""Constantes inmutables del escenario (NO forman parte del estado).

Todo lo que se puede derivar del `scenario.json` y nunca cambia durante la
búsqueda vive aquí: grafo de corredores, pesos, requisitos de paneles y
estaciones, costos oficiales y la clausura de la meta. El `State` solo guarda
lo que varía.

El escenario es la fuente de verdad: aquí no hay ningún id, costo ni cantidad
hardcodeado de la instancia demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


@dataclass(frozen=True)
class World:
    """Vista indexada e inmutable del escenario."""

    raw: Dict[str, Any]

    start_zone: str
    battery_max: int
    cargo_capacity: int

    cost_pickup: int
    cost_drop: int
    cost_interact: int
    cost_recharge: int

    zones: Tuple[str, ...]
    corridors: Dict[str, Tuple[Tuple[str, int, Optional[str]], ...]]
    door_key: Dict[str, str]
    door_zones: Dict[str, Tuple[str, str]]
    key_door: Dict[str, str]
    item_weight: Dict[str, int]
    panel_zone: Dict[str, str]
    panel_tool: Dict[str, str]
    panel_material: Dict[str, str]
    station_zone: Dict[str, str]
    station_needs_panels: Dict[str, FrozenSet[str]]
    station_needs_stations: Dict[str, FrozenSet[str]]
    recharge_zones: Dict[str, str]
    goal_stations: FrozenSet[str]

    needed_stations: FrozenSet[str]
    needed_panels: FrozenSet[str]

    battery_start: int
    doors_open_start: FrozenSet[str]
    panels_ok_start: FrozenSet[str]
    stations_online_start: FrozenSet[str]
    keys_start: Dict[str, str]
    tools_start: Dict[str, str]
    materials_start: Dict[Tuple[str, str], int]
    material_type_set: FrozenSet[str]

    def corridor_cost(self, frm: str, to: str) -> int:
        """Costo oficial del corredor frm->to."""
        for neighbour, cost, _door in self.corridors.get(frm, ()):
            if neighbour == to:
                return cost
        raise KeyError("no corridor {}->{}".format(frm, to))

    def tool_for(self, panel: str) -> str:
        return self.panel_tool[panel]

    def material_for(self, panel: str) -> str:
        return self.panel_material[panel]

    def is_key(self, item: str) -> bool:
        return item in self.key_door

    def is_tool(self, item: str) -> bool:
        return item in self.tools_start

    def is_material(self, item: str) -> bool:
        return item in self.material_type_set


def _goal_closure(
    goal_stations: FrozenSet[str],
    needs_stations: Dict[str, FrozenSet[str]],
    needs_panels: Dict[str, FrozenSet[str]],
) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """S* = meta + dependencias transitivas entre estaciones. P* = sus paneles.

    Lo que quede fuera es decorado: ninguna acción sobre ello acerca a la meta.
    """
    pending: List[str] = list(goal_stations)
    reached = set()
    while pending:
        station = pending.pop()
        if station in reached:
            continue
        reached.add(station)
        for dependency in needs_stations.get(station, frozenset()):
            if dependency not in reached:
                pending.append(dependency)

    panels = set()
    for station in reached:
        panels |= set(needs_panels.get(station, frozenset()))
    return frozenset(reached), frozenset(panels)


def build_world(scenario: Dict[str, Any]) -> World:
    """Parsea el escenario. Solo lectura: nada de esto cambia durante la búsqueda."""
    robot = scenario["robot"]
    costs = scenario.get("action_costs", {})

    cost_pickup = int(costs.get("pickup", 1))
    cost_drop = int(costs.get("drop", 1))
    cost_interact = int(costs.get("interact", 2))
    cost_recharge = int(costs.get("recharge", 3))
    for name, value in (
        ("pickup", cost_pickup),
        ("drop", cost_drop),
        ("interact", cost_interact),
        ("recharge", cost_recharge),
    ):
        if value < 0:
            raise ValueError("action_costs.{} is negative: UCS loses optimality".format(name))

    adjacency: Dict[str, List[Tuple[str, int, Optional[str]]]] = {}
    for corridor in scenario.get("corridors", []):
        cost = int(corridor["cost"])
        if cost < 0:
            raise ValueError(
                "corridor {}->{} has negative cost".format(corridor["from"], corridor["to"])
            )
        adjacency.setdefault(corridor["from"], []).append(
            (corridor["to"], cost, corridor.get("door"))
        )
    corridors = {zone: tuple(sorted(edges)) for zone, edges in adjacency.items()}

    door_key: Dict[str, str] = {}
    door_zones: Dict[str, Tuple[str, str]] = {}
    key_door: Dict[str, str] = {}
    doors_open_start = set()
    for door in scenario.get("doors", []):
        door_key[door["id"]] = door["key"]
        key_door[door["key"]] = door["id"]
        a, b = door["between"]
        door_zones[door["id"]] = (a, b)
        if door.get("state") == "OPEN":
            doors_open_start.add(door["id"])

    item_weight: Dict[str, int] = {}
    keys_start: Dict[str, str] = {}
    for key in scenario.get("keys", []):
        keys_start[key["id"]] = key["zone"]
        item_weight[key["id"]] = int(key.get("weight", 1))

    tools_start: Dict[str, str] = {}
    for tool in scenario.get("tools", []):
        tools_start[tool["id"]] = tool["zone"]
        item_weight[tool["id"]] = int(tool.get("weight", 1))

    materials_start: Dict[Tuple[str, str], int] = {}
    for material in scenario.get("materials", []):
        slot = (material["type"], material["zone"])
        materials_start[slot] = materials_start.get(slot, 0) + int(material.get("count", 1))
        item_weight[material["type"]] = int(material.get("weight", 1))

    panel_zone: Dict[str, str] = {}
    panel_tool: Dict[str, str] = {}
    panel_material: Dict[str, str] = {}
    panels_ok_start = set()
    for panel in scenario.get("panels", []):
        panel_zone[panel["id"]] = panel["zone"]
        requires = panel.get("requires", {})
        panel_tool[panel["id"]] = requires.get("tool")
        panel_material[panel["id"]] = requires.get("material")
        if panel.get("state") == "OK":
            panels_ok_start.add(panel["id"])

    station_zone: Dict[str, str] = {}
    station_needs_panels: Dict[str, FrozenSet[str]] = {}
    station_needs_stations: Dict[str, FrozenSet[str]] = {}
    stations_online_start = set()
    for station in scenario.get("stations", []):
        station_zone[station["id"]] = station["zone"]
        requires = station.get("requires", {})
        station_needs_panels[station["id"]] = frozenset(requires.get("panels_ok", []))
        station_needs_stations[station["id"]] = frozenset(requires.get("stations_online", []))
        if station.get("state") == "ONLINE":
            stations_online_start.add(station["id"])

    recharge_zones: Dict[str, str] = {}
    for charger in scenario.get("chargers", []):
        recharge_zones[charger["zone"]] = charger["id"]

    goal_stations = frozenset(scenario.get("goal", {}).get("stations_online", []))
    needed_stations, needed_panels = _goal_closure(
        goal_stations, station_needs_stations, station_needs_panels
    )

    return World(
        raw=scenario,
        start_zone=robot["start"],
        battery_max=int(robot["battery_max"]),
        cargo_capacity=int(robot["cargo_capacity"]),
        cost_pickup=cost_pickup,
        cost_drop=cost_drop,
        cost_interact=cost_interact,
        cost_recharge=cost_recharge,
        zones=tuple(z["id"] for z in scenario.get("zones", [])),
        corridors=corridors,
        door_key=door_key,
        door_zones=door_zones,
        key_door=key_door,
        item_weight=item_weight,
        panel_zone=panel_zone,
        panel_tool=panel_tool,
        panel_material=panel_material,
        station_zone=station_zone,
        station_needs_panels=station_needs_panels,
        station_needs_stations=station_needs_stations,
        recharge_zones=recharge_zones,
        goal_stations=goal_stations,
        needed_stations=needed_stations,
        needed_panels=needed_panels,
        battery_start=int(robot["battery_start"]),
        doors_open_start=frozenset(doors_open_start),
        panels_ok_start=frozenset(panels_ok_start),
        stations_online_start=frozenset(stations_online_start),
        keys_start=keys_start,
        tools_start=tools_start,
        materials_start=materials_start,
        material_type_set=frozenset(t for (t, _z) in materials_start),
    )
