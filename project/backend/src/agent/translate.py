"""Traducción: acciones INTERNAS del agente -> contrato cerrado del frontend.

Solo existen 4 `op`: MOVE | PICKUP | DROP | INTERACT.
OPEN_DOOR / REPAIR / ACTIVATE / RECHARGE son valores del campo `action`
dentro de un paso INTERACT (ver CONTRATO.md §3).

La capa visual no determina la lógica del agente: esta es la única frontera, y
va en un solo sentido. La búsqueda no sabe que existe un frontend.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .problem import ACTIVATE, DROP, MOVE, OPEN_DOOR, PICKUP, RECHARGE, REPAIR, Action
from .world import World


def to_contract_steps(world: World, plan: List[Action]) -> List[Dict[str, Any]]:
    """Cada acción interna -> un paso del contrato, con su costo oficial."""
    steps: List[Dict[str, Any]] = []

    for action in plan:
        if action.kind == MOVE:
            steps.append(
                {"op": "MOVE", "from": action.frm, "to": action.target, "cost": action.cost}
            )
        elif action.kind == PICKUP:
            steps.append({"op": "PICKUP", "item": action.target, "cost": action.cost})
        elif action.kind == DROP:
            steps.append({"op": "DROP", "item": action.target, "cost": action.cost})
        elif action.kind == REPAIR:
            steps.append(
                {
                    "op": "INTERACT",
                    "target": action.target,
                    "action": REPAIR,
                    "consumes": action.consumes,
                    "cost": action.cost,
                }
            )
        elif action.kind in (OPEN_DOOR, ACTIVATE, RECHARGE):
            steps.append(
                {
                    "op": "INTERACT",
                    "target": action.target,
                    "action": action.kind,
                    "cost": action.cost,
                }
            )
        else:
            raise ValueError("cannot translate internal action {}".format(action.kind))

    return steps
