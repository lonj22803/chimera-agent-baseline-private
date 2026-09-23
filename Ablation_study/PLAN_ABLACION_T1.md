# PLAN — Estudio de ablación de las intervenciones de la Tarea 1

**21 de septiembre de 2026.** Rama `ablation_study_final_version`. Base: la arquitectura
final `version_final_reto_send_v4` (enlace `version_final_reto`), commit `fe4ec15`.
Alcance: **sólo la Tarea 1** (decisión de biopsia). El diseño es extensible a T2/T3 (PASO 8.2),
pero no se toca nada de ellas.

> **Estado: F0-F8 cerradas; estudio completo.** Registro de avance en §8. Nada se marca
> hecho sin evidencia en disco.

---

## 0. Cómo leer y ejecutar este plan (Codex: obligatorio)

1. **Lee por pasos, nunca el fichero entero.** `cat` se trunca a ~14 000 tokens y este plan
   es más largo. Localiza los pasos con
   `grep -n '^### PASO' Ablation_study/PLAN_ABLACION_T1.md` y léelos con `sed -n 'A,Bp'`.
   Las secciones 1-5 (contexto y diseño) se leen enteras una vez, por rangos de ~150 líneas.
2. **Ejecuta SÓLO el paso que se te asigna.** Al cerrarlo actualiza, en el mismo turno, los
   tres sitios: la tabla de §7, el Registro de §8 (fecha + ruta de la evidencia) y el bloque
   `> Estado:` del paso. Sin fichero de evidencia en disco, no está hecho.
3. **`version_final_reto_send_v4/` es de sólo lectura**, y con él `src/`, `inference.py`,
   `configs/`, `templates/`, `resources/`, `dev/`, `data/`, `model/`. Todo el código nuevo
   vive en `Ablation_study/`. Invariante que se comprueba al cerrar **cada** paso:
   `git status --short` sólo lista rutas bajo `Ablation_study/`. Si un paso parece exigir
   tocar algo de arriba, **PARA** y anótalo en §8 «Bloqueos»; lo decide el humano.
4. **No hagas commit ni push.**
5. **Quién ejecuta.** `[CODEX]` = CPU, dentro de tu sandbox. `[HUMANO-GPU]` = corridas con
   vLLM u Ollama: tu sandbox aísla la red (`localhost:11434` da HTTP 000 aunque el servicio
   esté arriba) y no llega a la GPU. **No intentes ejecutarlas ni concluyas «Ollama no está
   disponible»**: escribe el script y el runbook, y valida los resultados cuando existan.
6. **Entorno.** Desde la raíz del repo: `export PYTHONPATH=$PWD:$PWD/src`. Intérprete de
   entrega: `.venv/bin/python`. Juez (sólo F6): `.venv-eval/bin/python`. Evaluador oficial en
   `~/PycharmProjects/CHIMERA-agent-eval` (o `CHIMERA_EVAL_REPO`) con `USE_RATIONALE_JUDGE=0`
   salvo en F6.
7. **Pruebas: una suite por invocación.** Los paquetes `tests` de `tests/`, `common/tests/`,
   `task_*/agent/tests/`… colisionan si se pasan juntos a un solo `pytest`
   (`ModuleNotFoundError: tests.test_...`). Las de este estudio van en
   `Ablation_study/ablacion_tests/` (nombre único a propósito).
8. **Datos bajo acuerdo de uso.** No copies `data/`. Los resultados llevan `case_id`,
   decisiones sí/no y puntuaciones; nunca `free_text` del urólogo ni valores clínicos.
9. **Límite de cuenta de Codex.** Si un turno muere con «usage limit», no reintentes antes de
   la hora que da el mensaje. Todos los pasos son idempotentes y escriben su evidencia al
   final, así que retomar es repetir el paso.
10. **Un paso de GPU se verifica por su artefacto real** (91 ficheros, un campo `accepted`),
    no porque `pytest` siga en verde: la suite no se entera de que la corrida no produjo nada.
11. **Una fase no está cerrada hasta correr su compuerta tal como está escrita.**

---

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

## 2. La arquitectura sobre la que se mide

Todo sale de leer el código de la V4; las referencias son `fichero:línea`.

```
INTAKE(1,2) → E1 STRUCTURED → COHORT → LIBRARY → E4 TRACE(fija el plan) → EAU ⇄ RAG
  → MODERATOR → [IMAGE si lo pide] → REGISTRAR ⇄ MCP → E2 PSA → E3 FUSION → PANEL-PROTOCOL
  → VERIFIER ⇄ RAG ──(falta un doc del plan)──► MODERATOR (pase 2)
                   └─(listo)──► CHAIR → nota + formulario                 task_1/agent/graph.py:720-777
```

**Lo que decide el código, no un modelo** (graph.py:26-39):
- *La decisión*: `protocol.consolidate` (protocol.py:126), una cascada:
  1. **cohorte** (`cohort.criterion`, cohort.py:75): sin biopsia previa PI-RADS ≥ 3 · biopsia
     negativa PI-RADS ≥ 4 · biopsia positiva: PSA ≥ 20, edad ≥ 78 o PI-RADS ≤ 2 → diferir.
  2. **grado documentado** (`decide.documented_grade`, decide.py:71; regex sobre el texto
     **crudo** de la herramienta): bx=Positive, GG ≥ 2 → no; GG 1 → sí.
  3. **voto ponderado**: E3 × 1,5 × tramo + E1 × tramo (`firm` 3 · `supports` 2 · `discuss` 1),
     biopsia si p ≥ 0,45; `library_weight = 0`. Sin ningún experto: «sí» por carga de la prueba.
  (El peldaño «precedente idéntico» está apagado en la entrega: sólo dispara dentro de muestra.)
- *Confianza*: política `agreement` (protocol.py:189). *Pesos del formulario*: los de **E4**
  (`trace.predict`, trace.py:42) con guardia de aterrizaje (`variable_view`, protocol.py:92, y
  `enforce_grounding`, decide.py:262). *Plan de documentos*: E4 (`reveal_sequence`); el
  registrador abre exactamente eso.
- *El LLM* recupera (EAU, registrador), pregunta (moderador), verifica y **redacta la nota**
  (presidente). No vota.

**Cifras ancla** (simulador sin LLM, `task_1/analysis/simulate.py`, 91 etiquetados; recalculadas
el 21-sep-2026). En `deployed` la corrida con LLM (`result_v2/`, 0,83903) dio lo mismo que la
simulación: «el modelo no mueve la nota». **En `honest` nunca se ha corrido con LLM**: que el
simulador lo represente bien es una hipótesis que verifica L0 (PASO 5.1) antes de seguir.

| modo | ranking | gate | F1(yes) | por peldaño (aciertos) |
|---|---:|---:|---:|---|
| **honest** (expertos out-of-fold; **la referencia del estudio**) | **0,7607** | 74/91 | 0,8547 | cohorte 49/52 · grado 10/12 · **voto 15/27** |
| deployed (expertos vieron las etiquetas) | 0,8390 | 83/91 | 0,9310 | cohorte 49/52 · grado 10/12 · voto 24/27 |
| techo (biblioteca devuelve el caso) | 0,9469 | 91/91 | 1,0000 | irrelevante: imposible en test |

**Dos consecuencias que gobiernan el diseño.** (1) `deployed` mide memorización: los 9 aciertos
de más del voto son de casos que E1/E3 vieron con su etiqueta. En el test real ningún caso está
etiquetado, así que **toda conclusión se saca de `honest`**; `deployed` se publica al lado como
el precio de la memorización. (2) En `honest` el voto de los expertos decide 27 casos y acierta
15 (55,6 %): **es la primera pregunta que el estudio tiene que contestar** (¿baten a la
constante «sí»?), porque es donde se concentra la exactitud que falta.

**Capa operativa** (no se ablaciona; ver §3.D): `supervisor.py` (reloj duro externo),
`shadow.py`, `warmup.py`, `deadline.py`, `serial_predict.py`, perfil de 16 GB, caché/puntuación
en vivo del panel. Verificadas antes: salida byte a byte igual cuando no se disparan.

---

## 3. Catálogo de intervenciones y mecanismos

**Unidad de estudio.** Las 15 intervenciones del grafo (§3.A) **más** los mecanismos del
protocolo (§3.B) y las guardias (§3.C), porque varias intervenciones sólo actúan a través de un
mecanismo concreto (p. ej. el registrador importa por el grado y por qué documentos abre).
`Tier` = con qué se mide: **S** simulador sin LLM (CPU, ~1 s por configuración, [CODEX]),
**L** corrida con LLM (GPU, [HUMANO-GPU]), **J** juez de razonamiento (Ollama, [HUMANO-GPU]).
`H` = hipótesis pre-registrada (§4.7).

### 3.A Nodos del grafo (`task_1/agent/graph.py`)

| ID | Intervención | Línea | Canal hacia la nota | Cómo se apaga | Tier | H |
|---|---|---|---|---|---|---|
| N01 | INTAKE (1, 2) | 236 | vuelca el expediente en el acta | **estructural: no se ablaciona** | — | — |
| N03 | EXPERT-STRUCTURED (E1) | 253 | voto (M5) | `structured={"available":False}` | S | H4 |
| N04 | EXPERT-COHORT | 264 | peldaño 1 (M1-M3) | `criterion` → `verdict=None` | S | H1 |
| N05 | EXPERT-EXPERIENCE (biblioteca kNN) | 268 | no vota; su `bucket_mode` alimenta pesos, confianza y plan de E4 | `library=None` | S | H7 |
| N06 | EXPERT-TRACE (E4) | 277 | plan de documentos, pesos, confianza base | ver M9-M10 | S | H6 |
| N07 | EXPERT-EAU (+ RAG) | 290-315 | texto de guía → acta y parte del presidente; **no entra al protocolo** | `add_node` → stub | L, J | H9 |
| N08 | MODERATOR | 319 | sólo preguntas; el plan lo fija E4 | stub + `plan_from_sections(..., {})` | L, J | H10 |
| N09 | EXPERT-IMAGE | 364 | sólo si el moderador la convoca | nunca convocar; **medir activaciones en L0** | L | H12 |
| N10 | REGISTRAR (+ MCP) | 381-441 | abre documentos → grado (M4), E2/E3 disponibles, `tool_score` | `opened=[]` (S) · plan libre (S) | S, L | H8 |
| N11 | EXPERT-PSA (E2) | 445 | **no vota**; sólo `levels` de `variable_view` (irrelevantes con `form_weights=trace`) | `psa={}` | S | H5 |
| N12 | EXPERT-FUSION (E3) | 450 | voto (M5); sólo habla si se abrió `radiology_report` | `fusion={"available":False}` | S | H4 |
| N13 | PANEL-PROTOCOL | 455 | **la decisión** | no se quita; se ablacionan sus mecanismos (§3.B) | S | — |
| N14 | VERIFIER (+ reapertura) | 467-516 | sólo puede reabrir y añadir texto; `max_passes=2` | stub + `max_passes=1` | L, J | H11 |
| N15 | CHAIR | 527-656 | nota (lo que puntúa el juez); decisión, confianza y pesos ya vienen del protocolo | `--chair-retries 0` → nota determinista `clinical_note` | L, J | H13 |

### 3.B Mecanismos del protocolo y del formulario (`protocol.py`, `decide.py`, `trace.py`)

| ID | Mecanismo | Dónde | Cómo se ablaciona | Tier |
|---|---|---|---|---|
| M1 | Cohorte, sin biopsia previa: PI-RADS ≥ 3 (24/24) | cohort.py:80 | fuerza `verdict=None` en `bx=None` | S |
| M2 | Cohorte, biopsia negativa: PI-RADS ≥ 4 (16/18) | cohort.py:85 | ídem en `bx=Negative` | S |
| M3 | Cohorte, bx positiva: **M3a** PSA ≥ 20 · **M3b** edad ≥ 78 · **M3c** PI-RADS ≤ 2 (9/10) | cohort.py:64-73,91 | cada regla por separado y juntas | S |
| M4 | Grado documentado: **M4a** GG ≥ 2 → no · **M4b** GG 1 → sí | decide.py:71, protocol.py:166 | `grade_rule=False` (existe), y cada mitad | S |
| M5 | Voto ponderado: **M5a** E1 · **M5b** E3 · umbral 0,45 · tramos 3/2/1 · `fusion_mult` 1,5 | protocol.py:50,176 | E1 fuera, E3 fuera, ambos fuera; barrido de parámetros = *sensibilidad*, no ablación | S |
| M6 | `library_weight = 0` (la biblioteca no vota) | protocol.py:58 | *add-back*: 0,5 (evidencia previa: −0,033) | S |
| M7 | Peldaño «precedente idéntico» (apagado) | protocol.py:155 | **no se ablaciona**; sólo referencia (techo) | — |
| M8 | Confianza `agreement` (la alternativa `trace` es la moda por cubo, trace.py:58) | protocol.py:189 | `trace` (moda por cubo) · constante `clear` | S |
| M9 | Pesos del formulario: E4 `model+mode` | trace.py:47-53 | `mode` · `model` · constante `noted`; `form_weights=board` como *add-back* | S |
| M10 | Plan de documentos = predicción de E4 | trace.py:55-57 | plan por moda del cubo · abrir los 4 · abrir ninguno | S |
| M11 | Guardia de aterrizaje (`variable_view.grounded` + `enforce_grounding`) | protocol.py:118, decide.py:262 | apagada · estricta incluyendo `bx` | S |
| M12 | Excepción `bx` (`UNGROUNDABLE_BY_DESIGN`) | decide.py:232 | = «estricta» de M11 | S |
| M13 | Cada documento del plan: `previous_notes`, `radiology_report`, `laboratory_results`, `psa_trend` | roster.py | *leave-one-document-out*: cierra uno | S |

### 3.C Guardias del LLM

| ID | Guardia | Dónde | Cómo se apaga | Tier |
|---|---|---|---|---|
| G1 | Valores sin fuente (reto al registrador) | graph.py:416, guards.py:22 | parchear `graph.unsourced_values` → `[]` | L |
| G2 | Grados sin fuente, **tres capas** (reto, borrado del parte, verificación de la nota) | graph.py:417,554,588 | parchear `graph.unsourced_grades` → `[]` y `graph.drop_unsourced_grade_lines` → identidad | L |
| G3 | Lenguaje de proceso + reto + nota determinista | graph.py:586-623, decide.py:148 | parchear `graph.process_language` → `[]` | L |
| G4 | El presidente ve un parte, no el acta (`clinical_digest`) | prompts.py:675 | **no se re-ejecuta**: evidencia previa (187/195 notas nombraban la maquinaria antes de G4; 0/195 después). Citarla | — |
| G5 | Sin plan, el registrador pierde las herramientas de documento | graph.py:368 | irrelevante si el plan nunca está vacío en A0; contar casos con plan vacío | — |
| G6 | Filtros del moderador (`drops_panel_question`, extras fuera del plan) | graph.py:337-351 | van con N08 | L |
| G7 | Empujones (`nudge`) a EAU/registrador | graph.py:299,392 | contar cuántas veces se disparan en L0 | — |

### 3.D Fuera de alcance, con su clasificación

| Bloque | Clasificación | Por qué no se ablaciona |
|---|---|---|
| Supervisor, sombra, `warmup`, `deadline`, `serial_predict`, perfil 16 GB, caché/puntuación en vivo | `OPERATIVA` | Existen por el límite de 15 min de Test. Evidencia: `PLAN_V4.md`, `BITACORA_TEST.md`, `common/tests/test_supervisor.py`. Sólo se comprueba (PASO 8.1) que siguen sin cambiar la salida |
| Bloques de rasgos **dentro** de E1/E3/E4 (A, B, D, E…) | ya medido | Ablación por bloque en `README_TAREA_1_EXPERTOS_ARQUITECTURA.md` §bloques. Este estudio ablaciona **intervenciones del agente**, no rasgos |
| Prompts (redacción) | fuera | Es otra pregunta (calidad de prosa); sólo entra vía G1-G3 |
| Esquema de salida, `reveal_sequence` derivada de herramientas, validación | estructural | Son el contrato del reto |

---

## 4. Diseño experimental

### 4.1 Tres niveles de medida

| Tier | Qué mide | Cómo | Coste |
|---|---|---|---|
| **S** | D y F de todo lo que decide el código | `harness/sim.py`: la misma función que `simulate.simulate`, con variantes; supone que el registrador abre exactamente el plan (lo verifica L0) | ~1 s/config; < 15 min todo el barrido |
| **L** | lo que sólo existe con el LLM: EAU, moderador, verificador, presidente, guardias; y comprueba que S y L coinciden | `run_task1.py` con parches (`harness/graph_variants.py`), 91 casos, modo `honest`, T = 0 | ~26 s/caso (`result_v2`: 5 129 s / 195) → ~45 min por brazo |
| **J** | N: la nota, por el juez oficial | `dev/score_with_judge.py` en `.venv-eval`, todos los brazos en **la misma sesión** de Ollama | ~10 min por pasada y brazo |

### 4.2 Datos, modos y particiones

- 91 casos etiquetados de `data/task1` (49 `bx=Positive` · 24 `None` · 18 `Negative`). Los 104
  restantes no tienen etiqueta: sólo sirven para comprobar que los brazos entregan (195/195).
- **Modo primario `honest`**; `deployed` como contraste. Biblioteca en *leave-one-out* siempre.
- Particiones fijas `dev/splits/task1_dev.txt` (64) y `task1_val.txt` (27): **no se usan para
  elegir**, sólo para exigir que un veredicto tenga el mismo signo en ambas (§4.6).

### 4.3 Brazos de referencia (los suelos)

Cada ablación se compara con **A0** (la V4 tal cual) y el estudio incluye los **suelos** para
saber cuánto vale el conjunto: `F0` = «sí» constante; `F1` = sólo cohorte; `F2` = `F1` + grado;
`F3` = `F2` + E3 (el experto fuerte); `A0` = `F3` + E1 y el resto (formulario incluido). Es la
escalera de construcción; en cada peldaño los documentos que el paso necesita están abiertos.

### 4.4 Sobre el «reemplazo neutro»

Retirar una intervención exige decir qué queda en su lugar; si no, el resultado mide el
reemplazo. Regla: **el sustituto es siempre el comportamiento que el propio código ya tiene
cuando esa pieza no está disponible** (`available: False`, `verdict: None`, `library=None`,
`chair_retries=0`…), no un invento del estudio. Si no existe, se documenta en
`BITACORA_ABLACION.md` con la justificación.

### 4.5 Estadística (`harness/stats.py`)

- **Datos pareados por caso.** `Δ = métrica(A0) − métrica(A0∖X)`; positivo = X ayuda.
- `ranking_from_rows(rows)` reimplementa `compute_aggregate_metrics`; se **prueba** que
  reproduce el oficial al 1e-12 sobre A0 antes de usarse.
- IC 95 % por **bootstrap pareado de casos**, 10 000 remuestreos, semilla `20260921`,
  recalculando F1 en cada remuestreo (no promediando diferencias).
- Decisión (D): **McNemar exacto** sobre aciertos pareados, y prueba de signos; ×Holm sobre
  la familia de ablaciones primarias. F: Wilcoxon pareado **sólo sobre los casos acertados en
  ambos brazos** (así F no se contamina con D).
- **Descomposición de Shapley** del ranking sobre el factorial de decisión (§PASO 3.3): reparte
  el mérito entre cohorte, grado, E1 y E3 respetando las interacciones.
- **Detectabilidad** (se publica): con n = 91, ¿cuántas decisiones netas hacen falta para que
  McNemar dé p < 0,05? (con 6 discordantes a favor y 0 en contra, p = 0,031). Un efecto de 1-3
  casos **no es detectable**: el estudio lo dice y no lo interpreta.

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

1. Las reglas de cohorte y de grado se **leyeron de los 49 `free_text`**, y el umbral 0,45 se
   eligió sobre los mismos 91: su Δ sobreestima lo que valdrán en el test, y no se puede
   anidar. Se publican con esa etiqueta.
2. `honest` es out-of-fold con semilla fija (`20260907`), pero los hiperparámetros de los
   expertos se eligieron sobre estos casos.
3. n = 91, y sólo 49 en el cubo difícil: efectos de 1-3 casos no son detectables (§4.5).
4. Un solo modelo (gemma-4-E2B-it), T = 0, un solo pase por brazo; el juez es estocástico
   (Δ 0,012 entre dos pasadas seguidas sin recarga; hasta ±0,12 entre recargas).
5. El test real tiene otra distribución que no conocemos (104 casos sin etiqueta).

### 4.9 Presupuesto

| Bloque | Ejecuta | Tiempo |
|---|---|---|
| F0-F3 (harness + Tier S) | Codex, CPU | horas de Codex; el barrido ~15 min de reloj |
| F4 (arnés de grafo) | Codex, CPU, LLM simulado | horas de Codex |
| F5 (8 brazos × 91 casos) | humano, GPU | ~6 h (8 × ~45 min) + cargas de vLLM |
| F6 (juez: ≤ 8 brazos × 3 pasadas) | humano, GPU | ~4 h |
| F7-F8 | Codex, CPU | horas de Codex |

---

## 5. Estructura de `Ablation_study/`

```
Ablation_study/
  PLAN_ABLACION_T1.md      este plan (fuente de verdad del avance)
  README.md                índice de 15 líneas
  PREREGISTRO.md           hipótesis, márgenes y regla; congelado con sha256 (PASO 0.3)
  BITACORA_ABLACION.md     decisiones, desviaciones, bloqueos (sólo se añade)
  RUNBOOK_GPU.md           lo que ejecuta el humano, con comandos exactos (PASO 4.3)
  __init__.py
  harness/                 código: paths, sim, variants, stats, classify, graph_variants,
                           run_arm, audit_notes, judge_analysis, report, *.sh
  configs/                 intervenciones_t1.yaml · variantes_sim.yaml · brazos_llm.yaml
  ablacion_tests/          pruebas del arnés (nombre único: `tests` colisiona con el resto)
  results/                 anclas.json, huella_v4.txt, S_*.{json,csv}, L_*.json, J_*.json,
                           tabla_maestra.{csv,json}
  runs/                    salidas de los brazos con LLM (en .gitignore; se regeneran)
  reports/                 INFORME_ABLACION_T1.md y figuras/
```

`.gitignore` de la carpeta: `runs/`, `__pycache__/`. `results/` **sí** se versiona (agregados,
por caso sólo decisiones y puntuaciones).

---

## 6. Fases y pasos

Cada paso: **quién** · qué · salidas · **compuerta** (obligatoria).

### FASE 0 — Preparación y congelación

### PASO 0.1 — Línea base verificable [CODEX]
- Confirma `git branch --show-current` = `ablation_study_final_version` y crea el esqueleto de §5.
- Calcula `sha256` de todo `version_final_reto_send_v4/` (sin `__pycache__` ni `*.log`) y de
  `src/`, `inference.py`, `dev/` → `results/huella_v4.txt`.
- Ejecuta el simulador **llamando a las funciones de la V4** (no reimplementadas) en los dos
  modos y guarda `results/anclas.json` con ranking, gate, F1, los 5 componentes, aciertos por
  cubo y **aciertos por peldaño** (`who`).
- Corre cada suite de la V4 **por separado** y guarda `results/tests_base.json` (pasadas/falladas).
  Referencia del 21-sep: `tests` 92 · `common/tests` 141 · `task_1/agent/tests` 22 ·
  `task_2/agent/tests` 4 · `task_2/experts_2/tests` 4 · `task_3/agent/tests` 10 ·
  `runtime_16gb/test_perfil.py` 7 · `task_3/experts_3/train/test_acceptance.py` 11. En
  `common/tests` hubo **un** fallo aislado no reproducido en 9 pasadas posteriores: si aparece,
  repite con `-rf`, anota qué prueba es y no bloquees.
- **Compuerta:** `anclas.json` reproduce **0,8390 (deployed) y 0,7607 (honest)** a 4 decimales,
  y por peldaño `honest` = cohorte 49/52 · grado 10/12 · voto 15/27; `deployed` = 49/52 · 10/12 ·
  24/27. Si no coinciden, **no se sigue**: el entorno no es el de la V4.
> Estado: hecho 2026-09-21. Evidencia: `Ablation_study/results/huella_v4.txt`,
> `Ablation_study/results/anclas.json`, `Ablation_study/results/tests_base.json`.

### PASO 0.2 — Esqueleto, rutas y `.gitignore` [CODEX]
- `Ablation_study/__init__.py`, `harness/paths.py` (raíz del repo, `DATA`, `EVAL_REPO`, `CACHE`
  reutilizando `version_final_reto.task_1.agent.paths`), `ablacion_tests/conftest.py`.
- **Compuerta:** `import Ablation_study.harness.paths` funciona desde la raíz con el `PYTHONPATH`
  de §0.6; `git status --short` sólo muestra `Ablation_study/`.
> Estado: hecho 2026-09-21. Evidencia: import de `Ablation_study.harness.paths` con
> `PYTHONPATH=$PWD:$PWD/src`; `git status --short` sólo bajo `Ablation_study/`.

### PASO 0.3 — Pre-registro [CODEX]
- Escribe `PREREGISTRO.md` copiando **literalmente** de este plan: la pregunta (§1), los
  márgenes y la regla de veredicto (§4.6), las hipótesis H1-H16 (§4.7) y el registro de
  variantes S/L (§6 pasos 3.x y 5.x). Añade una sección final `## Desviaciones` (vacía).
- `sha256sum PREREGISTRO.md > results/preregistro.sha256`. **Desde aquí el fichero no se edita**
  salvo la sección Desviaciones, con fecha y motivo.
- **Compuerta:** el sha256 existe y una prueba `test_preregistro.py` falla si el fichero cambia
  fuera de `## Desviaciones`.
> Estado: hecho 2026-09-21. Evidencia: `Ablation_study/PREREGISTRO.md`,
> `Ablation_study/results/preregistro.sha256`,
> `Ablation_study/results/preregistro_pre_desviaciones.sha256` y
> `Ablation_study/ablacion_tests/test_preregistro.py`.

### FASE 1 — Catálogo

### PASO 1.1 — Catálogo legible por máquina [CODEX]
- `configs/intervenciones_t1.yaml`: una entrada por ID de §3.A-§3.C con `id`, `nombre`,
  `nodos_grafo`, `simbolo` (`fichero:línea`), `canal`, `variantes`, `tier`, `hipotesis`.
- Un módulo `harness/catalogo.py` lo carga y valida.
- **Compuerta (automática):** una prueba compila el grafo de la V4 con un modelo mudo (patrón en
  `task_1/analysis/_build_anatomia.py`: `_Mute` + `create_conference_graph(tools, _Mute(), None,
  None, None)`; si el cliente MCP no arranca en el sandbox, usa herramientas falsas con los
  nombres de `common/roster.SECTION_BY_TOOL` y `search_guidelines`) y comprueba que **todo nodo
  del grafo pertenece a algún ID del catálogo o figura en `estructural`**. Si la V4 tiene un
  nodo que el catálogo no conoce, la prueba falla y se corrige el catálogo, no la prueba.
> Estado: hecho 2026-09-21. Evidencia: `Ablation_study/configs/intervenciones_t1.yaml`,
> `Ablation_study/harness/catalogo.py` y
> `Ablation_study/ablacion_tests/test_catalogo.py`; la prueba compila el grafo V4 con modelo
> mudo y herramientas falsas y cubre todos sus nodos.

### PASO 1.2 — Registro de lo no ablacionable [CODEX]
- Sección `estructural` del YAML con justificación de una línea por elemento de §3.D y N01, M7,
  G4-G5, G7.
- **Compuerta:** cada elemento tiene `por_que` no vacío.
> Estado: hecho 2026-09-22. Evidencia: sección `estructural` de
> `Ablation_study/configs/intervenciones_t1.yaml`, validada por
> `Ablation_study/harness/catalogo.py` y `test_catalogo.py`.

### FASE 2 — Arnés de simulación (Tier S)

### PASO 2.1 — `harness/sim.py` [CODEX]
- `simulate_variant(spec, mode) -> rows`: **misma estructura** que `simulate.simulate`
  (simulate.py:63) llamando a las mismas funciones de la V4 (`cohort_expert`, `trace_expert`,
  `P.consolidate`, `documented_grade`, `enforce_grounding`, `ProfessionalExperience`), con puntos
  de gancho para cada variante de §3. `score_rows(rows)` usa el evaluador oficial y devuelve
  agregados + **filas por caso** (`decision_score`, `case_score`, 5 componentes, `rule`, `who`,
  `bx`, `pred`, `gt` binaria).
- El `spec` es un dataclass inmutable con un `id` y campos explícitos (cohorte por regla, grado
  por mitad, E1, E3, biblioteca, plan, documentos cerrados, política de pesos, política de
  confianza, aterrizaje, `form_weights`, `library_weight`, `threshold`, `fusion_mult`, `tiers`).
- **Compuerta (identidad):** con el `spec` de A0, las **91 filas** (y las 195 con `--all-cases`
  sin puntuar) son **idénticas campo a campo** a las de `simulate.simulate(...)` en los dos
  modos, y los agregados dan los anclas de PASO 0.1.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/harness/sim.py` y
> `Ablation_study/ablacion_tests/test_sim_identity.py`; identidad exacta de A0 en `deployed` y
> `honest`, anclas reproducidas y 195 casos recorridos con 91 puntuados.

### PASO 2.2 — `harness/variants.py` y `configs/variantes_sim.yaml` [CODEX]
Registro con las variantes (`spec` derivados de A0), cada una con `id`, descripción y H:

| bloque | ids | qué |
|---|---|---|
| Decisión | `S-M1`, `S-M2`, `S-M3`, `S-M3a/b/c`, `S-COH` (M1+M2+M3) | apaga reglas de cohorte |
| | `S-M4`, `S-M4a`, `S-M4b` | grado |
| | `S-E1`, `S-E3`, `S-E1E3` | voto sin E1, sin E3, sin ninguno (queda «sí» por carga de la prueba) |
| | `S-VOTO-YES`, `S-VOTO-E1`, `S-VOTO-E3` | el voto sustituido por «sí» constante / sólo E1 / sólo E3 (**H3**) |
| Suelos | `F0` `F1` `F2` `F3` | §4.3 |
| Documentos | `S-DOC-prev`, `S-DOC-rad`, `S-DOC-lab`, `S-DOC-psa` | cierra un documento del plan (M13) |
| Plan | `S-PLAN-bucket`, `S-PLAN-todo`, `S-PLAN-nada` | M10 |
| Formulario | `S-W-mode`, `S-W-model`, `S-W-noted` | M9 |
| | `S-C-trace`, `S-C-clear` | M8 |
| | `S-LIB-off` | N05 fuera |
| | `S-PSA-off` | N11 fuera (**H5**) |
| | `S-G-off`, `S-G-bx` | M11/M12 |
| *Add-back* | `S-A-libvote` (0,5) · `S-A-board` | M6 y M9 (`form_weights=board`) |
| Sensibilidad | `S-T-<umbral>` (0,35-0,55), `S-FM-<x>` (1,0/1,5/2,0), `S-TW-<tramos>` | **no son ablaciones**; se rotulan así |

- **Compuerta:** cada `id` genera un `spec` válido; una prueba comprueba que ninguna variante
  modifica `protocol.PARAMS` (se copia, nunca se muta) y que `S-PSA-off` da **0 filas distintas**
  respecto a A0 (H5).
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/configs/variantes_sim.yaml`,
> `Ablation_study/harness/variants.py` y `Ablation_study/ablacion_tests/test_variants.py`;
> 50 configuraciones válidas, `PARAMS` inmutable y `S-PSA-off` con 0 filas distintas.

### PASO 2.3 — `harness/stats.py` y `harness/classify.py` [CODEX]
- Todo lo de §4.5 y la regla mecánica de §4.6. `classify.classify(deltas, ci, ...) -> veredicto`.
- **Compuerta:** pruebas con datos sintéticos de respuesta conocida: (a) reproduce el ranking
  oficial al 1e-12; (b) 6 discordantes a favor y 0 en contra → McNemar p = 0,03125; (c) un
  `Δ` de 0 exacto → `SOBRA`; (d) un `IC` que cruza 0 con `Δ` grande → `INDETERMINADA`; (e) la
  tabla de detectabilidad se genera y es monótona.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/harness/stats.py`,
> `Ablation_study/harness/classify.py` y `Ablation_study/ablacion_tests/test_stats.py`; seis
> pruebas sintéticas cubren ranking, McNemar, veredictos, detectabilidad y Shapley.

### PASO 2.4 — Pruebas del arnés [CODEX]
- `ablacion_tests/`: identidad (2.1), inmutabilidad de `PARAMS`, `PREREGISTRO` congelado,
  catálogo completo (1.1), estadística (2.3). Se corre **como su propia suite**.
- **Compuerta:** `.venv/bin/python -m pytest -q -p no:cacheprovider Ablation_study/ablacion_tests`
  en verde, y `git status --short` sólo bajo `Ablation_study/`.
> Estado: hecho 2026-09-22. Evidencia: suite actual de 34 pruebas en verde registrada en
> `Ablation_study/results/tests_harness.json`. `git status` sólo añade a las rutas del estudio
> el cambio preexistente `M .dockerignore` ya documentado en §8.

### FASE 3 — Ablaciones de decisión y formulario (Tier S) [CODEX]

Todo por triplicado: `honest` (primario), `deployed` (contraste) y por cubo `bx`. Cada resultado
guarda `n`, modo, semilla y `spec`. Salidas en `results/S_*.json` y `results/S_*.csv`.

### PASO 3.1 — Ablaciones de una en una (*leave-one-out*) [CODEX]
- Corre todas las variantes de decisión, documentos, plan y formulario de PASO 2.2 frente a A0.
  Para cada una: Δ e IC de ranking, gate, F1, 5 componentes; McNemar; **lista de casos que
  cambian** con la regla de A0 y la de la variante (`rule`, `who`).
- **Compuerta:** A0 aparece en la tabla con Δ = 0; el número de filas de `S_loo.csv` = nº de
  variantes × 2 modos; sin NaN.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/S_loo.json` y
> `Ablation_study/results/S_loo.csv`; 66 filas, A0 con delta cero, sin valores no finitos y
> cambios por caso con reglas de ambos brazos.

### PASO 3.2 — Reparto por peldaño («cascade replay») [CODEX]
- Tabla, por modo y por cubo: cuántos casos decide cada peldaño y con qué acierto; y, para el
  voto, **el mismo resultado con «sí» constante** (H3) con su IC.
- **Compuerta:** reproduce cohorte 49/52 · grado 10/12 · voto 15/27 (honest) y 24/27 (deployed).
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/S_cascade.json` y
> `Ablation_study/results/S_cascade.csv`; reproduce 49/52, 10/12 y 15/27 (`honest`) o 24/27
> (`deployed`), y compara el voto con el suelo 18/27.

### PASO 3.3 — Factorial de decisión y Shapley [CODEX]
- Factorial completo 2⁶ sobre {M1, M2, M3, M4, E1, E3} (64 configuraciones × 2 modos). Salidas:
  `S_factorial.csv`, **valores de Shapley** del ranking y del gate por factor, e interacciones de
  segundo orden (p. ej. M4×`previous_notes`, E3×`radiology_report`).
- Escalera de construcción `F0→F1→F2→F3→A0` con el incremento de cada peldaño.
- **Compuerta:** la suma de Shapley = ranking(A0) − ranking(todo apagado) al 1e-9.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/S_factorial.json` y
> `Ablation_study/results/S_factorial.csv`; 128 filas, Shapley cierra con error máximo
> 1,11e-16, escalera F0-F3-A0 e interacciones de segundo orden.

### PASO 3.4 — Formulario [CODEX]
- Factorial `pesos(3) × confianza(2) × aterrizaje(2) × biblioteca(2)` = 24 configuraciones con la
  decisión de A0, más `S-A-board`. Reporta los 5 componentes por separado (H6, H7, H15).
- **Compuerta:** con A0 la fila reproduce los 5 componentes de PASO 0.1.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/S_formulario.json` y
> `Ablation_study/results/S_formulario.csv`; 24 combinaciones más `S-A-board` por modo, decisión
> congelada a A0 y cinco componentes ancla reproducidos exactamente.

### PASO 3.5 — Sensibilidad de parámetros [CODEX]
- Barridos de umbral, `fusion_mult` y tramos. Etiqueta **«sensibilidad, no ablación»**. Objetivo:
  saber si el veredicto de M5 depende de un parámetro ajustado sobre estos 91 (§4.8-1).
- **Compuerta:** cada barrido incluye el valor de A0 y lo reproduce.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/S_sensibilidad.json` y
> `Ablation_study/results/S_sensibilidad.csv`; 22 filas rotuladas como sensibilidad, con un
> valor A0 exacto en cada barrido y modo.

### PASO 3.6 — Robustez [CODEX]
- Repite 3.1 restringido a `dev` (64) y a `val` (27): tabla de **signo por partición**.
- Detectabilidad: cuántas decisiones netas exige cada ablación para ser significativa.
- **Compuerta:** `S_robustez.csv` con una fila por variante y columnas `signo_dev`, `signo_val`.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/S_robustez.json` y
> `Ablation_study/results/S_robustez.csv`; 33 variantes, particiones 64/27, signos por modo y
> umbral detectable de seis decisiones netas.

### PASO 3.7 — Lectura provisional del Tier S [CODEX]
- `results/LECTURA_S.md` (≤ 2 páginas): qué salió de H1-H8, H15 según la regla de §4.6, **con la
  columna «desviaciones respecto a lo pre-registrado»**. No propone cambios.
- **Compuerta:** cada hipótesis tiene «confirmada / refutada / indeterminada» y la ruta del CSV.
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/results/LECTURA_S.md` y
> `Ablation_study/results/S_veredictos.json`; nueve hipótesis clasificadas, 411 palabras y
> columna de desviaciones completa.

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
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/harness/graph_variants.py` y
> `Ablation_study/ablacion_tests/test_graph_variants.py`; nueve variantes compilan y alcanzan
> END, A0 conserva la topología y el contexto restaura la V4.

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
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/harness/run_arm.py`,
> `Ablation_study/harness/launch_arms.sh`, `Ablation_study/configs/brazos_llm.yaml` y
> `Ablation_study/runs/_smoke_L1/arm.json`; dry-run validado y smoke L1 con 2/2 salidas.

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
> Estado: hecho 2026-09-22. Evidencia: `Ablation_study/RUNBOOK_GPU.md`; incluye preflight,
> compuerta L0, orden de brazos, reanudación, regla de VRAM, validación, entrega y sesión de juez.

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
> Estado: hecho 2026-09-22. L0 tiene 91/91 salidas válidas, reproduce exactamente decisión,
> confianza, pesos y plan de Tier S, y su ranking coincide (`0.7607067167163322`). El registrador
> abrió exactamente el plan en 91/91 casos; hubo 0 activaciones de imagen, 0 reaperturas, 0
> empujones inferidos y 0 planes vacíos. Evidencia: `Ablation_study/results/L_L0.json`
> (`accepted: true`).

### PASO 5.2 — Resto de brazos [HUMANO-GPU] + [CODEX] valida
- `launch_arms.sh L1 L2 L3 L4 L5 L6 L7 L0p`. Tras cada uno, `validate_arm.py` (misma compuerta de
  91/91 y `accepted`).
- **Compuerta:** `results/L_<brazo>.json` para los ocho, cada uno con `accepted: true`. Un brazo con
  `accepted: false` guarda su `blocker` legible y se relanza sólo ése.
> Estado: hecho 2026-09-22. Los ocho brazos tienen 91/91 salidas, contrato válido y
> `accepted: true`. Evidencia: `Ablation_study/results/L_L1.json` a
> `Ablation_study/results/L_L7.json` y `Ablation_study/results/L_L0p.json`.

### PASO 5.3 — D y F con LLM [CODEX]
- Δ de cada brazo frente a L0 con la estadística de §4.5, y **la diferencia L−S** (por brazo, si
  el LLM cambia alguna decisión o forma respecto al simulador). Salidas `results/L_efectos.csv`.
- Ruido de fondo: L0 vs L0' (la decisión debe ser idéntica; si no, se publica cuánto).
- **Compuerta:** cada brazo tiene su fila y `L0−L0'` está calculado.
> Estado: hecho 2026-09-22. Ningún brazo cambió decisiones; L0 y L0p son idénticos en D/F.
> L2 cambió el plan/pesos en 34 casos y la confianza en uno (`Δrank=0.0009745`); L4 cambió
> plan/pesos en 23 (`Δrank=0.0000912`). Evidencia: `Ablation_study/results/L_efectos.csv`,
> `Ablation_study/results/L_efectos.json` y `Ablation_study/harness/run_tier_l.py`.

### FASE 6 — Narrativa (Tier N/J)

### PASO 6.1 — Auditoría de la nota, sin juez [CODEX]
- `harness/audit_notes.py` pasa **los detectores de la V4** (`decide.process_language`,
  `guards.unsourced_grades`/`unsourced_values`) sobre las notas finales de todos los brazos, y
  cuenta: notas con lenguaje de proceso, con grado sin fuente, longitud, uso de `clinical_note`
  (`audit.fallback_note`), reintentos del presidente y del registrador.
- **Compuerta:** L0 reproduce 0 violaciones (referencia: 0/195 en la entrega); para L6 y L7 se
  publica cuántas aparecen sin la guardia (**H14**).
> Estado: hecho 2026-09-22. L0 y los brazos con guardias activas tienen 0 violaciones; L6
> expone 3 notas con grado sin fuente y L7, 2 con lenguaje de proceso. Evidencia:
> `Ablation_study/results/N_audit.csv`, `Ablation_study/results/N_audit.json` y
> `Ablation_study/harness/audit_notes.py`.

### PASO 6.2 — Sesión de juez [HUMANO-GPU]
- `harness/judge_session.sh`: con vLLM **apagado**, levanta Ollama `gemma4:e4b` y puntúa **todos
  los brazos que cambian la nota** (L0, L0', L1-L7) con `dev/score_with_judge.py` en
  `.venv-eval`, **3 pasadas**, orden aleatorizado y **sin descargar el modelo entre medias** (una
  recarga cambia la nota hasta ±0,12). Salidas `results/J_<brazo>_p<r>.json`.
- **Compuerta:** 9 brazos × 3 pasadas = 27 ficheros con `rationale_score` y casos juzgados. El
  script registra `api/ps` antes y después para demostrar que no hubo recarga.
> Estado: hecho 2026-09-23. Los 27/27 ficheros son validos y la residencia de Ollama
> quedo registrada antes y despues de la sesion en `results/J_session_*.json`.

### PASO 6.3 — Análisis de N [CODEX]
- Nota por caso = media de las 3 pasadas; EE del replicado (L0 vs L0') → **δ_N** de §4.6; Δ por
  brazo sobre los casos juzgados en ambos.
- **Compuerta:** `results/J_efectos.csv` y `δ_N` calculado y registrado en `BITACORA_ABLACION.md`.
> Estado: hecho 2026-09-23. Evidencia: `Ablation_study/results/J_efectos.csv`,
> `J_efectos.json`; margen narrativo `delta_N=0.030000`.

### FASE 7 — Síntesis

### PASO 7.1 — Tabla maestra [CODEX]
- `harness/classify.py` aplica **mecánicamente** §4.6 sobre S, L y J y escribe
  `results/tabla_maestra.{csv,json}`: una fila por intervención/mecanismo con Δ e IC en D, F, N;
  coste (Δ s/caso, Δ tokens, tomados de la telemetría de L0/`summary.jsonl`); veredicto; y las
  hipótesis que confirma o refuta.
- **Compuerta:** toda fila de §3.A-§3.C con Tier ≠ «—» tiene veredicto; los `INDETERMINADA` se
  listan aparte con el motivo (potencia).
> Estado: hecho 2026-09-23. La tabla contiene 29 intervenciones con veredicto
> y trazabilidad en `results/tabla_maestra.{csv,json}`.

### PASO 7.2 — Ablación conjunta (H16) [CODEX] + [HUMANO-GPU]
- `A_min` = la V4 sin **todo** lo veredicto `SOBRA` a la vez. Tier S primero (exacto). Si toca
  intervenciones del LLM, un brazo `L9` con LLM (humano) y juez opcional.
- Una ablación «neutra» por separado no garantiza que sea neutra junta: éste es el control.
- **Compuerta:** Δ de A_min frente a A0 con IC; si `Δ ≥ δ_rank`, se lista **qué par de
  intervenciones interactúa** (mediante el factorial de 3.3 o brazos intermedios).
> Estado: hecho 2026-09-23. `A_min` fue aceptada con brazo `L9`, delta de ranking
> `0.000000` e IC95 `[0.0, 0.0]`. H16: `confirmada`.

### PASO 7.3 — Informe [CODEX]
- `reports/INFORME_ABLACION_T1.md`: (1) resumen ejecutivo con **una tabla**: intervención ·
  veredicto · efecto en ranking (Δ, IC) · efecto en F y N · coste · confianza en el veredicto;
  (2) método en una página; (3) resultados por bloque con la escalera de construcción y Shapley;
  (4) el honest frente al deployed; (5) H1-H16 una a una, confirmadas o refutadas **sin
  reescribir la predicción**; (6) los sesgos de §4.8, con lo que impide concluir;
  (7) recomendaciones (mantener / retirar / simplificar / no se sabe) y qué costaría cada una.
- Figuras (`reports/figuras/`): tornado de Δ ranking con IC; barras de Shapley; dispersión
  coste-vs-Δ; escalera de construcción. Un solo tipo de gráfico por mensaje, con los datos en
  `results/`.
- **Compuerta:** cada afirmación numérica del informe se puede localizar en un fichero de
  `results/` (una prueba `test_informe_citas.py` comprueba que las cifras del resumen coinciden
  con `tabla_maestra.json`).
> Estado: hecho 2026-09-23. Informe, cuatro figuras y prueba de trazabilidad numerica en
> `Ablation_study/reports/` y `ablacion_tests/test_informe_citas.py`.

### FASE 8 — Cierre

### PASO 8.1 — Invariantes y capa operativa [CODEX]
- La V4 **no cambió**: recalcula `huella_v4.txt` y compáralo con el de PASO 0.1; `git status`
  sólo lista `Ablation_study/`; las suites de PASO 0.1 dan lo mismo.
- Capa operativa: con lo ya existente en la V4 (`common/tests/test_supervisor.py`, `PLAN_V4.md`),
  confirma que su clasificación `OPERATIVA` sigue en pie y que ninguna ablación de este estudio
  la ha tocado.
- **Compuerta:** `results/cierre.json` con `v4_intacta: true` y los conteos de pruebas.
> Estado: hecho 2026-09-23. `results/cierre.json`: V4 intacta, suites de referencia sin
> regresiones y 37 pruebas del estudio pasadas.

### PASO 8.2 — Preguntas abiertas y extensión [CODEX]
- `EXTENSION_T2_T3.md` (≤ 1 página): qué del arnés es reutilizable tal cual (estadística,
  clasificación, corrida de brazos) y qué hay que rehacer por tarea (catálogo, simulador). Lista
  de preguntas abiertas que el estudio dejó.
- **Compuerta:** el fichero existe y `PLAN` §7 marca F8 cerrada.
> Estado: hecho 2026-09-23. Evidencia: `Ablation_study/EXTENSION_T2_T3.md`; F8 cerrada.

---

## 7. Tabla de fases

| Fase | Contenido | Quién | Estado |
|---|---|---|---|
| F0 | línea base verificable, esqueleto, pre-registro | Codex | hecho |
| F1 | catálogo de intervenciones | Codex | hecho |
| F2 | arnés de simulación y estadística | Codex | hecho |
| F3 | ablaciones de decisión y formulario (Tier S) | Codex | hecho |
| F4 | arnés del grafo, runbook | Codex | hecho |
| F5 | corridas con LLM (8 brazos) | **humano-GPU**, Codex valida | hecho |
| F6 | narrativa: auditoría y juez | Codex + **humano-GPU** | hecho |
| F7 | tabla maestra, ablación conjunta, informe | Codex (+ humano-GPU para L9) | hecho |
| F8 | cierre e invariantes | Codex | hecho |

**Camino crítico:** F0 → F1 → F2 → F3 (ya contesta D y F, y H3, con sólo CPU) → F4 → F5 (L0 gobierna
el resto) → F6 → F7 → F8. F3 no depende de F4-F6: **si el tiempo de GPU falta, el estudio
contesta igualmente a la pregunta de exactitud (D y F) con F0-F3 y sólo queda sin medir N**.

---

## 8. Registro de avance y bloqueos

| Fecha | Paso | Qué se cerró | Evidencia en disco |
|---|---|---|---|
| 2026-09-21 | — | Plan escrito | `Ablation_study/PLAN_ABLACION_T1.md` |
| 2026-09-21 | 0.1 | Línea base verificable: rama correcta, huella V4, anclajes `deployed`/`honest` reproducidos y suites V4 existentes en verde. La ruta `version_final_reto_send_v4/tests` no existe en este checkout. | `Ablation_study/results/huella_v4.txt`; `Ablation_study/results/anclas.json`; `Ablation_study/results/tests_base.json` |
| 2026-09-21 | 0.2 | Esqueleto, rutas y `.gitignore`: paquete importable, rutas del estudio reutilizando `version_final_reto.task_1.agent.paths`, y `conftest.py` para pruebas futuras. | `Ablation_study/__init__.py`; `Ablation_study/harness/paths.py`; `Ablation_study/ablacion_tests/conftest.py` |
| 2026-09-21 | 0.3 | Pre-registro congelado con pregunta, regla de veredicto, hipótesis H1-H16 y variantes S/L; prueba de congelación en verde. | `Ablation_study/PREREGISTRO.md`; `Ablation_study/results/preregistro.sha256`; `Ablation_study/results/preregistro_pre_desviaciones.sha256`; `Ablation_study/ablacion_tests/test_preregistro.py` |
| 2026-09-21 | 1.1 | Catálogo legible por máquina con los 34 IDs de §3.A-§3.C, validación de contrato y correspondencia completa con los nodos del grafo V4 compilado sin MCP real. Compuerta: 2 pruebas del estudio pasadas. | `Ablation_study/configs/intervenciones_t1.yaml`; `Ablation_study/harness/catalogo.py`; `Ablation_study/ablacion_tests/test_catalogo.py` |
| 2026-09-22 | 1.2 | Registro estructural completo para §3.D, N01, M7, G4-G5 y G7; cada elemento tiene justificación no vacía y la lista exacta se valida al cargar. | `Ablation_study/configs/intervenciones_t1.yaml`; `Ablation_study/harness/catalogo.py`; `Ablation_study/ablacion_tests/test_catalogo.py` |
| 2026-09-22 | 2.1 | Simulador Tier S parametrizable con `VariantSpec` inmutable, puntuación oficial enriquecida e identidad exacta con A0 V4 en ambos modos; recorrido sin puntuación de los 195 casos. | `Ablation_study/harness/sim.py`; `Ablation_study/ablacion_tests/test_sim_identity.py` |
| 2026-09-22 | 2.2 | Registro declarativo de 50 configuraciones Tier S y constructor inmutable; todas generan un `VariantSpec`, ninguna muta `protocol.PARAMS` y `S-PSA-off` produce 0 filas distintas frente a A0. | `Ablation_study/configs/variantes_sim.yaml`; `Ablation_study/harness/variants.py`; `Ablation_study/ablacion_tests/test_variants.py` |
| 2026-09-22 | 2.3 | Estadística pareada y clasificación mecánica: bootstrap fijo, McNemar/signos, Wilcoxon común, Holm, Shapley y detectabilidad; las referencias sintéticas pre-registradas pasan. | `Ablation_study/harness/stats.py`; `Ablation_study/harness/classify.py`; `Ablation_study/ablacion_tests/test_stats.py` |
| 2026-09-22 | 2.4 | Compuerta integral del arnés: 13 pruebas pasadas. El estado del árbol conserva únicamente la excepción preexistente y documentada de `.dockerignore` fuera de `Ablation_study/`. | `Ablation_study/results/tests_harness.json` |
| 2026-09-22 | 3.1 | LOO de 33 configuraciones en `honest` y `deployed`, 10.000 bootstraps pareados y desglose por cubo; 66 filas sin NaN, A0 con delta cero y cambios de decisión trazados por regla. | `Ablation_study/results/S_loo.json`; `Ablation_study/results/S_loo.csv` |
| 2026-09-22 | 3.2 | Replay de la cascada por modo y cubo, incluidos los aciertos del voto sustituido por «sí» y su IC; reproduce todos los recuentos ancla por peldaño. | `Ablation_study/results/S_cascade.json`; `Ablation_study/results/S_cascade.csv` |
| 2026-09-22 | 3.3 | Factorial completo 2^6 en ambos modos, Shapley de ranking/gate, interacciones de segundo orden y escalera F0-F3-A0; la suma de Shapley cierra al máximo error 1,11e-16. | `Ablation_study/results/S_factorial.json`; `Ablation_study/results/S_factorial.csv` |
| 2026-09-22 | 3.4 | Factorial del formulario 3×2×2×2 más `S-A-board`, con decisión congelada a A0 y desglose por cubo; A0 reproduce exactamente los cinco componentes ancla. | `Ablation_study/results/S_formulario.json`; `Ablation_study/results/S_formulario.csv` |
| 2026-09-22 | 3.5 | Barridos de umbral, multiplicador E3 y tramos en ambos modos, etiquetados como sensibilidad y no ablación; cada familia contiene y reproduce su valor A0. | `Ablation_study/results/S_sensibilidad.json`; `Ablation_study/results/S_sensibilidad.csv` |
| 2026-09-22 | 3.6 | Robustez de las 33 variantes LOO en DEV/VAL, signos para `honest` y `deployed`, McNemar y distancia a la detectabilidad; particiones verificadas en 64/27. | `Ablation_study/results/S_robustez.json`; `Ablation_study/results/S_robustez.csv` |
| 2026-09-22 | 3.7 | Lectura provisional Tier S de H1-H8 y H15, con regla mecánica, fuentes CSV y desviaciones; 411 palabras, sin propuestas de cambio. | `Ablation_study/results/LECTURA_S.md`; `Ablation_study/results/S_veredictos.json`; `Ablation_study/harness/summarize_tier_s.py` |
| 2026-09-22 | 4.1 | Gestor reversible de variantes del grafo para nodos, guardias, imagen y presidente; nueve variantes llegan a END con modelo mudo, preservan topología y restauran todos los símbolos parcheados. | `Ablation_study/harness/graph_variants.py`; `Ablation_study/ablacion_tests/test_graph_variants.py` |
| 2026-09-22 | 4.2 | Runner de brazos en el mismo proceso que V4, manifiesto con huellas, lanzador serie con comprobación de procesos GPU y `--resume`; dry-run y brazo L1 simulado con 2/2 salidas validados. | `Ablation_study/harness/run_arm.py`; `Ablation_study/harness/launch_arms.sh`; `Ablation_study/configs/brazos_llm.yaml`; `Ablation_study/runs/_smoke_L1/arm.json`; `Ablation_study/ablacion_tests/test_run_arm.py` |
| 2026-09-22 | 4.3 | Runbook autónomo para ejecutar F5-F6: preflight, VRAM, perfil fijo, orden L0-resto, reanudación, compuertas, entrega y juez tras liberar vLLM. | `Ablation_study/RUNBOOK_GPU.md` |
| 2026-09-22 | 5.1 (preparación) | Validador de brazos implementado y probado contra un smoke de dos casos: contrato, puntuación, identidad L0-S, auditoría de actas y `accepted/blocker`. La corrida humana L0 aún no existe (0/91), por lo que la compuerta permanece abierta y no se lanzan los demás brazos. | `Ablation_study/harness/validate_arm.py`; `Ablation_study/ablacion_tests/test_validate_arm.py`; `Ablation_study/results/L_L0.json` |
| 2026-09-22 | 4.2 (corrección) | El lanzador valida la lista completa antes de usar la GPU y conserva una lista inmutable; un argumento accidental `source` se rechaza antes de iniciar L0. | `Ablation_study/harness/launch_arms.sh`; `Ablation_study/ablacion_tests/test_run_arm.py` |
| 2026-09-22 | 5.1 | L0 validado con 91/91 salidas: contrato, puntuación oficial e identidad Tier S exactos; registrador 91/91 conforme al plan y auditoría sin activaciones de imagen, reaperturas, empujones ni planes vacíos. | `Ablation_study/results/L_L0.json` |
| 2026-09-22 | 5.2 | L1-L7 y L0p validados con 91/91 salidas y `accepted: true`; L5 conserva en el resumen el timeout y su reintento, resueltos por último registro por caso. | `Ablation_study/results/L_L1.json` a `L_L7.json`; `Ablation_study/results/L_L0p.json` |
| 2026-09-22 | 5.3 | Comparación pareada Tier L con 10.000 bootstraps: cero cambios de decisión en todos los brazos y ruido L0-L0p nulo; L2 y L4 producen cambios pequeños de formulario. | `Ablation_study/results/L_efectos.csv`; `Ablation_study/results/L_efectos.json` |
| 2026-09-22 | 6.1 | Auditoría con detectores V4: L0 sin violaciones; quitar G1-G2 expone 3 grados sin fuente y quitar G3 expone lenguaje de proceso en 2 notas. | `Ablation_study/results/N_audit.csv`; `Ablation_study/results/N_audit.json` |
| 2026-09-22 | 6.2 (preparación) | Sesión de juez reanudable, tres órdenes aleatorizados fijos, comprobación de vLLM, residencia Ollama y calendario verificado de 27 evaluaciones. | `Ablation_study/harness/judge_session.sh`; `Ablation_study/ablacion_tests/test_tier_l_analysis.py` |

| 2026-09-23 | 6.2 | Sesion unica del juez completada: 27/27 artefactos validos y residencia registrada. | `Ablation_study/results/J_session_validation.json`; `J_session_before.json`; `J_session_after.json` |
| 2026-09-23 | 6.3 | Efectos narrativos pareados, replica y margen de equivalencia calculados. | `Ablation_study/results/J_efectos.csv`; `J_efectos.json` |
| 2026-09-23 | 7.1 | Tabla maestra con 29 filas y clasificacion mecanica completa. | `Ablation_study/results/tabla_maestra.csv`; `tabla_maestra.json` |
| 2026-09-23 | 7.2 | Ablacion conjunta `L9` aceptada; H16 `confirmada`. | `Ablation_study/results/A_min_config.json`; `A_min.json` |
| 2026-09-23 | 7.3 | Informe final y cuatro figuras trazables generados. | `Ablation_study/reports/INFORME_ABLACION_T1.md`; `reports/figuras/` |
| 2026-09-23 | 8.1 | Huella, suites V4, suite del estudio y capa operativa verificadas. | `Ablation_study/results/cierre.json`; `huella_v4_cierre.txt` |
| 2026-09-23 | 8.2 | Extension y preguntas abiertas para T2/T3 documentadas. | `Ablation_study/EXTENSION_T2_T3.md` |

**Bloqueos:** ninguno. Todas las compuertas F0-F8 estan cerradas.

**Aviso del árbol:** al iniciar 1.1, `git status --short` ya mostraba `M .dockerignore`
(`Ablation_study/` añadido a sus exclusiones). El paso 1.1 no modificó esa ruta; todos sus
cambios están bajo `Ablation_study/`. La corrida L0 dejó además modificado
`resources/guidelines_db/chroma.sqlite3`: la comparación lógica con HEAD muestra iguales todas
las tablas salvo la contabilidad de bloqueos `acquire_write` (9175 frente a 9572 filas), sin
cambios en los datos de guías. Se conserva para no revertir una escritura de la corrida; evidencia
en `Ablation_study/results/guidelines_db_runtime_write.json`.

---

## 9. Trampas conocidas (por qué el plan es como es)

1. **`deployed` engaña.** Los expertos vieron las etiquetas de estos 91: el voto acierta 24/27
   en `deployed` y 15/27 en `honest`. Toda conclusión, de `honest`.
2. **Un caso por proceso** si alguna vez se puntúan expertos en vivo: los imputadores llevan
   `sample_posterior=True` y su `RandomState` viaja en el pickle, así que puntuar dos veces el
   mismo caso en el mismo intérprete da números distintos. Aquí se usa la caché, determinista;
   si un paso puntúa en vivo, un proceso por caso y por brazo (`verification/expert_worker.py`).
3. **El `case_id` va dentro del prompt** (`Board.HEAD`): dos ids = dos prompts = dos
   trayectorias. Mismo `case_id` en todos los brazos (vienen de los ficheros).
4. **El juez cambia de nota.** Δ 0,012 entre dos pasadas seguidas sin recarga; hasta ±0,12 tras
   recargar. Comparar sólo dentro de una sesión, con réplicas, y usar los componentes
   deterministas para D y F.
5. **vLLM y Ollama no caben a la vez.** El síntoma es un aborto en segundos con `0/195` salidas y
   `ZeroDivisionError` al puntuar; `pytest` sigue en verde. Ollama deja el modelo residente:
   mira `--query-compute-apps`.
6. **`--count-missing` siempre** al puntuar corridas reales: excluir los casos sin salida da un
   número optimista.
7. **El simulador supone que el registrador abre exactamente el plan.** L0 lo verifica (91/91);
   si no se cumple, S no representa al agente.
8. **Los parches del arnés se hacen sobre los nombres del módulo del grafo**, no sobre `decide` o
   `guards`: `graph.py` los importó por nombre y las clausuras los buscan ahí.
9. **Si no quieres verlo en la salida, no lo escribas en un prompt.** El modelo copia frases de
   ejemplo. Este estudio **no cambia prompts**.
10. **Reglas y umbral ajustados sobre los mismos 91** (§4.8-1): el Δ de M1-M5 es una cota
    optimista de lo que valdrán en el test.
11. **`pytest` de varias suites a la vez falla** por el nombre `tests` (§0.7).
12. **Sandbox de Codex:** si muere en ~22 s con `bwrap: loopback: Failed RTM_NEWADDR`, es el
    sysctl `kernel.apparmor_restrict_unprivileged_userns`; no es un fallo del plan.

---

## 10. Prompt de arranque (lo único que se pega en Codex)

> Lee `Ablation_study/PLAN_ABLACION_T1.md`. §0 y §1-§5 primero, por rangos. Ejecuta **SÓLO** el
> PASO `<N.M>`: localízalo con `grep -n '^### PASO' Ablation_study/PLAN_ABLACION_T1.md` y léelo
> con `sed -n`. No toques nada fuera de `Ablation_study/`, no hagas commit, y no marques el paso
> hecho sin su compuerta y su evidencia en disco. Al terminar actualiza §7, §8 y el `> Estado:`
> del paso.
