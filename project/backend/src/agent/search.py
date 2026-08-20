"""Uniform-Cost Search (Graph Search) con CLOSED canónico y dominancia de batería.

  * frontera: heap por g(n);
  * goal test AL EXTRAER (no al generar) -> optimalidad;
  * CLOSED indexado por `state.world_key()` guardando el frente de pares
    (batería, g) no dominados, con borrado perezoso: el nodo se contrasta
    contra CLOSED después de salir del heap;
  * costos > 0 y espacio finito -> completitud y terminación (FAILURE).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Dict, List, Optional, Tuple

from .problem import Action, applicable, goal_test, result
from .state import State, initial_state
from .world import World


@dataclass
class Node:
    """Historial de búsqueda: NO es el estado físico."""

    state: State
    g: int
    parent: Optional["Node"] = None
    action: Optional[Action] = None


@dataclass
class SearchResult:
    found: bool
    plan: List[Action] = field(default_factory=list)
    cost: int = 0
    expanded: int = 0
    generated: int = 0
    aborted: bool = False   # se alcanzó la cota de nodos, no es un FAILURE legítimo


def _dominated(closed: Dict[Tuple, List[Tuple[int, int]]], node: Node) -> bool:
    """¿Existe ya un camino a esta misma configuración con >= batería y <= costo?"""
    for battery, g in closed.get(node.state.world_key(), ()):
        if battery >= node.state.battery and g <= node.g:
            return True
    return False


def _register(closed: Dict[Tuple, List[Tuple[int, int]]], node: Node) -> None:
    """Guarda el nodo en el frente de Pareto, descartando lo que él domina."""
    key = node.state.world_key()
    frontier = [
        (battery, g)
        for battery, g in closed.get(key, ())
        if not (node.state.battery >= battery and node.g <= g)
    ]
    frontier.append((node.state.battery, node.g))
    closed[key] = frontier


def uniform_cost_search(
    world: World, max_nodes: int = 500_000, allow_live_drops: bool = False
) -> SearchResult:
    """UCS sobre el problema definido en problem.py.

    `max_nodes` es una salvaguarda de examen: el enunciado prohíbe quedar
    atrapado explorando indefinidamente. En una instancia bien formulada no se
    alcanza; si se alcanza, se reporta como `aborted`, que NO es lo mismo que
    demostrar que no hay solución.
    """
    root = Node(initial_state(world), 0)

    tiebreaker = itertools.count()
    # (g, contador, nodo): el contador evita que el heap compare estados, que
    # definen == y hash pero no un orden total.
    open_heap: List[Tuple[int, int, Node]] = [(0, next(tiebreaker), root)]
    closed: Dict[Tuple, List[Tuple[int, int]]] = {}

    expanded = 0
    generated = 1

    while open_heap:
        g, _, node = heappop(open_heap)

        if goal_test(world, node.state):
            return SearchResult(True, reconstruct(node), g, expanded, generated)

        if _dominated(closed, node):
            continue
        _register(closed, node)

        expanded += 1
        if expanded > max_nodes:
            return SearchResult(False, [], 0, expanded, generated, aborted=True)

        for action in applicable(world, node.state, allow_live_drops):
            child = Node(
                state=result(world, node.state, action),
                g=g + action.cost,
                parent=node,
                action=action,
            )
            heappush(open_heap, (child.g, next(tiebreaker), child))
            generated += 1

    return SearchResult(False, [], 0, expanded, generated)


def reconstruct(node: Node) -> List[Action]:
    """Del nodo meta hacia atrás por `parent` hasta la raíz."""
    plan: List[Action] = []
    cursor: Optional[Node] = node
    while cursor is not None and cursor.action is not None:
        plan.append(cursor.action)
        cursor = cursor.parent
    plan.reverse()
    return plan
