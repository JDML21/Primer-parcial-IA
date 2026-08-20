/**
 * Valida el plan del agente contra el ejecutor REAL del banco de pruebas,
 * sin abrir el navegador.
 *
 *   npm run verify:plan                    # usa scenarios/scenario.json
 *   npm run verify:plan -- scenario_alt_routes.json
 *
 * Requiere el backend corriendo en el puerto 8000.
 */
import { applyStep, checkGoal } from '../src/lib/executor'
import type { PlanStep, Scenario, WorldRuntime } from '../src/types'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const name = process.argv[2] ?? 'scenario.json'
const path = resolve(import.meta.dirname, '../../scenarios', name)
const scenario = JSON.parse(readFileSync(path, 'utf-8')) as Scenario

const response = await fetch('http://127.0.0.1:8000/api/solve', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(scenario),
})
const plan = (await response.json()) as {
  solution_found: boolean
  total_cost: number
  steps: PlanStep[]
  message?: string
}

console.log(`escenario: ${name}`)
console.log(`respuesta: ${plan.message ?? ''}`)

if (!plan.solution_found) {
  console.log('FAILURE — el agente no encontró plan; nada que ejecutar.')
  process.exit(plan.steps.length === 0 ? 0 : 1)
}

let runtime: WorldRuntime = {
  robotZone: scenario.robot.start,
  battery: scenario.robot.battery_start,
  energySpent: 0,
  payload: [],
  doors: Object.fromEntries(scenario.doors.map((d) => [d.id, d.state])),
  panels: Object.fromEntries(scenario.panels.map((p) => [p.id, p.state])),
  stations: Object.fromEntries(scenario.stations.map((s) => [s.id, s.state])),
  groundKeys: Object.fromEntries(scenario.keys.map((k) => [k.id, k.zone])),
  groundTools: Object.fromEntries(scenario.tools.map((t) => [t.id, t.zone])),
  groundMaterials: Object.fromEntries(
    scenario.materials.map((m) => [m.type, { type: m.type, count: m.count, zone: m.zone }]),
  ),
  robotPosition: [0, 0.35, 0],
  robotYaw: 0,
} as WorldRuntime

for (const [i, step] of plan.steps.entries()) {
  const outcome = applyStep(scenario, runtime, step)
  if (!outcome.ok) {
    console.error(`PASO ${i + 1} RECHAZADO: ${outcome.message}`)
    process.exit(1)
  }
  runtime = outcome.runtime
}

const reached = checkGoal(scenario, runtime)
console.log(`pasos ejecutados: ${plan.steps.length}`)
console.log(`energía gastada: ${runtime.energySpent} (plan: ${plan.total_cost})`)
console.log(`estaciones: ${JSON.stringify(runtime.stations)}`)
console.log(reached ? 'MISSION COMPLETE — el banco de pruebas acepta el plan.' : 'META NO ALCANZADA')
process.exit(reached && runtime.energySpent === plan.total_cost ? 0 : 1)
