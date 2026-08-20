# Emergency Control — Planificador autónomo

Agente de búsqueda que resuelve la misión del parcial: restaurar las estaciones
críticas de la instalación con el **plan de menor costo**.

El diseño de IA —estado, acciones, transición, meta, costo y estrategia— está en
[`design.md`](design.md), escrito antes de implementar. El enunciado está en el
`README.MD` de la raíz y las reglas del mundo en [`../CONTRATO.md`](../CONTRATO.md).

```text
project/
├── frontend/          # React + R3F — simulación 3D (entregado por el profesor)
├── backend/
│   ├── src/
│   │   ├── agent/     # el agente: World, State, Applicable/Result, UCS, traducción
│   │   ├── main.py    # FastAPI — POST /api/solve
│   │   ├── simulator.py   # reglas del mundo, usado como validador en los tests
│   │   └── demo_plan.py   # plan artesanal original, ya no lo usa /api/solve
│   └── tests/         # los cinco casos del Entregable 3
├── scenarios/         # scenario.json (fuente de verdad) + instancias de prueba
├── design.md
└── README.md
```

---

## 1. Instalar dependencias

Se necesita **Python 3.9+** y **Node 18+**. Dos terminales.

### Backend

```bash
cd project/backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd project/frontend
npm install
```

---

## 2. Iniciar el backend

```bash
cd project/backend
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uvicorn main:app --app-dir src --port 8000
```

Comprobar: <http://127.0.0.1:8000/api/health> devuelve `{"status":"ok"}`.

## 3. Iniciar el frontend

```bash
cd project/frontend
npm run dev
```

Abrir <http://localhost:5173>. Vite redirige `/api` al puerto 8000.

## 4. Ejecutar el agente

En la interfaz, pulsar **EXECUTE PLAN**. El frontend envía el escenario a
`POST /api/solve`, recibe el plan y lo **re-ejecuta paso a paso contra su propio
simulador**: no confía en el plan, así que cualquier paso ilegal aparecería como
error en el log.

Sin interfaz, directamente contra la API:

```bash
curl -s -X POST http://127.0.0.1:8000/api/solve \
  -H 'Content-Type: application/json' \
  -d @project/scenarios/scenario.json
```

Respuesta sobre la instancia demo: `solution_found: true`, **33 pasos**,
**costo total 88**.

## 5. Probar una misión

El escenario es la **fuente de verdad**: el agente no tiene nada codificado de la
instancia demo. Para probar otra misión basta con enviar otro JSON con la misma
estructura. En `scenarios/` hay tres instancias de validación:

| Escenario | Para qué sirve | Resultado |
|---|---|---|
| `scenario.json` | misión del enunciado | plan de 33 pasos, costo 88 |
| `scenario_cost_vs_steps.json` | separar pasos de costo | 3 pasos y costo 12, frente a 2 pasos y costo 22 |
| `scenario_alt_routes.json` | dos rutas a la misma configuración | costo 8 por la ruta barata |
| `scenario_no_solution.json` | misión imposible | `solution_found: false`, `steps: []` |

```bash
curl -s -X POST http://127.0.0.1:8000/api/solve \
  -H 'Content-Type: application/json' \
  -d @project/scenarios/scenario_no_solution.json
```

### Validar el plan contra el banco de pruebas, sin navegador

El frontend no confía en el plan: lo re-ejecuta con su propio simulador. Ese
mismo ejecutor (`src/lib/executor.ts`) se puede correr desde la terminal, con el
backend levantado:

```bash
cd project/frontend
npm run verify:plan                                  # scenario.json
npm run verify:plan -- scenario_no_solution.json     # caso FAILURE
```

Salida esperada en la instancia demo: 33 pasos, energía 88 y
`MISSION COMPLETE — el banco de pruebas acepta el plan.`

### Tests

```bash
cd project/backend
python3 tests/run_all.py
```

Ejecuta los cinco casos del Entregable 3 más la auditoría del plan contra el
contrato. Cada archivo también corre suelto: `python3 tests/test_case4_failure.py`.

---

## 6. Interpretar el resultado

La respuesta de `/api/solve` sigue el contrato:

```json
{
  "solution_found": true,
  "total_cost": 88,
  "steps": [ { "op": "PICKUP", "item": "KEY1", "cost": 1 } ],
  "message": "Optimal plan found by uniform-cost search: 33 steps, cost 88 (38751 states expanded, 109238 generated)."
}
```

- **`solution_found: false` con `steps: []`** es el caso `FAILURE`: la frontera
  se vació sin encontrar meta, es decir, **se demostró que no existe plan** bajo
  la formulación del agente. Es distinto de agotar la cota de nodos, que el
  `message` reporta explícitamente como `Search aborted`.
- **`total_cost`** es el `g(n)` del nodo meta, no una suma recalculada aparte, y
  coincide con la energía que gasta el robot al ejecutar el plan.
- **`message`** trae los nodos expandidos y generados, que es la medida honesta
  de cuánto costó la búsqueda.

En la interfaz:

- **POWER CORE** — batería restante; baja con cada acción según su costo y vuelve
  al máximo con `RECHARGE`.
- **PAYLOAD** — los `cargo_capacity` espacios de carga. Cuando se llenan, el
  agente suelta lo que ya no sirve: ahí se ven los `DROP`.
- **ENERGY COST** — energía acumulada frente al costo total del plan.
- **EXECUTION LOG** — cada paso con su `op` y, en los `INTERACT`, su `action`.
  Un paso rechazado indica la razón exacta (puerta cerrada, batería insuficiente,
  material faltante).
- **MISSION COMPLETE** al final significa que las estaciones de `goal` quedaron
  `ONLINE` en el estado final del mundo, que es como se verifica la meta.

---

## Qué hace el agente por dentro

```text
scenario.json → World (índices + clausura de la meta S*, P*)
              → State inicial canónico
              → UCS: Applicable → Result → CLOSED con dominancia de batería
              → plan de acciones internas
              → translate.py → 4 operaciones del contrato
              → /api/solve
```

Las cuatro operaciones visuales (`MOVE`, `PICKUP`, `DROP`, `INTERACT`) son la
**única** frontera con el frontend, y va en un solo sentido: la búsqueda no sabe
que existe una interfaz. Las acciones internas del agente —`OPEN_DOOR`, `REPAIR`,
`ACTIVATE`, `RECHARGE`— se traducen a valores del campo `action` dentro de un
paso `INTERACT`, nunca a un `op`.

El detalle de por qué el estado es ese, por qué `DROP` se restringe y qué
garantías tiene UCS aquí está en [`design.md`](design.md).
