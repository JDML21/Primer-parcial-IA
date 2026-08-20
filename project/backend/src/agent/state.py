"""Estado del agente: s = ⟨zona, batería, carga, suelo, puertas, paneles, estaciones⟩.

Reglas de diseño (ver `project/design.md`):
  * inmutable y hasheable -> `frozen=True`, estructuras canónicas;
  * materiales por TIPO, nunca por id individual;
  * los objetos muertos se borran del SUELO, que es donde vive la explosión
    combinatoria (dónde quedó cada objeto);
  * en la CARGA se conserva el id aunque el objeto esté muerto: el contrato
    exige nombrar el objeto al soltarlo (`{"op":"DROP","item":"KEY1"}`), y la
    carga está acotada por `cargo_capacity`, así que no hay explosión;
  * `g(n)`, padre y acción NO viven aquí: viven en el Nodo de búsqueda.

`State` define `==` y `hash` pero deliberadamente NO un orden total: el heap de
`search.py` desempata con un contador, nunca comparando estados.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple

from .world import World

# carga de materiales: tupla ordenada ((tipo, count), ...) para hash estable
MaterialBag = Tuple[Tuple[str, int], ...]
# suelo de materiales: tupla ordenada (((tipo, zona), count), ...)
GroundMaterials = Tuple[Tuple[Tuple[str, str], int], ...]


@dataclass(frozen=True)
class State:
    zone: str
    battery: int

    # --- carga ---
    carried_ids: FrozenSet[str]      # llaves y herramientas (vivas o ya inútiles)
    carried_materials: MaterialBag   # materiales por tipo

    # --- suelo (solo objetos vivos) ---
    ground_ids: Tuple[Tuple[str, str], ...]   # ((item_id, zona), ...) ordenado
    ground_materials: GroundMaterials

    # --- entorno persistente ---
    doors_open: FrozenSet[str]
    panels_ok: FrozenSet[str]
    stations_online: FrozenSet[str]

    # ------------------------------------------------------------------
    def load_weight(self, world: World) -> int:
        """Peso total de la carga. DERIVADO: no es variable de estado."""
        total = sum(world.item_weight.get(item, 1) for item in self.carried_ids)
        for mtype, count in self.carried_materials:
            total += world.item_weight.get(mtype, 1) * count
        return total

    def carried_count(self, mtype: str) -> int:
        for candidate, count in self.carried_materials:
            if candidate == mtype:
                return count
        return 0

    def ground_count(self, mtype: str, zone: str) -> int:
        for (candidate, candidate_zone), count in self.ground_materials:
            if candidate == mtype and candidate_zone == zone:
                return count
        return 0

    def world_key(self) -> Tuple:
        """Configuración del mundo SIN batería.

        Clave de CLOSED para la poda por dominancia: misma configuración y más
        batería a costo menor o igual => el otro nodo está dominado.
        """
        return (
            self.zone,
            self.carried_ids,
            self.carried_materials,
            self.ground_ids,
            self.ground_materials,
            self.doors_open,
            self.panels_ok,
            self.stations_online,
        )


# ----------------------------------------------------------------------
# Relevancia: qué sigue vivo dado el entorno y la clausura de la meta
# ----------------------------------------------------------------------
def pending_panels(
    world: World, panels_ok: FrozenSet[str], stations_online: FrozenSet[str]
) -> FrozenSet[str]:
    """Paneles que todavía hay que reparar para alcanzar la meta.

    Un panel cuenta solo si (a) está en la clausura P*, (b) sigue dañado y
    (c) alguna estación de S* que aún está OFFLINE lo exige. Un panel que solo
    servía a una estación ya activada deja de importar.
    """
    pending = set()
    for station in world.needed_stations:
        if station in stations_online:
            continue
        for panel in world.station_needs_panels.get(station, frozenset()):
            if panel not in panels_ok:
                pending.add(panel)
    return frozenset(pending)


def material_needs(world: World, pending: FrozenSet[str]) -> Dict[str, int]:
    """necesarios(M) = cuántas unidades de M exigen los paneles pendientes."""
    needs: Dict[str, int] = {}
    for panel in pending:
        mtype = world.panel_material.get(panel)
        if mtype is not None:
            needs[mtype] = needs.get(mtype, 0) + 1
    return needs


def is_alive(world: World, item: str, doors_open: FrozenSet[str], pending: FrozenSet[str]) -> bool:
    """Una llave vive mientras su puerta esté cerrada; una herramienta, mientras
    quede un panel pendiente que la exija."""
    door = world.key_door.get(item)
    if door is not None:
        return door not in doors_open
    return any(world.panel_tool.get(panel) == item for panel in pending)


# ----------------------------------------------------------------------
def canonical(world: World, state: State) -> State:
    """Ordena las estructuras y borra del suelo lo que ya no sirve.

    Se llama al final de cada `Result`, de modo que ningún estado no canónico
    llega nunca a OPEN ni a CLOSED. Un objeto muerto en el suelo no habilita
    ninguna acción futura (el entorno es monótono), así que su posición deja de
    distinguir estados: mantenerlo multiplicaría el espacio por |zonas| por cada
    objeto muerto.
    """
    pending = pending_panels(world, state.panels_ok, state.stations_online)
    needs = material_needs(world, pending)

    ground_ids = tuple(
        sorted(
            (item, zone)
            for item, zone in state.ground_ids
            if is_alive(world, item, state.doors_open, pending)
        )
    )

    ground_materials = []
    for (mtype, zone), count in state.ground_materials:
        # nunca hace falta más de `necesarios(M)` unidades desde una misma zona
        keep = min(count, needs.get(mtype, 0))
        if keep > 0:
            ground_materials.append(((mtype, zone), keep))

    carried_materials = tuple(
        sorted((mtype, count) for mtype, count in state.carried_materials if count > 0)
    )

    return State(
        zone=state.zone,
        battery=state.battery,
        carried_ids=state.carried_ids,
        carried_materials=carried_materials,
        ground_ids=ground_ids,
        ground_materials=tuple(sorted(ground_materials)),
        doors_open=state.doors_open,
        panels_ok=state.panels_ok,
        stations_online=state.stations_online,
    )


def initial_state(world: World) -> State:
    """Estado inicial ya canonicalizado."""
    ground_ids = []
    for key_id, zone in world.keys_start.items():
        ground_ids.append((key_id, zone))
    for tool_id, zone in world.tools_start.items():
        ground_ids.append((tool_id, zone))

    raw = State(
        zone=world.start_zone,
        battery=world.battery_start,
        carried_ids=frozenset(),
        carried_materials=(),
        ground_ids=tuple(sorted(ground_ids)),
        ground_materials=tuple(sorted(world.materials_start.items())),
        doors_open=world.doors_open_start,
        panels_ok=world.panels_ok_start,
        stations_online=world.stations_online_start,
    )
    return canonical(world, raw)
