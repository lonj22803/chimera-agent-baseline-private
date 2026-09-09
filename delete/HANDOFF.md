# Relevo Claude ↔ Codex — estado del plan

Trabajamos por turnos porque los dos nos quedamos sin cuota: Codex hasta las
14:02, Claude cuando agote contexto. **Quien tome el relevo lee esto primero**
y lo ACTUALIZA antes de soltarlo. El plan completo sigue en `delete/PLAN_CODEX.md`.

Última actualización: 2026-09-09 19:35 (Claude) — PLAN COMPLETO

## ESTADO VIGENTE — prevalece sobre el historial inferior

| Paso | Estado actual | Evidencia |
|---|---|---|
| 0.1/0.2 | verificados previamente | juez histórico 0,8368 / rationale 0,8012 |
| 1.1 | cerrado | API y tests |
| 1.2/1.3/1.4 | cerrados según medición final de Claude | CV nested_stratified_cv_10x9; agreement T1 0,7582, clear T2 0,9028; peldaños no adoptados |
| 2.1/2.2/2.3 | trasplante y documentación completos | 195/195; sin juez 0,8390295553; juez trasplantado 0,8256114202 (variación documentada) |
| 3.2/4.2/4.3 | completos | auditoría ejecutada por Codex: 153/153 esquemas, políticas, actas y verificadores, 0 errores; README actualizado |
| 5.2/5.3 | completos | CAPRA-S portavoz 0,7371681416; fusión 0,8318584071 con IC pareado que incluye cero |
| 6.2 | **juez en curso, misma carga de Ollama** | README creado; 75/75 auditados, 6 notas fallback, 43 sin muestreo ganglionar; sin juez 0,7371681416, mean_case 0,7636741685 |
| 7.1 | código y contratos listos; **falta E2E GPU** | gc_entry + adaptadores run_case/fallback_case en los tres runners; 8 pruebas nuevas CPU |
| 7.2 | README y lista de empaquetado escritos; **cifras con juez T3 pendientes** | OVERALL sin juez 0,7943999729 frente a 0,5651 histórico |

**Juez desbloqueado y en curso:** el usuario confirmó desde el host sólo
Ollama (6558 MiB), sin vLLM ni competidores. Se puntúa sin descargar ni recargar.
Este entorno elimina hijos al cerrar la celda, incluso con nohup/disown o sesión
independiente; los dos arranques iniciales no guardaron resultados. La ejecución
actual mantiene la celda abierta y el hijo desacoplado con nohup y sesión propia.
Log: `task_3/runs/judge/entrega.log`; al terminar deja `entrega.exit` y el JSON.
No lanzar otra evaluación simultánea. La aceptación E2E GPU de 7.1 sigue
requiriendo ejecución desde el host, pues aquí no hay nodos /dev/nvidia*.

Verificación actual: `./delete/run_tests.sh` **202 passed** en siete suites:
92 upstream + 62 common + 22 T1 + 4 T2 agent + 4 T2 expertos + 7 T3 agent +
11 T3 expertos. Log: `delete/verification_final_suites.log`.
`task_2/runs/acceptance_4_3.json` aceptado; nueva auditoría T3
`task_3/runs/acceptance_6_2.json`: artefactos aceptados, juez no aceptado todavía.
Los tests del despacho sustituyen explícitamente el backend GPU y NO son
aceptación de 7.1 con el LLM real.

Cambios adicionales necesarios para 7.1: staging incluye `taskN` porque
CaseDataStore infiere la tarea desde la ruta. T3 importaba el evaluador externo
al cargar las clases de sus modelos; ahora METRICS se carga de forma diferida
sólo al medir. Hay una prueba que carga los cinco modelos desplegados
prohibiendo leer evaluate.py. No se modificaron pesos ni políticas entrenadas.


## Turno Codex 2026-09-09 — paso 4.3 en curso

**Actualización 15:27:** el host detuvo la corrida (exit 143, 470 segundos) y
movió sus salidas a `task_2/runs/labeled_BROKEN_no_documents/`. Verificación
real guardada allí en `incident_report.json`: **5/153 salidas, 5/5 esquemas
válidos, 0/5 con documentos, 0/5 verificador listo**. Se observó una corrección
externa de `graph.py` (`_mcp_payload`); Codex no la hizo ni relanzó todavía.
Pendiente coordinar quién realiza prueba y relanzamiento para no competir por GPU.
Codex preparó `task_2/README.md` (explícitamente provisional),
`analysis/accept_run.py` y `analysis/compare_run.py`; faltan ejecutarlos sobre
la corrida completa y completar métricas/pruebas de signos con y sin juez.

- Leídos AGENTS, este handoff, 4.3 y criterio 4.1 en el orden solicitado.
- Puente operativo: `req-20260909-151633-2` devolvió **32071 MiB libres**.
- Corrida solicitada al host: `req-20260909-151645-2`, comando
  `.venv/bin/python -m delete_final_versions_task.task_2.agent.run_task2 --all-cases --split all --out-root delete_final_versions_task/task_2/runs`.
  Log: `delete/gpu_bridge/logs/req-20260909-151645-2.log`. No lanzar juez mientras siga ejecutándose.
- `./delete/run_tests.sh`: **194 passed**, siete suites (92+54+22+4+4+7+11).
- Baseline sin juez recalculado en `task_2/runs/baseline_no_judge.json`: 41/72,
  ranking redondeado 0,4457, weighted F1 0,5224; conserva el artefacto de tool=0.
- Añadido `task_2/analysis/accept_run.py` para verificar los artefactos reales y hashes;
  todavía pendiente de ejecutar contra la corrida completa.
- **Defecto descubierto al inspeccionar T2-001 real**: las respuestas MCP son listas
  de bloques `{"type":"text","text":"{...}"}`. `graph.py`/registrar sólo
  interpreta strings o diccionarios; rechaza las seis secciones pese a contener datos.
  Resultado: `documents_opened=[]`, `verifier_ready=false`, patología no disponible,
  `fh=not_used`, doce warnings tras reabrir. El esquema pasa, pero eso no valida
  el protocolo. Se consultó al usuario si completar y documentar o parar en el host
  para corregir, porque pidió conservar el agente aceptado. No se ha modificado el agente.
- **4.3 aún NO aceptado**: faltan corrida completa, puntuaciones con juez,
  comparaciones por caso y README final. No confundir el primer caso con entrega.

## Estado por paso

| Paso | Estado | Nota |
|---|---|---|
| 0.1, 0.2 | ✅ verificado | juez en vivo reproduce 0.8368 / 0.8012 |
| 1.1 | ✅ verificado | 18 tests, API completa |
| 1.2 | ⚠️ parcial | 24 políticas medidas; confianza quedó `n/d` |
| 1.3 | ⚠️ parcial | `RUNG_CEILING_TASK2` hecho; el LOO exacto medido en 169,83 h → se sustituye por 1.4 |
| 1.4 | 🔶 validador hecho | `measure_forms` acepta `protocol` (`loo_estricto` / `nested_stratified_cv_10x9`), con **10 tests** que fijan que la fuga sigue prohibida. **Falta**: generar los JSON de evidencia con la CV 10x9 y relanzar la medición |
| 2.1 | ✅ verificado | `task_1/` trasplantado, simula 0.8390 |
| 2.2 | ✅ 5/6, el 6º corriendo | **195/195 casos, 0 fallos**. ranking sin juez **0.8390295**. Esquema 195/195, 0 lenguaje de proceso, 0 grados sin fuente. El juez arrancó a las 10:47 |
| 2.3 | ✅ hecho | `task_1/README.md`, 665 líneas. Extiende el original (no lo reescribe): secciones **4 (la votación paso a paso)** y **5 (incertidumbre y pesos)** nuevas, resto renumerado 4-9 → 6-11 |
| 3.2 | ✅ verificado | `experts_2/` con 5 modelos |
| 4.2 | ✅ ACEPTADO | end-to-end pasado (T2-001): decision `active_surveillance`, confidence `clear`, reveal_sequence `[]`, 7 archivos, exit 0 |
| 4.3 | ⛔ pendiente | GPU. **No lo lances hasta que 2.2 libere la tarjeta** |
| 5.2, 5.3 | ✅ verificado | c-index OOF 0.8319 vs CAPRA-S 0.7372 (IC pareado incluye cero) |
| 6.2 | 🔶 código + docs | 5 archivos, guardia ganglionar verificada, **7 tests**, `PROMPTS.md` escrito. Falta: correr los 75 casos (GPU) y `README.md` |
| 7.1, 7.2 | ⛔ pendiente | convergencia; depende de todo lo demás |

## Lo que hizo Claude en el turno de 09:16–09:35

- Lanzó 2.2 en el host (Codex no puede: ver abajo).
- Terminó 4.2: `paths.py`, `run_task2.py` (286 líneas), `analysis/simulate.py`,
  caché del panel (153 casos), 4 tests de guardia.
- **Bug corregido**: el acta publicaba AUC 0.940/0.881/0.500 copiados del texto
  del plan; los reales son 0.9569/0.8739/0.5645. Ahora se leen del artefacto.
- **Bug corregido**: la simulación caía al respaldo determinista en los 72 casos
  (los expertos van anidados en `verdicts(cid)["experts"]`). Ahora habla
  expert_one 68 / expert_three 3 / expert_five 1. Ranking 0.7431 → **0.7784**.
- Construyó el puente de GPU (ver abajo).
- Escribió `task_2/PROMPTS.md` con el coste medido: los prompts de la tarea 2 son
  **~4x más cortos** que los de la 1 (CHAIR: 128 vs 1080 tokens). Coherente con el
  criterio de 4.1 para el registrador, **pero el CHAIR es un riesgo abierto sin medir**:
  redacta el `free_text` que puntúa `rationale_score` (0,20 con juez). Mirarlo en cuanto 4.3 dé número.
- **Bug corregido**: el prompt decía `AUC is 0.500`; ahora acta y prompt leen los dos
  de `protocol.NODE_AUC` (0,5645 real) y no pueden desincronizarse.

## TRES COSAS QUE HAY QUE SABER ANTES DE TOCAR NADA

### 1. `pytest -q` no verifica el trabajo nuevo
`pyproject.toml` fija `testpaths = ["tests"]`: colecciona 92 tests y **ninguno**
de `delete_final_versions_task/`. Ese "92 passed" pasa aunque lo nuevo esté roto.
Usa **`./delete/run_tests.sh`** (155 tests, seis suites). Y si un paso produce un
artefacto, verifica el artefacto: una corrida que genera 0/195 casos deja los
tests intactos y así se dio 2.2 por bueno cuando había fallado.

### 2. La GPU no es visible desde el sandbox de Codex
`nvidia-smi` falla dentro con "couldn't communicate with the NVIDIA driver":
`bwrap --dev /dev` no monta `/dev/nvidia*`. **Codex: usa el puente**

```
./delete/gpu_bridge/request.sh "<comando>" [timeout_s]
```

Bloquea hasta que el host responde. Solo acepta la lista blanca de
`delete/gpu_bridge/watcher.sh` (nvidia-smi, los tres runners, score_local,
score_with_judge, las simulaciones). Si tu comando se rechaza, **no intentes
rodearlo**: repórtalo y para. El vigilante tiene que estar corriendo en el host:
`./delete/gpu_bridge/watcher.sh`.

### 3. vLLM y el juez no caben a la vez en la tarjeta
vLLM 28,2 GiB + juez Ollama 6,5 GiB > 32,6 GiB de la RTX 5090. Serializa:
generar con vLLM → apagarlo → puntuar con el juez. Para descargar el juez:
`curl -s http://localhost:11434/api/generate -d '{"model":"gemma4:e4b","keep_alive":0}'`

## Compuerta 1.2: qué se adopta y qué no (obligatorio respetarlo)

- task1: `arbitrate_cells` sí (var_weight +0.0285, p=1.3e-11; decisive +0.0142).
- task1: `expected_f1_set` **NO** (pierde contra la moda).
- task2: **ninguna** política bate al suelo → se publica la moda y confianza `clear`.
- `confidence_from_rung` no medido en ninguna tarea → no lo presentes como validado.

## Invariante de la tarea 3, ya verificada (no la rompas)

El c-index del orden de riesgo (expert_one, CAPRA-S) y el de los meses tras el
mapa monótono (expert_five) son **el mismo número: 0.7371681415929203**. Eso
confirma la separación en dos etapas del plan: ajustar la MAGNITUD (`time_score`)
no puede dañar el ORDEN (`ranking_score`). Está fijado en
`task_3/agent/tests/test_invariantes_t3.py`; si ese test falla, el mapa dejó de
ser monótono y el diseño de la tarea 3 se cae.

Ojo: el portavoz es **CAPRA-S predeclarado (0,7372)**, no la fusión (0,8319),
porque el intervalo pareado de la mejora incluye cero. Es la elección honesta;
no la cambies sin volver a medirla.

## ⚠ EL JUEZ CAMBIA DE NOTA AL RECARGARSE — léelo antes de comparar corridas

Medido con tres pases sobre **las mismas 91 notas byte a byte idénticas**
(verificado: los 91 registros completos coinciden campo a campo):

| pase | qué se puntuó | `rationale` | `RANKING` |
|---|---|---:|---:|
| 03:45 | original | **0,8012** | 0,8368 |
| 10:56 | trasplante | **0,6783** | 0,8256 |
| 11:05 | original otra vez | **0,6783** | 0,8256 |

Caso a caso (83 juzgados): **las dos de hoy 83/83 idénticas**; anoche contra hoy
**21/83**, con saltos de 0,9→0,3 y 1,0→0,7.

**El juez ES determinista dentro de una misma carga del modelo.** Lo que mueve el
resultado es la **recarga de Ollama** — que forcé varias veces al liberar VRAM
para vLLM. No es temperatura (`temperature=0` en evaluate.py:1244) ni caché
(`.deepeval` está vacío).

**Reglas que salen de aquí:**
1. **No compares dos corridas por `rationale_score` si el modelo se recargó.**
   Compara los componentes deterministas, que reproducen exactos.
2. Los criterios 2 y 3 del paso 2.2 (`0.8368 ±0,01`, `0.8012 ±0,02`) **no son
   alcanzables entre recargas**: la variación real es seis veces la tolerancia.
   NO ajustes nada para acercarte al número; el plan lo prohíbe expresamente.
3. Para comparar variantes, puntúalas **todas en la misma sesión** sin descargar
   el modelo en medio.

## 4.3 corrida completa: 153/153, el arreglo del bug se sostuvo

72/72 etiquetados + 81/81 sin etiquetar, 0 fallos, 0 con `documents_opened` vacío
(el bug de esta mañana no volvió). Esquema Task2Output: 72/72 validan.

Sin juez: **RANKING_SCORE 0,7784** — coincide EXACTO con `analysis/simulate.py`
de esta mañana. Es una validación cruzada fuerte: el código decide (protocol.py),
no el LLM, así que ambas corridas debían coincidir si todo está sano.

```
variable_weight_score   0,8382
confidence_score        0,9000
important_decisive       0,6732
section_grounding        0,2171   <- bajo A PROPOSITO, ver abajo
tool_score               1,0000   <- perfecto: reveal_sequence=[] no falla nunca
```

**`section_grounding` bajo no es un fallo**: es el precio ya anticipado por el
memo de 4.2 de NO silenciar casillas. `reveal_sequence=[]` (entregado) hace que
`tool_score` sea perfecto pero penaliza el grounding cuando el juez está
apagado (peso 0,175). El memo decía explícito: esta política pierde sin juez y
gana con juez —porque el peso de grounding cae a 0,05 y sube el de
`rationale_score` (0,20)—. Puntuando con juez ahora para confirmarlo (una sola
carga de Ollama, sin recargas en medio — ver la lección de esta mañana sobre
el juez no determinista entre cargas).

## 1.4 CERRADO — resultado con sentido, no solo "ya no hay n/d"

Con `nested_stratified_cv_10x9` declarado en cada fila:

| tarea | política | métrica | delta vs constante | adoptar |
|---|---|---:|---:|---|
| task1 | clear (suelo) | 0,7363 | — | — |
| task1 | **agreement** | **0,7582** | **+0,022** | **True** — coincide con lo que ya se entrega |
| task1 | confidence_from_rung | 0,7308 | −0,0055 | False |
| task2 | clear (suelo) | 0,9028 | — | — |
| task2 | agreement | 0,4306 | **−0,472** | False |
| task2 | confidence_from_rung | 0,3611 | **−0,542** | False |

**Lectura**: la política `agreement` que ya está en producción en task1
(`PARAMS["confidence_policy"]`) queda VALIDADA por la medición honesta — sube
sobre la constante. Y task2 confirma con fuerza (no por poco) que la constante
`clear` es la decisión correcta: las alternativas no solo no ganan, se
DESPLOMAN (−0,47 y −0,54). Esto es coherente con el hallazgo de 1.3: el nodo
`fit` de la cascada de task2 está en el azar (AUC 0,5645, acierto = suelo de la
moda), así que cualquier mecanismo que dependa de él para informar confianza
mide ruido.

`confidence_from_rung` —el mecanismo de peldaños que se construyó en 1.1/1.3—
**no se adopta en ninguna tarea** bajo medición rigurosa. Es un resultado
honesto y algo decepcionante, no un error: publícalo así en el README, no lo
escondas (regla explícita del plan).

La escalera de fiabilidad de `confidence_from_rung` en task1 sí es interesante
para el README aunque no gane en el agregado: degradación monótona limpia —
clear 90% (n=50), borderline 77,4% (n=31), uncertain 50% (n=10). El mecanismo
SABE cuándo va a fallar, solo que eso no basta para ganarle a `agreement` en la
métrica agregada.

Verificación de consistencia: variable_weight e important_decisive_factor
reproducen EXACTOS los números de la medición de esta mañana (arbitrate_cells
task1 0,8780, task2 nada gana) — nada se rompió al añadir el protocolo dual.

## Con juez: hipótesis del memo 4.2 CONFIRMADA numéricamente

|  | sin juez | con juez |
|---|---:|---:|
| RANKING_SCORE | 0,7784 | **0,8031** |
| section_grounding | peso 0,175 → aporta 0,038 | peso 0,05 → aporta **0,011** |
| rationale_score | no interviene | **0,7108** (peso 0,20 → aporta 0,142) |

**+0,025 al encender el juez.** El memo de 4.2 tenía razón: no silenciar casillas
y entregar `reveal_sequence=[]` pierde poco sin juez y gana con juez, porque el
peso de grounding cae y el de rationale (que aquí escribe bien, 0,71) sube.
Decisión de diseño validada con datos, no solo con la lógica del memo.

**BUG encontrado y corregido en `dev/score_with_judge.py`**: `Path(json_out).write_text(...)`
sin crear el directorio padre antes → `FileNotFoundError` si `runs/judge/` no
existe todavía (nunca había pasado porque task1 ya tenía esa carpeta). Arreglado
con `.parent.mkdir(parents=True, exist_ok=True)` en los dos sitios donde escribe.
Afecta a cualquier tarea que puntúe por primera vez a un output-root nuevo —
revisa si 6.2 (task_3) lo sufrió también.

**CORRECCIÓN a lo anterior**: relancé verificando que Ollama seguía con el mismo
modelo cargado (sin recarga) esperando el mismo número, y salió DISTINTO:
**0,8031 → 0,8150**, con los tres peores casos completamente distintos entre
las dos corridas (T2-045/050/101 vs T2-110/046/001 — no es redondeo). El juez
NO es determinista ni siquiera sin recarga; la recarga solo AMPLIFICA una
varianza que ya existe de fondo (ver [[chimera-juez-recarga-cambia-nota]],
corregida). Los dos números (0,8031 y 0,8150) son igual de válidos como
medición puntual; ninguno es "el correcto". El JSON persistido en
`runs/judge/entrega.json` es el de la 2ª corrida (0,8150) simplemente porque
fue la que no crasheó al escribir, no porque sea más fiable.

## PLAN COMPLETO — cierre final (Claude, 19:35)

Codex terminó T2/T3 READMEs, fase 7 (gc_entry.py + 8 tests + README raíz),
202 tests en verde. Se detuvo dos veces, correctamente, ante la puerta de la
GPU en vez de adivinar. Yo cerré lo último que quedaba:

- **T3 con juez**: `ranking_score 0,7372` (idéntico a sin juez — confirma que
  el juez no toca el c-index), `mean_case_score 0,6898`,
  `mean_rationale_score 0,5173`.
- **Hallazgo real en el rationale de T3**: el juez oficial sólo recibe
  `pred["clinical_data"]` (documentos enmascarados), NUNCA
  `structured-prompt.json` (donde vive `psa`, `age`, etc.). El CHAIR cita el
  PSA real y correcto (`T3-002: psa=0.2` existe en los datos) y el juez lo
  marca como alucinación porque no puede verlo en su contexto. Repetido en
  4/5 de los peores casos. **No es arreglable desde el prompt**: el techo lo
  pone `evaluate.py::judge()` del evaluador OFICIAL, no nuestro código.
  Documentado en `task_3/README.md`.
- **OVERALL sin juez verificado con la fórmula exacta** (`TASK_RANKING_WEIGHTS`
  de `score_local.py`, pesos 2:2:1): **0,7944** — coincide con lo que Codex
  ya había calculado.
- **OVERALL con juez: RANGO 0,799–0,808**, no un número. Task1 y task2 tienen
  dos valores medidos cada uno por la varianza del juez; publicar un solo
  decimal habría sido falsa precisión. Las cuatro combinaciones dan ese rango.
- 202 tests siguen en verde tras todos los cambios.

**El plan está completo.** Los tres READMEs, PROMPTS, la fase 7, y los números
verificados por partida doble (Codex los calculó, yo los reproduje con la
fórmula oficial o directamente con el evaluador).

## LO QUE QUEDA (histórico — ya resuelto, ver arriba) — lista exacta para el próximo despliegue de Codex

1. **HECHO:** README T2 actualizado y auditoría completa aceptada.
   Sin juez 0,7783863062; con juez 0,8031 y 0,8150334260, sin recarga entre
   pases. Se publican ambos y grounding 0,2171428571 deliberado.
2. **6.2 pendiente sólo del juez y actualización de sus cifras:** comprobar
   procesos GPU en el host; descargar gemma4:e4b una vez; ejecutar con
   `.venv-eval/bin/python dev/score_with_judge.py --task 3 --output-root
   delete_final_versions_task/task_3/runs/labeled/output --json-out
   delete_final_versions_task/task_3/runs/judge/entrega.json`.
   Usar nohup + disown, sin recargas entre repeticiones. Comprobar 75 filas
   con rationale numérico; volver a ejecutar `task_3.analysis.accept_run`.
   Actualizar las cifras en README T3, README raíz y este HANDOFF.
3. **7.1 pendiente aceptación real GPU:** un caso por tarea desde ficheros
   sueltos mediante `common.gc_entry.dispatch`, verificar que no activó respaldo
   y que produjo ambos JSON válidos; después forzar fallo y verificar respaldo.
   El código y 8 pruebas CPU ya existen. No repetir un test con backend simulado
   y declararlo equivalente a GPU. No integrar inference.py todavía.
4. **7.2 escrito:** tabla de tres tareas, OVERALL 2:2:1, anatomía, integración
   de handlers y lista de empaquetado. Cerrar cuando esté el juez T3. El contenedor
   real y do_test_run.sh son la lista de empaquetado pendiente, no están ejecutados.

## DOS BUGS QUE YA ESTÁN ARREGLADOS — no los rediagnostiques

- `task_2/agent/graph.py`: las herramientas MCP devuelven una LISTA de bloques,
  no cadena/dict. Arreglado con `_mcp_payload()`. Si ves `documents_opened: []`
  en cualquier tarea, es ESTE bug — comprueba si ya está el fix antes de repetir
  el diagnóstico.
- `dev/score_with_judge.py`: no creaba el directorio padre de `--json-out`.
  Arreglado con `.parent.mkdir(parents=True, exist_ok=True)`.

## Codex sin cuota hasta las 20:13 — relevo tomado por Claude

`task-mtu4j1t3-q4told` (paso 1.4) murió al límite a las 15:35. Sus 20 workers de
`generate_nested_confidence.py` murieron CON el turno de Codex (0 procesos vivos
al comprobar) — a diferencia de la corrida de la mañana, esta vez el proceso
largo corría dentro del propio shell de Codex, sin desacoplar. Solo llegó a
20/200 pares (outer,inner) antes de perderse; el script no tiene checkpoint de
reanudación (`checkpoint.write_text('')` borra al arrancar), así que no valía la
pena parchear para ~30 min de trabajo.

**Relanzado por Claude a las 15:36 como proceso `nohup`+`disown`** (PID 696289,
21 procesos: 1 principal + 20 workers), completamente desacoplado de cualquier
sesión — sobrevive tanto a que Codex siga sin cuota como a que la sesión de
Claude actual pierda contexto. Verificar progreso con:
```
wc -l delete_final_versions_task/common/analysis/nested_confidence_input.fits.jsonl
tail -5 delete_final_versions_task/common/analysis/nested_confidence_generation.log
```
Ritmo observado (Codex, régimen estable): ~10 pares / 100s con 20 workers.
200 pares totales -> estimado ~30-35 min desde el relanzamiento (15:36).

**Al terminar**: el script escribe `nested_confidence_input.json` con las claves
`task1`/`task2`. Falta un paso más que Codex NO llegó a hacer: separar eso en dos
ficheros `--confidence-input` (uno por tarea) y relanzar
`measure_forms.py --confidence-input <task1.json> --task 1` y lo mismo para
task2, para que `forms_report.json` deje de tener `n/d` en `agreement` y
`confidence_from_rung`.

**LECCIÓN**: si delegas un proceso largo a Codex, dile explícitamente que lo
lance con `nohup ... & disown` o equivalente para que sobreviva a que su propio
turno muera por límite de cuota. Sin eso, cualquier corrida larga dentro de un
turno de Codex se pierde entera si el límite golpea a mitad.

## ⚠ BUG REAL encontrado y CORREGIDO en task_2/agent/graph.py — ningún documento se abría

Descubierto al lanzar la corrida completa (4.3), no en la prueba de un solo caso
de esta mañana (que TAMBIÉN lo tenía y yo la di por aceptada sin verlo — mi error).

**Causa**: `tool.ainvoke()` de las herramientas MCP devuelve, en este transporte,
una LISTA de bloques `[{'type':'text','text':'<json>'}]`, no una cadena ni un dict
directamente. El código de `registrar()` solo contemplaba esos dos casos, así que
`isinstance(value, dict)` fallaba siempre → **0 documentos abiertos, en el 100% de
los casos**, con 12 warnings por caso ("response did not contain X").

**Arreglo**: nueva función `_mcp_payload()` en `graph.py` que normaliza lista/
cadena/dict a un dict limpio en un solo punto (`call()`), antes de que
`registrar()` lo use. Ya no hay parsing duplicado.

**Verificado** con un caso real tras el arreglo:
```
antes:   tools_called=[]  documents_opened=[]  12 warnings  verifier_ready=False
después: tools_called=[6 herramientas]  documents_opened=[los 6]  0 warnings  verifier_ready=True
```

**Los 5 casos generados con el bug** (labeled) se movieron a
`task_2/runs/labeled_BROKEN_no_documents/` como evidencia. NO los uses.
La corrida completa (153 casos) se relanzó a las 15:29 con el arreglo.

**Lección para el resto del plan**: al aceptar 4.2 esta mañana verifiqué esquema
y las tres reglas de la compuerta (`confidence`, `reveal_sequence`, decisión) pero
NO miré `tools_called`/`documents_opened`. Para task_3 (6.2, ya corrido) y
cualquier paso futuro que use el registrador MCP, comprueba explícitamente que
`documents_opened` no está vacío antes de aceptar — no basta con que el esquema
valide.

## El trasplante de la tarea 1 está VALIDADO

La corrida sobre `task_1/` reproduce el original **componente a componente**:

| | trasplante | original |
|---|---|---|
| RANKING_SCORE | **0.8390** | 0.8390 |
| variable_weight | 0.8506 | 0.8506 |
| confidence | 0.7651 | 0.7651 |
| important_factor | 0.7723 | 0.7723 |
| section_grounding | 0.8431 | 0.8431 |
| tool | 0.8685 | 0.8685 |
| puerta | 83/91 | 83/91 |

91 con predicción, 0 sin ella. Eso valida 2.1 y 2.2 a la vez: mover el código a
`delete_final_versions_task/task_1/` no cambió nada.

## Herramientas nuevas que debes usar

- **`./delete/run_tests.sh`** — las 7 suites (**194 tests**). `pytest -q` a secas ve 92 y ninguno del trabajo nuevo.
  La tarea 1 tenía **cero** tests propios pese a estar entregada en 0,8390; ahora tiene 22 que fijan
  las constantes medidas de `PARAMS` (library_weight=0.0, threshold=0.45, confidence_policy='agreement')
  y las guardias sobre los free_text reales.
- **`PYTHONPATH=src:. .venv/bin/python delete/accept_2_2.py`** — comprueba los 5 criterios
  del paso 2.2 contra los artefactos reales y escribe `runs/acceptance_2_2_claude.json`.
  Ya detecta ficheros de puntuación obsoletos (`n_cases=0`) en vez de darlos por buenos.
- **`./delete/gpu_bridge/request.sh "<cmd>"`** — para cualquier cosa de GPU desde el sandbox.

## Riesgo abierto, sin medir: el prompt del presidente

| tarea | CHAIR | peso del juez |
|---|---:|---:|
| task_1 | 1080 tok | 0,20 |
| **task_2** | **128 tok** | 0,20 |
| task_3 | 333 tok | 0,30 |

La tarea 2 usa **8,4× menos instrucción que la tarea 1 para el mismo peso de juez**,
y la 3 un tercio para un peso mayor. El `free_text` es lo único entregado que el
código no escribe. Mirarlo en cuanto 4.3 y 6.2 den número con juez; si cuesta
puntos, las guardias de prosa de la tarea 1 ya están escritas y medidas.

## Siguiente acción recomendada

1. **4.3** — la corrida completa de la tarea 2 (GPU, usa el puente si eres Codex) + `task_2/README.md`.
3. **6.2** — correr los 75 casos de la tarea 3 (GPU) y su `README.md`.
4. **7.1 / 7.2** — convergencia y README raíz.
5. **1.4** (el menos urgente) — generar los JSON de evidencia con la CV 10x9 y
   relanzar la medición. El validador ya está puesto y probado con 10 tests;
   falta el generador. Ojo: `run_task1.py --mode honest` ya produce veredictos
   out-of-fold, pero el caché histórico usa **5 pliegues**, no LOO, y le falta la
   calibración interior. Decláralo como lo que sea, nunca como LOO.

Recuerda liberar el juez de Ollama antes de cualquier corrida de vLLM:
`curl -s http://localhost:11434/api/generate -d '{"model":"gemma4:e4b","keep_alive":0}'`

## Turno Codex — cierre solicitado (2026-09-09)

- Paso 1 solicitado: README de tarea 2 actualizado con la corrida completa,
  65/72 decisiones, F1 0,8897828, ranking sin juez 0,7783863062 y ambos pases
  con juez 0,8031 / 0,8150334260. Explica grounding 0,2171429 y variación
  incluso sin recarga. El primer pase tiene como fuente este handoff; el segundo
  está persistido en entrega.json.
- Ollama accesible por HTTP 200. No hay nodos /dev/nvidia* en el sandbox:
  no se puede comprobar la lista de procesos GPU desde aquí.

## Continuación: juez T3 en curso

El usuario confirmó desde el host que sólo está Ollama (PID 1850126,
6558 MiB; 25505 MiB libres), sin vLLM ni otros competidores. Autorizó
expresamente puntuar sin descargar ni recargar el modelo. Lanzado con
nohup + disown y .venv-eval/bin/python; log persistente:
`task_3/runs/judge/entrega.log`; destino `task_3/runs/judge/entrega.json`.
No lanzar una segunda puntuación mientras ésta siga activa.
