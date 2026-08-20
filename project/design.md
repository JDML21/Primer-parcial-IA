# Diseño del agente — Emergency Control

Autor: Jose Marmolejo
Curso: Fundamentos de Inteligencia Artificial — Primer Parcial

Clasifico el entorno como **totalmente observable, determinista, secuencial,
estático, discreto y de agente único**. Bajo esas propiedades el agente no
necesita percibir durante la ejecución ni replanificar: puede calcular de
antemano un **plan completo** desde el estado inicial, y el marco correcto es
la **búsqueda clásica en grafos** (AIMA cap. 3). Por eso todo el diseño que
sigue es una formulación de problema `⟨s₀, Actions, Result, Goal, cost⟩`, no
una política reactiva.

---

## Estado

### Definición formal

```text
s = ⟨ z, b, C, G, D, P, S ⟩
```

| Símbolo | Significado | Representación |
|---|---|---|
| `z` | zona donde está el robot | `str` |
| `b` | batería disponible | `int`, `0 ≤ b ≤ battery_max` |
| `C` | carga: llaves/herramientas + materiales por tipo | `frozenset` de ids + tupla ordenada `((tipo, count), …)` |
| `G` | suelo **vivo**: dónde quedó cada objeto que todavía sirve | tuplas ordenadas `((id, zona), …)` y `(((tipo, zona), count), …)` |
| `D` | puertas abiertas | `frozenset` de ids |
| `P` | paneles reparados | `frozenset` de ids |
| `S` | estaciones en línea | `frozenset` de ids |

`State` es un `dataclass(frozen=True)`: inmutable y hasheable, para que pueda
ser clave de CLOSED.

### Por qué cada variable es necesaria

Aplico el criterio de clase: una variable pertenece al estado **si y solo si**
dos configuraciones que difieran en ella pueden diferir en las acciones legales
futuras o en su resultado.

- **`z`** — decide qué `MOVE` existen y en qué zona puedo recoger, reparar,
  activar o recargar. Cambiarla cambia el conjunto de acciones legales.
- **`b`** — toda acción exige `b ≥ cost(a)`. Dos situaciones idénticas salvo la
  batería difieren en qué puedo hacer después (§2.1 del enunciado): la batería
  es parte de la situación física, no un contador de bitácora.
- **`C`** — `OPEN_DOOR` exige la llave *en la carga*, `REPAIR` exige herramienta
  y material *en la carga*. Además su peso limita los `PICKUP` futuros.
  Un objeto ya inútil que siga en la carga **sigue ocupando espacio**, así que
  no desaparece de `C`: sale solo cuando el robot lo suelta.
- **`G`** — en cuanto el robot puede soltar (`DROP`), la posición de los objetos
  deja de deducirse del escenario inicial. Necesito saber dónde está lo que
  todavía sirve para saber dónde puedo recogerlo.
- **`D`**, **`P`**, **`S`** — son los cambios permanentes del entorno: `D`
  habilita corredores, `P` es precondición de `ACTIVATE`, y `S` es a la vez
  precondición de estaciones dependientes y **la meta misma**. Además `D` y `P`
  determinan qué objetos siguen vivos.

### Qué información se deriva y NO se almacena

Todo lo que es constante del escenario o función del estado vive fuera de `State`
(en un objeto `World` inmutable) o se calcula al vuelo:

- el grafo de corredores, sus costos y sus puertas;
- `action_costs`, `cargo_capacity`, `battery_max`;
- el peso de la carga (suma de los pesos de los objetos de `C`);
- qué llave abre qué puerta, qué herramienta y qué material exige cada panel,
  qué paneles y estaciones requiere cada estación;
- la **clausura de la meta**, que calculo una sola vez al parsear el escenario:
  `S*` = las estaciones de `goal.stations_online` más, recursivamente, todas las
  estaciones de las que dependen; `P*` = los paneles exigidos por alguna estación
  de `S*`. Todo lo que quede fuera de `S*` y `P*` es **decorado**: existe en el
  mundo, pero ninguna acción sobre ello acerca a la meta;
- cuántas unidades de un material siguen haciendo falta:
  `necesarios(M) = |{p ∈ P* \ P : material(p) = M}|`;
- **si un objeto está vivo o muerto**: es función de `D`, `P` y de la clausura.

Duplicar cualquiera de estos datos dentro del estado solo crearía estados
distintos que representan la misma situación física.

### Qué pertenece al historial de búsqueda y no al estado físico

`g(n)`, el puntero al padre, la acción que generó el nodo y la profundidad
describen **cómo llegué**, no **dónde estoy**. Viven en el `Node`
(`search.py`), no en el `State`. Si los metiera en el estado, dos rutas
distintas hacia la misma situación física producirían claves distintas, CLOSED
no las reconocería como repetidas y la búsqueda degeneraría en Tree Search:
ciclos, reexploración y explosión de memoria. Esa separación es exactamente lo
que prueba el Caso 1 de la validación.

### Cuándo dos configuraciones son el mismo estado

Dos configuraciones son el mismo estado cuando coinciden **componente a
componente** en la tupla anterior. Para que `==` y `hash` coincidan con la
equivalencia física uso estructuras canónicas:

1. **Materiales por tipo, nunca por id** (§2.2). Dos `FUSE` son intercambiables:
   la carga guarda `FUSE:1`, no *cuál* fusible. Si les pusiera identificadores
   individuales, `n!` historias distintas producirían estados distintos que son
   el mismo mundo.
2. **Conjuntos y tuplas ordenadas**, no listas: el orden en que recogí los
   objetos no es información física. `PICKUP KEY1, PICKUP FUSE` y
   `PICKUP FUSE, PICKUP KEY1` producen el **mismo** estado.
3. La canonicalización se aplica **dentro de `Result`**, de modo que ningún
   estado no canónico llega nunca a OPEN ni a CLOSED.

### Relevancia: objetos que ya no cambian el futuro

Los cambios del entorno son **monótonos**: una puerta abierta no se cierra y un
panel reparado no se rompe. Combino esa monotonía con la clausura de la meta
`(S*, P*)` calculada al parsear:

- una llave `K` está **viva** ⟺ `puerta(K) ∉ D`;
- una herramienta `T` está **viva** ⟺ existe un panel `p ∈ P* \ P` que la exige;
- un material de tipo `M` está **vivo** hasta `necesarios(M)` unidades; las
  unidades sobrantes están muertas.

El filtro por `P*` importa: un panel que ninguna estación de la meta exige nunca
debe repararse, así que su herramienta y su material **nacen muertos** y jamás
entran al estado. En la instancia demo los tres paneles pertenecen a `P*` y no
se nota, pero en una instancia con equipamiento decorativo —de las que el
profesor puede probar— es la diferencia entre un espacio recorrible y uno que
permuta objetos inútiles por todas las zonas.

Un objeto solo puede influir en el futuro por tres vías: habilitar `OPEN_DOOR`,
habilitar `REPAIR`, u ocupar capacidad. Un objeto muerto no habilita ninguna de
las dos primeras y, por monotonía, **nunca volverá a habilitarlas**. Por lo
tanto:

- si está en el **suelo**, lo borro del estado: su posición ya no distingue
  situaciones. Mantenerlo multiplicaría el espacio por `|zonas|` por cada objeto
  muerto, que es justamente la explosión por permutaciones de objetos muertos.
  Esto no pierde soluciones: dos estados que solo difieran en objetos muertos
  del suelo tienen el mismo conjunto de planes futuros y los mismos costos;
- si está en la **carga**, **conservo su id**. Es tentador colapsarlo a un
  contador anónimo de lastre —físicamente solo importa el espacio que ocupa—,
  pero el contrato exige nombrar el objeto al soltarlo
  (`{"op":"DROP","item":"KEY1"}`), y un lastre sin identidad no se puede
  traducir a un paso válido. El costo de conservar el id es despreciable: la
  carga está acotada por `cargo_capacity`, así que aquí no hay explosión —
  la explosión vive en el suelo, que sí tiene `|zonas|` valores por objeto.

---

## Acciones

Acciones **internas** del agente. Todas exigen además `b ≥ cost(a)`, y todas
descuentan `cost(a)` de la batería.

```text
Acción            | Precondiciones                                          | Efectos                                   | Costo
------------------|---------------------------------------------------------|-------------------------------------------|------------------------
MOVE(z → z')      | existe corredor z→z'; si tiene puerta d, d ∈ D           | z := z'                                   | corridor.cost
PICKUP(x)         | x en el suelo de z; peso(C)+w(x) ≤ cap; x está VIVO;     | x: suelo → carga                          | action_costs.pickup
                  | si x es material M: llevados(M) < necesarios(M)          |                                           |
DROP(x)           | x ∈ C; x está MUERTO; carga LLENA; existe en z un        | x: carga → suelo de z                     | action_costs.drop
                  | PICKUP útil bloqueado únicamente por capacidad           | (al estar muerto, sale del estado)        |
OPEN_DOOR(d)      | z ∈ between(d); d ∉ D; llave(d) ∈ C                      | D := D ∪ {d}                              | action_costs.interact
REPAIR(p)         | z = zona(p); p PENDIENTE; herramienta(p) ∈ C;            | P := P ∪ {p}; material consumido;         | action_costs.interact
                  | material(p) ∈ C                                         | la herramienta NO se consume              |
ACTIVATE(st)      | z = zona(st); st ∈ S*; st ∉ S; paneles(st) ⊆ P;          | S := S ∪ {st}                             | action_costs.interact
                  | estaciones(st) ⊆ S                                      |                                           |
RECHARGE(c)       | c es un cargador declarado en zona z; b < battery_max    | b := battery_max                          | action_costs.recharge
```

Los costos **no se inventan**: salen de `scenario.json` (`corridor.cost` y
`action_costs.*`). En `RECHARGE` el costo se paga **antes** de recargar, así que
la precondición `b ≥ cost` sigue aplicando.

Tres precondiciones son más estrictas de lo que el simulador exigiría, y es
deliberado:

- **`p` PENDIENTE** en `REPAIR` no es «cualquier panel dañado», sino un panel de
  `P*` que sigue dañado y que alguna estación de `S*` todavía OFFLINE exige.
  Reparar un panel que ninguna estación de la meta necesita no acerca a `Goal`.
- **`st ∈ S*`** en `ACTIVATE`: activar una estación fuera de la clausura de la
  meta no aparece en ningún plan óptimo. Si otra estación de la meta dependiera
  de ella, la clausura ya la habría incluido.
- **`c` cargador declarado**: el frontend acepta recargar en una zona marcada
  con `recharge: true` aunque no tenga entrada en `chargers`, pero `simulator.py`
  exige que el `target` sea un id de `chargers` situado en la zona. Genero solo
  los `RECHARGE` que **ambos** validadores aceptan; si una instancia marcara una
  zona recargable sin declarar el cargador, mi agente simplemente no recargaría
  allí (pierde una opción, nunca emite un paso inválido).

### `Applicable` interno vs legalidad del contrato

El simulador dice qué paso es **legal**; mi generador de sucesores dice qué
acción es **relevante para buscar**. Genero un subconjunto estricto de lo legal,
y justifico cada recorte:

**1. No genero `PICKUP` de objetos muertos.**
Un `PICKUP` cuesta `pickup > 0` y un objeto muerto no habilita ninguna acción
futura (monotonía del entorno). Dado cualquier plan que lo contenga, borrar ese
paso deja un plan legal —solo libera capacidad— y **estrictamente más barato**.
Ningún plan óptimo puede contenerlo.

**2. No llevo más unidades de un material de las que exigen los paneles
dañados.** Mismo argumento: cada unidad sobrante cuesta un `pickup` y solo
consume capacidad. `REPAIR` consume exactamente una unidad por panel.

**3. `DROP` solo bajo presión de capacidad.**
Observación clave: **el único efecto de `DROP` que habilita algo es liberar un
espacio de carga**. Un objeto en el suelo no habilita ninguna acción; solo
habilita estando en la carga. Y la meta no menciona posiciones de objetos.

Argumento de intercambio. Sea `Π` un plan óptimo con un `DROP(x)` ejecutado en
un instante `t₀` en el que la carga **no** estaba llena o no había ningún
`PICKUP` útil bloqueado en esa zona:

- *Si `x` no vuelve a recogerse:* retraso ese `DROP` hasta el primer instante
  posterior en que un `PICKUP` quede bloqueado por capacidad, y lo ejecuto allí
  (mismo costo, `drop` es uniforme). Si tal instante no existe, **elimino** el
  `DROP`: el plan resultante es legal y estrictamente más barato.
- *Si `x` vuelve a recogerse y en el intervalo nunca hubo presión de capacidad:*
  elimino el `DROP` **y** el `PICKUP` correspondiente. El robot simplemente
  conservó `x`; el plan es legal y ahorra `drop + pickup`.

En ambos casos obtengo un plan de costo `≤` cuyos `DROP` cumplen la restricción,
así que exigir presión de capacidad no pierde el óptimo. (Borde: si tras la
reescritura un `RECHARGE` cae con la batería llena, ese `RECHARGE` era
innecesario y también se elimina; los prefijos de costo solo bajan, luego la
factibilidad de batería se conserva.)

**4. `DROP` solo de objetos muertos — la restricción que hace viable la
búsqueda, y la que más honestamente debo justificar.**

La condición anterior no basta. La medí: con `DROP` restringido solo por presión
de capacidad, UCS expande **32.745 estados sin pasar de `g = 45`** en la
instancia demo, cuyo plan óptimo cuesta 88. No termina. La razón es que el robot
puede **relevar** objetos vivos: llenarse, soltar una herramienta viva en una
zona intermedia y recogerla después. Cada relevo cambia *en qué zona quedó cada
objeto*, que es exactamente la combinatoria que el enunciado advierte.

Por eso mi generador solo suelta objetos **muertos** (llave de puerta ya
abierta, herramienta sin paneles pendientes, unidades de material sobrantes).
Con esa restricción la misma instancia se resuelve expandiendo **38.751 estados
en 1,4 s**.

*Por qué no pierde soluciones (completitud).* Como los objetos vivos nunca se
mueven de su zona original, siempre se pueden volver a buscar donde estaban.
Y ninguna acción de este dominio exige más de **dos** objetos simultáneos
(`REPAIR` pide herramienta + material; `OPEN_DOOR` pide una llave). Mientras
`cargo_capacity ≥ 2`, existe siempre un plan que va a buscar cada cosa cuando
la necesita y suelta lo que ya murió: la búsqueda explora todos los órdenes, así
que si la instancia tiene solución, la encuentra.

*Qué sí puede costar (optimalidad).* Un relevo puede ahorrar un viaje: dejar la
herramienta a mitad de camino en vez de devolverla a su zona. Mi agente nunca
generará ese plan, así que en una instancia donde el relevo sea estrictamente
más barato devolvería el óptimo **entre los planes sin relevo**, no el óptimo
global. Para la instancia demo estoy comprobándolo por fuerza bruta: un UCS con
`DROP` tan permisivo como el contrato, acotado a `g < 88`, que decide si existe
algún plan más barato. Mientras esa comprobación no concluya, la afirmación que
sostengo es la conservadora: mi agente devuelve el plan de menor costo **entre
los que no usan relevos**.

Dejo la condición escrita en lugar de esconderla: es una decisión de
formulación consciente y acotada, no un descuido, y el parámetro
`allow_live_drops` de `Applicable` permite comprobar el trade-off en cualquier
instancia (`tests/test_case3_cost_vs_steps.py`).

**Lo que NO hago.** No subo `cargo_capacity`, no ignoro la batería y no toco
`scenario.json`: eso resolvería esta instancia y fallaría la siguiente. El
escenario es la fuente de verdad; el arreglo está en la formulación.

---

## Modelo de transición

```text
s --a--> s'     solo si a ∈ Applicable(s)
```

`Result` es **determinista y parcial**: está definida solo sobre las acciones
aplicables, y devuelve un `State` **nuevo** (nunca muta el anterior, porque el
estado es inmutable y compartido con la frontera y CLOSED).

Qué puede cambiar:

| Acción | Cambia |
|---|---|
| `MOVE` | `z`, `b` |
| `PICKUP` / `DROP` | `C`/`J`, `G`, `b` |
| `OPEN_DOOR` | `D`, `b` — y puede **matar** la llave usada |
| `REPAIR` | `P`, `C` (el material se consume, la herramienta no), `b` — y puede matar la herramienta y las unidades sobrantes del material |
| `ACTIVATE` | `S`, `b` |
| `RECHARGE` | `b := battery_max` |

Qué se preserva: todo lo demás, literalmente (las estructuras no tocadas se
reutilizan por referencia, al ser inmutables).

**Sí canonicalizo después de cada acción.** `Result` termina llamando a
`canonical(...)`, que recalcula qué objetos quedaron muertos (porque `D` o `P`
crecieron), los borra del suelo, los suma a `J` si estaban en la carga y ordena
las estructuras. Así, dos caminos que llegan a la misma situación física
producen literalmente el mismo objeto `State`.

---

## Prueba de meta

```text
Goal(s) ⟺ goal.stations_online ⊆ S
```

Para la instancia demo: `{GENERATOR, COMMAND, ARTILLERY} ⊆ S`.

Esta es la condición **real** de éxito porque la misión es restaurar los
sistemas críticos, y eso es una propiedad del **estado final del mundo**, no de
la traza. No compruebo «se ejecutaron estas tareas»: si una estación llegara ya
`ONLINE` en el estado inicial, el plan óptimo simplemente no la activa, y sigue
siendo correcto.

**Las puertas y los paneles no son la meta: son medios.** `D` y `P` aparecen en
el estado porque condicionan acciones futuras (`MOVE` y `ACTIVATE`), no porque
haya que dejarlos en un valor determinado. Un plan que abre una puerta que no
necesitaba es peor, no mejor. Del mismo modo, un panel se repara únicamente
porque alguna estación de la meta lo exige.

---

## Función de costo

```text
g(n) = Σᵢ cost(aᵢ)     sobre el camino desde s₀ hasta n
```

donde `cost(a)` es el **costo oficial del escenario**: `corridor.cost` para
`MOVE`, y `action_costs.pickup / drop / interact / recharge` para el resto.
Todos son positivos. `g(raíz) = 0`.

Esta función representa lo que significa una solución «mejor» en este mundo
porque el costo es **energía**, y la energía es el recurso escaso de la misión:
cada acción descuenta de la batería exactamente su costo. Minimizar `g` es
minimizar el gasto energético total del robot.

**Minimizar pasos no es minimizar costo.** Los costos son heterogéneos: un
`MOVE` vale entre 3 y 12, un `PICKUP` vale 1 y un `INTERACT` vale 2. Ejemplo
real de la instancia demo — el robot está en `Z4` sin `KEY3` y debe llegar a
`Z5`:

- **Ruta A (5 acciones, costo 16):** `Z4→Z3` (5), `PICKUP KEY3` (1), `Z3→Z4` (5),
  `OPEN_DOOR DOOR3` (2), `Z4→Z5` (3).
- **Ruta B (3 acciones, costo 23):** `Z4→Z3` (5), `Z3→Z2` (6), `Z2→Z5` (12),
  saliendo por el corredor exterior, que no tiene puerta (supone `DOOR2` ya
  abierta, que es el caso una vez el robot ha pasado por el taller).

La ruta con **menos acciones cuesta un 44 % más**. Un agente que minimizara
pasos —BFS— devolvería B. El enunciado pide el plan de **menor costo
acumulado**, así que el criterio correcto es `g`, y el algoritmo debe ordenar
por `g`, no por profundidad.

---

## Estrategia de búsqueda

Elijo **Uniform-Cost Search (Dijkstra) en su versión Graph Search**.

Justificación a partir de las propiedades reales del problema:

- Los **costos son heterogéneos y positivos**, así que BFS no sirve: es óptimo
  solo con costos uniformes, y el ejemplo de la sección anterior muestra un caso
  concreto donde devolvería un plan más caro.
- Se exige **el plan de menor costo**, no cualquier plan: DFS y búsqueda en
  profundidad limitada quedan descartados por no ser óptimos (y DFS ni siquiera
  es completo con ciclos, que aquí abundan: el mapa es un grafo con caminos de
  ida y vuelta).
- **No dispongo de una heurística admisible no trivial** para justificar A*: la
  meta es una conjunción de estaciones con dependencias, materiales que hay que
  ir a buscar y capacidad limitada; cualquier heurística seria aquí es un
  problema de diseño aparte. UCS es A* con `h ≡ 0`, es decir el caso admisible
  seguro. Lo dejo anotado como extensión natural, no como parte de la entrega.

**Detalles de implementación que sostienen las garantías:**

- Frontera: cola de prioridad (heap) de tuplas `(g, contador, nodo)`. El
  **contador de desempate** es monótono creciente y solo existe para que, cuando
  dos nodos empatan en `g`, el heap nunca intente comparar los estados: `State`
  define `==` y `hash`, pero deliberadamente **no** define un orden total.
- **La prueba de meta se hace al EXTRAER, no al generar.** Es lo que da la
  optimalidad: un nodo meta generado temprano puede tener `g` mayor que otro
  camino todavía en la frontera. Comprobar al generar rompería la optimalidad.
- CLOSED sobre estados **canónicos**, con **borrado perezoso**: el nodo se
  contrasta contra CLOSED *después* de extraerlo, no al insertarlo. Si al salir
  del heap ya está dominado, se descarta sin expandir; si no, se registra y se
  expande. Así no hace falta un mecanismo aparte de reapertura ni tocar el
  interior del heap: un camino mejor hacia el mismo estado simplemente sale
  antes, y el peor muere al salir.

```text
OPEN   = heap ordenado por g            # (g, contador, nodo)
CLOSED = dict: clave_mundo -> frente de Pareto [(batería, g)]

mientras OPEN no esté vacío:
    n = pop(OPEN)
    si Goal(n.estado):      return reconstruir(n)     # meta AL EXTRAER
    si dominado(n, CLOSED): continue                  # borrado perezoso
    registrar(n, CLOSED)
    para a en Applicable(n.estado):
        push(OPEN, Nodo(Result(n.estado, a), padre=n, acción=a, g=n.g + costo(a)))
return FAILURE
```

**Completitud.** El espacio de estados canónico es finito (zonas × niveles de
batería × colocaciones de objetos vivos × subconjuntos de puertas/paneles/
estaciones) y todos los costos son `> 0`, así que UCS expande cada estado un
número finito de veces y termina siempre. Si no existe plan, la frontera se
vacía y devuelvo `FAILURE` (`solution_found: false`, `steps: []`): **termino, no
me quedo explorando indefinidamente**. Añado además una cota de nodos expandidos
como salvaguarda de examen, que en las instancias correctas no se alcanza.

**Optimalidad.** Se cumple porque todos los costos son no negativos y la prueba
de meta ocurre al extraer: cuando saco un nodo meta de la frontera, ningún otro
camino pendiente puede tener `g` menor.

**Tiempo y espacio.** `O(b^{1+⌊C*/ε⌋})` con `ε = 1` (el costo mínimo, un
`PICKUP`/`DROP`). El `b` peligroso **no es el grado del mapa** —cada zona tiene
2 o 3 corredores—, sino cuántos `PICKUP`/`DROP` genero por estado. Sin las podas
de relevancia, `b` crece con el número de objetos del escenario y UCS deja de
terminar en tiempo de examen. Con ellas, `b` está acotado por los objetos que
todavía sirven, que decrecen monótonamente a medida que avanza la misión. El
espacio es el habitual de UCS: la frontera domina la memoria.

**Cuándo se rompen las garantías:**

- **costos negativos**: rompen el supuesto de Dijkstra y con él la optimalidad,
  porque un camino ya cerrado podría abaratarse después. `build_world` los
  rechaza con `ValueError` al parsear el escenario. Los costos **cero** no
  rompen nada aquí: la optimalidad solo exige costos no negativos, y los ciclos
  gratis no cuelgan la búsqueda porque Graph Search los reconoce en CLOSED
  (el mismo estado con `g` igual y batería igual queda dominado);
- estados mal canonicalizados (materiales con id individual, listas en vez de
  conjuntos): CLOSED deja de reconocer repetidos y Graph Search degenera en Tree
  Search;
- CLOSED que ignore la batería: se «cerrarían» estados físicamente distintos y
  se perderían soluciones;
- `Applicable` demasiado generoso: no rompe la optimalidad, pero sí la
  viabilidad — es el fallo que el enunciado anticipa con `DROP`.

**Cómo evito reexplorar la misma situación física.** CLOSED es un diccionario
indexado por la parte del estado que describe el mundo, y `State` es hasheable y
canónico, de modo que dos historias distintas hacia la misma situación colisionan
en la misma entrada. Eso convierte los ciclos del mapa (`Z1→Z4→Z1`) en
repeticiones detectadas, no en ramas nuevas.

### Batería como recurso

La batería **sí** forma parte del estado (§2.1): sin ella no podría saber si un
`MOVE` caro es legal ni si conviene desviarse a `Z3` a recargar. Pero tratar cada
nivel de batería como un mundo distinto haría que UCS recorriera paseos que solo
gastan energía.

Uso la **dominancia** que describe el enunciado. Si dos caminos llegan a la
misma configuración del mundo `(z, C, J, G, D, P, S)` y uno lo hace con
`b₁ ≥ b₂` y `g₁ ≤ g₂`, entonces el segundo está **dominado**: cualquier plan
ejecutable desde el segundo lo es también desde el primero, al mismo costo,
porque toda precondición sobre la batería es de la forma `b ≥ cost`. Más batería
nunca deshabilita nada útil. (Única excepción aparente: `RECHARGE` es ilegal con
la batería llena; pero si está llena, ese `RECHARGE` era innecesario y el plan
sin él es más barato.)

Por eso **CLOSED se indexa por la configuración del mundo SIN la batería**, y en
cada entrada guardo el frente de pares `(g, b)` no dominados. Un nodo nuevo se
poda si algún par guardado lo domina; si él domina a otros, los reemplaza. Es
una poda *sound*: nunca elimina el único camino hacia el óptimo, solo caminos que
demostrablemente no pueden mejorarlo.

---

## Del plan interno al contrato del frontend

El algoritmo devuelve un **nodo**, no un plan. La reconstrucción sube por los
punteros `padre` hasta la raíz, invierte la secuencia y produce la lista de
acciones internas. `total_cost` es exactamente el `g` del nodo meta, no una suma
recalculada aparte: si ambos números no coinciden, hay un error de contabilidad
en `Result` o en los costos.

Después, y **solo** después, una capa de traducción convierte cada acción
interna en un paso del contrato (`CONTRATO.md` §3):

```text
MOVE(z→z')      →  { op: "MOVE", from: z, to: z', cost }
PICKUP(x)       →  { op: "PICKUP", item: x, cost }
DROP(x)         →  { op: "DROP", item: x, cost }
OPEN_DOOR(d)    →  { op: "INTERACT", target: d,  action: "OPEN_DOOR", cost }
REPAIR(p)       →  { op: "INTERACT", target: p,  action: "REPAIR", consumes: M, cost }
ACTIVATE(st)    →  { op: "INTERACT", target: st, action: "ACTIVATE", cost }
RECHARGE(c)     →  { op: "INTERACT", target: c,  action: "RECHARGE", cost }
```

`OPEN_DOOR`, `REPAIR`, `ACTIVATE` y `RECHARGE` **no son `op`**: son valores del
campo `action` dentro de un `INTERACT`. Los materiales viajan por **tipo**
(`FUSE`), coherente con que el estado no los distingue por id.

Esta frontera es de una sola dirección: la búsqueda no sabe que existe un
frontend, y el frontend no sabe que existe un UCS. Si mañana el contrato visual
cambiara, solo cambia `translate.py`; el modelo de IA queda intacto. Por eso la
capa visual no determina la lógica del agente (§5 del enunciado).

---

## Formulación y tamaño del espacio (obligatorio)

**1. ¿Por qué «5 zonas, ~10 objetos, capacidad 3» puede generar millones de
nodos?**

Porque el estado no es la posición del robot: es la configuración completa del
mundo. Contando de forma ingenua la instancia demo (3 llaves + 3 herramientas,
cada una en 5 zonas o en la carga; 2 `FUSE` + 1 `CHIP` + 1 `CABLE`; 3 puertas,
3 paneles y 3 estaciones binarios; 101 niveles de batería):

```text
5 (zonas) × 101 (batería) × 6⁶ (llaves y herramientas) × 21·6·6 (materiales)
        × 2³ (puertas) × 2³ (paneles) × 2³ (estaciones)  ≈  9,1 × 10¹²
```

Nueve billones de configuraciones. El mapa es pequeño; el espacio de estados no.
La capacidad recorta parte de eso, pero el orden de magnitud no lo salva nadie.

**2. ¿Qué papel tiene `DROP` en la explosión?**

`DROP` es el factor que convierte «dónde está el robot» en «dónde quedó **cada**
objeto». Sin `DROP`, la posición de un objeto solo tiene dos historias posibles:
sigue en su zona original o está en la carga (2 valores por objeto, y decrecen).
Con `DROP` libre son `|zonas| + 1` valores por objeto, y el producto es el `6⁶`
de arriba. Además `DROP` multiplica el factor de ramificación: en cada estado
con carga se abren hasta `cargo_capacity` sucesores que no acercan a la meta.

**3. ¿Qué podas apliqué y por qué son *sound*?**

| Poda | Por qué no pierde el óptimo |
|---|---|
| Borrar del suelo los objetos muertos | No habilitan ninguna acción futura (entorno monótono); dos estados que solo difieran en ellos tienen los mismos planes y costos |
| Colapsar los objetos muertos de la carga a `J` | Conserva lo único que aún afecta la legalidad —el espacio ocupado— y descarta la identidad, que ya no distingue nada |
| Materiales por tipo, no por id | Son intercambiables por definición del escenario (§2.2); distinguirlos crea `n!` estados equivalentes |
| No recoger objetos muertos ni unidades sobrantes | Cuestan `pickup > 0` y no habilitan nada: cualquier plan que los use es mejorable borrando ese paso |
| `DROP` solo bajo presión de capacidad | Argumento de intercambio de la sección de acciones (con el caso residual documentado allí) |
| Dominancia de batería en CLOSED | Un nodo dominado no puede mejorar ningún plan futuro |

**4. ¿Por qué NO es solución subir la capacidad, quitar estaciones o ignorar la
batería?**

Porque no arreglan el agente: arreglan *esta* instancia. Subir
`cargo_capacity` elimina la presión de carga y con ella los `DROP`, pero el
profesor probará instancias con otra capacidad, otros costos, otras posiciones y
otros recursos, y el mismo agente volverá a no terminar. Ignorar la batería
produce planes que el simulador rechaza por energía insuficiente. Quitar
estaciones cambia la meta. El escenario es la fuente de verdad y mi agente lo
lee entero: la única corrección legítima está en la **formulación** —estado
canónico, relevancia y un `Applicable` más estricto que el simulador cuando
puedo justificarlo—, que es lo que documenté arriba.
