# PREREGISTRO — Estudio de ablación de la Tarea 1

## 1. La pregunta y cómo se contesta

**De las intervenciones de la Tarea 1, ¿cuáles son necesarias porque de ellas depende la
exactitud de la inferencia, cuáles aportan otra cosa, y cuáles sobran?**

«Exactitud de la inferencia» no es un número. El evaluador oficial (`evaluate.py`) la reparte
en tres niveles, y el estudio los mide por separado:

| nivel | qué es | métrica oficial | dónde pesa |
|---|---|---|---|
| **D — decisión** | acertar biopsia sí/no. Es una **compuerta**: fallar da **0** al caso entero | gate (aciertos/91), F1(`yes`) | `ranking_score = (mean_case_score + F1_yes) / 2` |
| **F — fidelidad del formulario** | `confidence`, `variable_weights`, factor F1, `tool`, `grounding` | 5 componentes | pesos sin juez 0,225 · 0,275 · 0,175 · 0,150 · 0,175 |
| **N — narrativa** | la nota clínica, juzgada por GEval (Ollama `gemma4:e4b`) | `rationale_score` | 0,20 sólo con juez encendido |
| **C — coste** | segundos, tokens, llamadas LLM, VRAM | telemetría | no puntúa, pero Test rechazó la V2 por tiempo |

**«Directamente relacionada con la exactitud de la inferencia»** = retirarla mueve **D**, y
el estudio puede señalar por qué caso a caso: cambia la regla (`rule`/`who`) que decidió.
Que una intervención mueva F o N no la hace «de exactitud»: la hace necesaria para otra cosa.

Veredictos posibles (regla mecánica pre-registrada, §4.6): `NECESARIA_D`, `NECESARIA_F`,
`NECESARIA_N`, `SOBRA`, `PERJUDICIAL`, `INDETERMINADA`, y `OPERATIVA` (no mueve la exactitud
pero sostiene un límite de entrega; no se propone retirarla).


---

### 4.6 Regla de veredicto (pre-registrada, aplicada por `harness/classify.py`, no a mano)

Márgenes de equivalencia: **δ_rank = 0,010** (≈ un caso que cambia de decisión mueve el ranking
≈ 0,008), **δ_gate = 1/91**, **δ_F = 0,010** por componente, **δ_N = max(0,030, 2·EE del
replicado de A0)**. Para cada intervención X, con `Δ` e `IC = [lo, hi]`:

| nivel | `NECESARIA_x` | `SOBRA_x` | `PERJUDICIAL_x` | si no |
|---|---|---|---|---|
| **D** (ranking, y McNemar) | `lo > 0` y `Δ ≥ δ_rank` y Holm p < 0,05 | `IC ⊂ (−δ_rank, +δ_rank)` | `hi < 0` y `Δ ≤ −δ_rank` | `INDETERMINADA_D` |
| **F** (casos acertados en ambos) | `lo > 0` y `Δ ≥ δ_F` en ≥ 1 componente | todos los `IC ⊂ (−δ_F, +δ_F)` | análogo | `INDETERMINADA_F` |
| **N** (casos juzgados en ambos) | `lo > 0` y `Δ ≥ δ_N` | `IC ⊂ (−δ_N, +δ_N)` | análogo | `INDETERMINADA_N` |

**Veredicto global** (prioridad): `NECESARIA_D` › `NECESARIA_F` › `NECESARIA_N` › `PERJUDICIAL` ›
`SOBRA` (los tres niveles medidos son `SOBRA`) › `INDETERMINADA`. Si N no se midió (sólo Tier S),
el máximo es `SOBRA_DF (N sin medir)`. Un `NECESARIA_*` debe además tener **el mismo signo en DEV
y en VAL**; si no, se publica como `NECESARIA_FRÁGIL`. Todo veredicto lleva su columna de coste
(Δ s/caso, Δ tokens) tomada de la telemetría de L0.

**Un cambio de exactamente 0 en los 91 casos** (p. ej. E2 con `form_weights=trace`) se declara
`SOBRA` **por construcción** y se acompaña de «0 filas distintas»: es más fuerte que un IC.

### 4.7 Hipótesis pre-registradas (predicción, no resultado)

| H | Afirmación | Qué la refuta |
|---|---|---|
| H1 | La cohorte (M1-M3) es necesaria para D: decide 52/91 con 49 aciertos | Δ ranking al quitarla < δ_rank |
| H2 | El grado (M4) es necesario en `bx=Positive`, pero su efecto neto es pequeño (12 casos, 10 aciertos) | Δ ≥ 0,02 (mayor de lo previsto) o ≤ 0 |
| H3 | **En `honest` E1 + E3 no baten a «sí constante» en los 27 casos que decide el voto** (15/27) | el voto gana a «sí» por IC excluyendo 0 |
| H4 | E3 aporta más que E1; E1 es casi redundante con E3 | Shapley(E1) ≥ Shapley(E3) |
| H5 | E2 (PSA) no mueve nada de D ni F con `form_weights=trace` (0 filas distintas) | cualquier fila distinta |
| H6 | E4 es necesario para F (pesos y confianza: 0,275 + 0,225 del caso) y su plan para `tool` (0,150); abrir los 4 documentos baja `tool` | Δ F < δ_F |
| H7 | La biblioteca no vota pero su moda por cubo sostiene a E4: quitarla baja F, no D | Δ D ≠ 0 |
| H8 | El registrador importa por **qué documentos abre** (grado, E3), no por su prosa: un ejecutor determinista del plan da la misma D | L0 y S difieren en decisión |
| H9 | EAU sobra para D y F; su efecto en N es ≤ δ_N | Δ N ≥ δ_N |
| H10 | El moderador sobra para D y F (el plan lo fija E4) | Δ D o F ≠ 0 en L2 |
| H11 | El verificador y la reapertura sobran: el registrador abre el plan en 195/195 | reaperturas > 0 con Δ ≠ 0 |
| H12 | EXPERT-IMAGE nunca se convoca en A0 → sobra por construcción | activaciones > 0 |
| H13 | El presidente (LLM) es necesario sólo para N | Δ D o F ≠ 0 en L5 |
| H14 | Las guardias G1-G3 son necesarias para N e integridad (0/195 violaciones), no para D ni F | Δ N < δ_N y violaciones = 0 sin ellas |
| H15 | La guardia de aterrizaje (M11) sube `grounding` a costa de `variable_weight`; el neto es positivo | neto ≤ 0 |
| H16 | **Ablación conjunta:** quitar a la vez todo lo `SOBRA` no cambia D ni F | Δ ≥ δ_rank en A_min |

### 4.8 Sesgos que el informe **debe** declarar

---

## Registro de variantes S/L

guarda `n`, modo, semilla y `spec`. Salidas en `results/S_*.json` y `results/S_*.csv`.

### PASO 3.1 — Ablaciones de una en una (*leave-one-out*) [CODEX]
- Corre todas las variantes de decisión, documentos, plan y formulario de PASO 2.2 frente a A0.
  Para cada una: Δ e IC de ranking, gate, F1, 5 componentes; McNemar; **lista de casos que
  cambian** con la regla de A0 y la de la variante (`rule`, `who`).
- **Compuerta:** A0 aparece en la tabla con Δ = 0; el número de filas de `S_loo.csv` = nº de
  variantes × 2 modos; sin NaN.
> Estado: pendiente

### PASO 3.2 — Reparto por peldaño («cascade replay») [CODEX]
- Tabla, por modo y por cubo: cuántos casos decide cada peldaño y con qué acierto; y, para el
  voto, **el mismo resultado con «sí» constante** (H3) con su IC.
- **Compuerta:** reproduce cohorte 49/52 · grado 10/12 · voto 15/27 (honest) y 24/27 (deployed).
> Estado: pendiente

### PASO 3.3 — Factorial de decisión y Shapley [CODEX]
- Factorial completo 2⁶ sobre {M1, M2, M3, M4, E1, E3} (64 configuraciones × 2 modos). Salidas:
  `S_factorial.csv`, **valores de Shapley** del ranking y del gate por factor, e interacciones de
  segundo orden (p. ej. M4×`previous_notes`, E3×`radiology_report`).
- Escalera de construcción `F0→F1→F2→F3→A0` con el incremento de cada peldaño.
- **Compuerta:** la suma de Shapley = ranking(A0) − ranking(todo apagado) al 1e-9.
> Estado: pendiente

### PASO 3.4 — Formulario [CODEX]
- Factorial `pesos(3) × confianza(2) × aterrizaje(2) × biblioteca(2)` = 24 configuraciones con la
  decisión de A0, más `S-A-board`. Reporta los 5 componentes por separado (H6, H7, H15).
- **Compuerta:** con A0 la fila reproduce los 5 componentes de PASO 0.1.
> Estado: pendiente

### PASO 3.5 — Sensibilidad de parámetros [CODEX]
- Barridos de umbral, `fusion_mult` y tramos. Etiqueta **«sensibilidad, no ablación»**. Objetivo:
  saber si el veredicto de M5 depende de un parámetro ajustado sobre estos 91 (§4.8-1).
- **Compuerta:** cada barrido incluye el valor de A0 y lo reproduce.
> Estado: pendiente

### PASO 3.6 — Robustez [CODEX]
- Repite 3.1 restringido a `dev` (64) y a `val` (27): tabla de **signo por partición**.
- Detectabilidad: cuántas decisiones netas exige cada ablación para ser significativa.
- **Compuerta:** `S_robustez.csv` con una fila por variante y columnas `signo_dev`, `signo_val`.
> Estado: pendiente

### PASO 3.7 — Lectura provisional del Tier S [CODEX]
- `results/LECTURA_S.md` (≤ 2 páginas): qué salió de H1-H8, H15 según la regla de §4.6, **con la
  columna «desviaciones respecto a lo pre-registrado»**. No propone cambios.
- **Compuerta:** cada hipótesis tiene «confirmada / refutada / indeterminada» y la ruta del CSV.
> Estado: pendiente

### FASE 4 — Arnés del grafo (Tier L), sin ejecutar LLM

### PASO 4.1 — `harness/graph_variants.py` [CODEX]
Variantes del grafo **sin editar la V4**, con un gestor de contexto que parchea en tiempo de
ejecución y restaura al salir:
- **Nodos** (N07, N08, N14): interceptar `StateGraph.add_node` mientras corre
  `create_conference_graph` y sustituir la función por un *stub* que devuelve `{}` y el estado
  mínimo para que los enrutadores sigan (p. ej. `eau_agent` devuelve `eau_nudged=True` y un
  `AIMessage` vacío para que `route_eau` vaya a `eau_post`; `eau_post` no añade intervención).
  Verificador: `max_passes=1` **y** stub.
- **Guardias** (G1-G3): parchear los **nombres tal como los importa el módulo del grafo**
  (`graph.unsourced_values`, `graph.unsourced_grades`, `graph.drop_unsourced_grade_lines`,
  `graph.process_language`), porque las clausuras los buscan en los globales del módulo.
- **Presidente** (N15): `chair_max_retries=0` (parámetro ya existente).
- **Imagen** (N09): no convocar (`need_image=False`).
- **Compuerta (sin GPU):** por variante, con un modelo mudo o guionizado y el panel de la caché:
  (a) el grafo compila; (b) con **ninguna** variante, nodos y aristas son **idénticos** a los de
  la V4; (c) un caso recorre hasta `END`; (d) el acta **no contiene** al participante retirado y sí
  a todos los demás; (e) el módulo queda restaurado (una segunda compilación sin variante vuelve
  a ser idéntica).
> Estado: pendiente

### PASO 4.2 — `harness/run_arm.py` y `launch_arms.sh` [CODEX]
- `run_arm.py --arm <id>`: aplica la variante y llama a `run_task1.main()` **en el mismo
  proceso** con argumentos fijos: `--mode honest`, los 91 etiquetados, `--temperature 0`, mismo
  `--k`, `--gpu-util`, `--out-root Ablation_study/runs/<id>`. Escribe `arm.json` (variante,
  argumentos, `sha256` de la V4, `git rev-parse HEAD`, hora).
- `launch_arms.sh`: brazos **en serie**, uno por proceso; entre brazos comprueba que la GPU
  está libre (`nvidia-smi --query-compute-apps`, no sólo `--query-gpu`); `--resume` salta los
  brazos con 91 salidas válidas.
- **Compuerta (sin GPU):** `--dry-run` imprime la orden y valida los argumentos; el `arm.json`
  de un brazo simulado (2 casos, modelo mudo) se genera y valida.
> Estado: pendiente

### PASO 4.3 — `RUNBOOK_GPU.md` [CODEX]
- Para el humano: orden de brazos, comandos exactos, tiempos esperados, **la regla de VRAM**,
  cómo comprobar cada brazo y cómo devolverlos. Incluye:
  - vLLM (~28,2 GiB a 0,9) y el juez Ollama (~6,5 GiB) **no caben a la vez** en la 5090
    (32,6 GiB): generación primero, luego liberar y juzgar. Liberar el juez:
    `curl -s localhost:11434/api/generate -d '{"model":"gemma4:e4b","keep_alive":0}'`.
  - Un caso por proceso no hace falta aquí (los expertos salen de la caché, determinista),
    pero **el mismo `case_id` en todos los brazos** sí: viene de los ficheros, no se inventa.
  - Todos los brazos con el **mismo** perfil de vLLM (cambiarlo cambia la prosa a T = 0).
- **Compuerta:** un compañero podría ejecutar los pasos 5.x sólo con este fichero.
> Estado: pendiente

### FASE 5 — Corridas con LLM (Tier L) **[HUMANO-GPU]**; Codex valida

Todos en modo `honest`, 91 casos, T = 0. Orden fijo; **L0 primero** y su compuerta gobierna al
resto. ~45 min cada uno.

| brazo | qué se apaga | hipótesis |
|---|---|---|
| **L0** | nada (A0 honest con LLM) | referencia, H8, H11, H12 |
| L1 | EAU (N07) | H9 |
| L2 | moderador (N08) | H10 |
| L3 | verificador + reapertura (N14) | H11 |
| L4 | L1 + L2 + L3 a la vez («sala LLM mínima»: sólo registrador y presidente) | interacción |
| L5 | presidente LLM (N15) → nota determinista | H13 |
| L6 | G1 + G2 (procedencia) | H14 |
| L7 | G3 (lenguaje de proceso) | H14 |
| L0' | **réplica de L0** | ruido de fondo (decisión y prosa) |

`L8` (registrador sustituido por un ejecutor determinista del plan) queda **opcional**: sólo si
H8 sale dudosa. No se re-ejecuta la variante «presidente ve el acta» (G4): evidencia previa.

### PASO 5.1 — L0 y su compuerta [HUMANO-GPU] + [CODEX] valida
- Humano: `launch_arms.sh L0` (runbook). Codex: `harness/validate_arm.py` comprueba **91/91**
  salidas en `runs/<brazo>/output/task1/<caso>/` (así las escribe `run_task1.py`, líneas
  201-222; el acta va en `runs/<brazo>/boards/`, y la telemetría por papel en `summary.jsonl` y
  `telemetry.jsonl`), las valida con `version_final_reto/common/contract.py`, puntúa con
  `dev/score_local.py --tasks 1 --count-missing --output-root Ablation_study/runs/<brazo>/output`
  (el puntuador lee `<output-root>/task1/<caso>/`; **la ruta lleva `output/`**) y escribe
  `results/L_L0.json` con `accepted` y `blocker`.
- **Compuerta (la que gobierna todo lo demás):** en L0, **decisión, confianza, pesos y
  `reveal_sequence` de los 91 casos son idénticos a los de S-A0 `honest`**, y el ranking coincide
  al 4.º decimal. Además se cuentan y guardan: activaciones de EXPERT-IMAGE (**H12**), reaperturas
  del verificador (**H11**), empujones, casos con plan vacío, y **si el registrador abrió
  exactamente el plan en los 91** (el supuesto de Tier S). Si algo difiere, **se detiene el
  estudio** y se investiga antes de lanzar el resto: significaría que el simulador no representa
  al agente.
> Estado: pendiente

### PASO 5.2 — Resto de brazos [HUMANO-GPU] + [CODEX] valida
- `launch_arms.sh L1 L2 L3 L4 L5 L6 L7 L0p`. Tras cada uno, `validate_arm.py` (misma compuerta de
  91/91 y `accepted`).
- **Compuerta:** `results/L_<brazo>.json` para los ocho, cada uno con `accepted: true`. Un brazo con
  `accepted: false` guarda su `blocker` legible y se relanza sólo ése.
> Estado: pendiente

### PASO 5.3 — D y F con LLM [CODEX]
- Δ de cada brazo frente a L0 con la estadística de §4.5, y **la diferencia L−S** (por brazo, si
  el LLM cambia alguna decisión o forma respecto al simulador). Salidas `results/L_efectos.csv`.
- Ruido de fondo: L0 vs L0' (la decisión debe ser idéntica; si no, se publica cuánto).

---

## Desviaciones

