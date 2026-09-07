# Pizarra multi-experto con moderador — tarea 1 (decisión de biopsia)

> ## Resultado final
>
> Evaluador **oficial**, juez de razonamiento desactivado, **91 casos
> etiquetados**, temperatura 0, casos sin salida contados como fallo.
>
> | | referencia repo (T=1.0) | baseline (T=0) | pizarra v1 | **pizarra v2** |
> |---|---|---|---|---|
> | `ranking_score` | 0.6351 | 0.6428 | 0.6749 | **0.7125** |
> | sólo split `dev` (64) | — | 0.6362 | 0.6592 | **0.6918** |
> | sólo split `val` (27) | — | 0.6585 | 0.7126 | **0.7615** |
>
> **+0.0697 sobre el control a la misma temperatura** y +0.0774 sobre la
> referencia histórica del repositorio. Por caso: **63 suben, 8 bajan, 20
> empatan — prueba de signos p < 0.00001**. La puerta de decisión recupera 9
> casos y pierde 3.
>
> 91/91 casos entregados · 0 fallos · 0 respaldos deterministas · 29.3 s/caso.


Segunda generación de [`../solution_task_one`](../solution_task_one). Mismo
concepto —expertos independientes que escriben por turnos en una pizarra
compartida y un presidente que decide— con tres cambios de fondo, cada uno
motivado por una medición y no por una intuición:

| # | Cambio | Por qué | Evidencia |
|---|---|---|---|
| 1 | **Un moderador** abre la sesión fijando la agenda y la cierra comprobando suficiencia y consenso; puede **reabrir la pizarra** | la v1 era una cadena de montaje: cada experto hablaba una vez y el presidente decidía con lo que hubiera | §3 |
| 2 | **Random Forest** sustituye al kNN como experto de clasificación | el kNN era la peor de once familias probadas | +0.066 de proxy de ranking, **10 de 10 semillas**, Wilcoxon p=0.002 (§4) |
| 3 | Se usan **los tres ficheros de entrada**, cada uno por su vía | la v1 sólo explotaba `structured-prompt.json` | §5 |

Autocontenido y borrable: importa de `chimera_agent_baseline` pero no lo
modifica. Lo único bloqueado por el reglamento del reto —`output/schema.py`— es
lo que valida la salida.

---

## 1. La arquitectura

```
 START
   │
   ▼
 [1] INTAKE ──────────── structured-prompt.json renderizado con la plantilla upstream
   ▼
 [2] EXPERT-PRIOR ────── Random Forest sobre 8 variables: p(biopsia) ± dp + entropía
   ▼                     (modelo elegido por ablación, §4)
 [3] EXPERT-PROTOCOL ─── criterio EAU del cubo clínico del paciente, con su acierto medido
   ▼
 [4] EXPERT-IMAGE ────── FeatureStore + run_predictor sobre los embeddings congelados
   ▼
 [5] MODERATOR (open) ── fija la AGENDA: qué documento y qué pregunta debe contestar
   ▼
 [6] LLM-1 GAP-ANALYST ─ sólo duda ⇅ search_guidelines (RAG sobre la guía EAU)
   ▼
 [7] LLM-2 EVIDENCE ──── el único que abre documentos ⇅ herramientas MCP
   ▼
 [8] MODERATOR (close) ─ ¿suficiente? ¿consenso?
   │        │
   │        └── reabrir ──► vuelve a [6] con la ronda + 1
   ▼
 [9] LLM-3 CHAIR ─────── decide y emite el formulario validado contra Task1Output
   ▼
  END
```

Los tres expertos deterministas hablan **antes** que ningún LLM, a propósito:
así la agenda se fija sobre evidencia cuantificada y no sobre la primera
impresión de un modelo de lenguaje.

---

## 2. Por qué una pizarra, y no una cadena de prompts

La arquitectura de pizarra no es una metáfora suelta: es un patrón con nombre y
con cincuenta años de literatura. Nació en **Hearsay-II** para reconocimiento
del habla (Erman, Hayes-Roth, Lesser y Reddy, *The Hearsay-II Speech-Understanding
System: Integrating Knowledge to Resolve Uncertainty*, ACM Computing Surveys
12(2), 1980), se formalizó en Hayes-Roth (*A blackboard architecture for
control*, Artificial Intelligence 26(3), 1985) y se sistematizó en Nii
(*Blackboard Systems*, AI Magazine 7(2), 1986). Sus tres propiedades son
exactamente las que pide este reto:

1. **Fuentes de conocimiento heterogéneas y desacopladas.** Un clasificador
   estadístico, una regla de guía clínica, una cabeza sobre embeddings y varios
   LLM no comparten representación ni pueden llamarse entre sí; comparten un
   medio.
2. **Control oportunista.** Qué se hace después depende del estado de la
   pizarra, no de un guion fijo. Es literalmente el papel del moderador.
3. **Traza auditable por construcción.** El reto evalúa el razonamiento contra
   los campos de entrada reales y penaliza lo no soportado: una pizarra
   persistida *es* esa traza.

En la literatura reciente de LLM el mismo patrón reaparece como *multi-agent
debate* (Du, Li, Torralba, Tenenbaum y Mordatch, *Improving Factuality and
Reasoning in Language Models through Multiagent Debate*, arXiv:2305.14325,
2023; Liang et al., arXiv:2305.19118, 2023), como conversación entre agentes
con un gestor de grupo (Wu et al., *AutoGen*, arXiv:2308.08155, 2023), y como
procedimiento operativo con roles (Hong et al., *MetaGPT*, arXiv:2308.00352,
2023). En el dominio clínico, **MedAgents** (Tang et al., arXiv:2311.10537,
2023) y **MDAgents** (Kim et al., *MDAgents: An Adaptive Collaboration of LLMs
for Medical Decision-Making*, NeurIPS 2024) muestran que la colaboración
estructurada entre roles mejora el razonamiento médico de cero disparos.

**Y la advertencia, que es la razón de que aquí se mida todo.** Wang et al.
(*Rethinking the Bounds of LLM Reasoning: Are Multi-Agent Discussions the
Key?*, ACL 2024) encuentran que un agente único con un buen prompt iguala a
muchas configuraciones de discusión multi-agente. Por eso la comparación de
este paquete no es "pizarra contra nada", sino contra el ReAct del baseline y
contra la pizarra sin moderador, con el evaluador oficial y con contraste
pareado.

---

## 3. El moderador: suficiencia y consenso

`moderator.py` interviene dos veces.

**Al abrir** fija la agenda: qué documentos hay que abrir y **qué pregunta debe
contestar cada uno para este paciente**. Sin eso, L2 recupera a bulto — es lo
que se midió en la v1: las cuatro secciones abiertas en el 100 % de los casos.
Como `tool_score` del evaluador es **precisión** sobre las secciones reveladas,
recuperar de más se paga y recuperar de menos es gratis.

**Al cerrar** responde una pregunta procedimental, no clínica: *¿este
expediente está en condiciones de decidirse?* Comprueba dos cosas que se
confunden con facilidad:

* **suficiencia** — ¿se abrió lo que la agenda pedía y contestó?
* **consenso** — ¿coinciden las posturas del prior, del criterio de protocolo y
  de la evidencia recuperada?

Si falla cualquiera de las dos y quedan rondas, **reabre la pizarra**: los
mismos expertos vuelven a intervenir viendo lo que se escribió antes y lo que
el moderador ha declarado que falta.

### Por qué el moderador es híbrido y no un LLM suelto

El estado de la mesa —quién dijo qué, qué documentos se abrieron, si la agenda
se cumplió— **se calcula de forma determinista** y se le entrega ya contado. El
LLM sólo aporta la lectura clínica de si lo recuperado *responde* a la pregunta.

La razón es empírica: Huang et al. (*Large Language Models Cannot Self-Correct
Reasoning Yet*, ICLR 2024) muestran que los LLM no saben juzgar de forma fiable
si su propia respuesta necesita corrección sin señal externa, y Turpin et al.
(*Language Models Don't Always Say What They Think*, NeurIPS 2023) que su
explicación puede no reflejar lo que realmente usaron. Un moderador que se
limitara a preguntarle al modelo "¿tienes bastante información?" heredaría
las dos patologías. Aquí la parte contable es código, y si el LLM no devuelve
un JSON legible la regla determinista decide igual: **el moderador nunca puede
bloquear un caso**.

El diseño de "conferencia con rondas hasta el consenso" sigue a **ReConcile**
(Chen, Saha y Bansal, *ReConcile: Round-Table Conference Improves Reasoning via
Consensus among Diverse LLMs*, arXiv:2309.13007, 2023), y la idea de un
moderador que **adapta el esfuerzo** —decidir solo cuándo es fácil, convocar a
la mesa cuando es difícil— es la de MDAgents (Kim et al., NeurIPS 2024). La
diferencia aquí es que el criterio de reapertura no es la confianza declarada
por un LLM, sino el estado verificable de la agenda.

---

## 4. El experto de clasificación: por qué Random Forest, medido

`ablation/` contiene el estudio completo: **15 familias de clasificador × 6
conjuntos de variables**, validación cruzada estratificada repetida 5×5,
out-of-fold, con imputación y escalado ajustados dentro de cada partición.

La métrica primaria **no es la exactitud**. El `ranking_score` de la tarea 1 es
`(mean_case_score + F1(yes)) / 2`, así que se reporta un *proxy de ranking* que
pesa las dos mitades como el evaluador oficial. Optimizar exactitud a secas
lleva a un clasificador que difiere demasiado y hunde el F1 de la clase
positiva.

### Resultado (mejor conjunto de cada familia, con el criterio de protocolo)

| familia | proxy | acc | F1(yes) | AUC | ECE |
|---|---|---|---|---|---|
| **ExtraTrees** | 0.7315 | 0.791 | 0.835 | 0.848 | 0.093 |
| GaussianNB | 0.7278 | 0.780 | 0.836 | 0.842 | 0.167 |
| RF-balanceado | 0.7125 | 0.769 | 0.814 | 0.842 | 0.070 |
| kNN-10-dist *(el de la v1)* | 0.7075 | 0.747 | 0.822 | 0.805 | 0.185 |
| Random Forest | 0.7047 | 0.747 | 0.816 | 0.820 | 0.068 |
| **Probabilistic RF** | 0.6971 | 0.736 | 0.810 | 0.820 | **0.063** |
| DeepEnsemble (MLP) | 0.6984 | 0.747 | 0.803 | 0.804 | 0.200 |
| Gaussian Process | 0.6821 | 0.703 | 0.806 | 0.811 | 0.047 |
| ... | | | | | |

> Cuidado al leer esta tabla: cada fila es el **mejor conjunto de variables** de esa
> familia con **una** semilla de validación cruzada. Random Forest aparece aquí con
> 0.7047 porque su mejor conjunto en esa semilla concreta fue `A-core+C+B`; promediado
> sobre diez semillas y sobre `A-core`, que es la configuración que se despliega, queda
> en 0.7165 — la primera. Ése es justamente el problema que arregla el apartado
> siguiente.

### Y la corrección que cambia el veredicto: estabilidad entre semillas

Elegir el máximo de una tabla de 90 filas medida sobre 91 casos es una forma
conocida de auto-engañarse. `ablation/stability.py` repite la comparación de
los finalistas con **10 semillas distintas** de la validación cruzada:

| configuración | proxy medio | sd | veces 1ª |
|---|---|---|---|
| **A-core (8v) · Random Forest** | **0.7165** | 0.0136 | 2 |
| A-core+B(PCA8) · ExtraTrees | 0.7163 | 0.0146 | 4 |
| A-core · RF-balanceado | 0.7118 | 0.0118 | 1 |
| A-core · ExtraTrees | 0.7097 | 0.0137 | 1 |
| A-core · Probabilistic RF | 0.7074 | 0.0222 | 1 |
| A-core · kNN-5 | 0.6956 | 0.0167 | 1 |
| A-core+C (42v) · RF-balanceado | 0.6940 | 0.0106 | 0 |
| **A-core · kNN-10-dist** *(la v1)* | **0.6507** | 0.0160 | 0 |

Contrastes pareados sobre las 10 semillas (Wilcoxon):

| comparación | Δ | gana | p |
|---|---|---|---|
| RF **vs kNN-10-dist** (el experto de la v1) | **+0.0658** | 10/10 | **0.002** |
| RF vs kNN-5 | +0.0209 | 9/10 | 0.006 |
| RF vs A-core+**C** (añadir el EHR parseado) | +0.0225 | 8/10 | 0.020 |
| RF vs Probabilistic RF | +0.0091 | 6/10 | 0.148 |
| ExtraTrees+**B** vs ExtraTrees (añadir embeddings) | +0.0065 | 5/10 | 0.322 |
| RF vs ExtraTrees+B | +0.0002 | 5/10 | 1.000 |

**Lo que responde esto, punto por punto:**

* **Sí, un Random Forest funciona mejor** que el kNN que llevaba la v1, y la
  diferencia no es de una partición: gana en las diez. Breiman (*Random
  Forests*, Machine Learning 45(1), 2001) y Geurts, Ernst y Wehenkel
  (*Extremely randomized trees*, Machine Learning 63(1), 2006) siguen siendo la
  referencia en tabular pequeño y ruidoso, y eso es exactamente este problema.
* **RF y ExtraTrees empatan** (p = 1.000). Entre dos que empatan se elige el
  más simple: RF sobre las 8 variables, sin PCA y sin depender del fichero de
  embeddings.
* **El Probabilistic Random Forest no gana, pero calibra mejor** (ECE medio
  sobre las diez semillas: 0.076 frente a 0.104 de RF, ambos sobre `A-core`). Su idea —tratar cada valor como `N(mu, sigma)` y
  propagar al objeto por las dos ramas con el peso de cada lado (Reis, Baron y
  Shahaf, *Probabilistic Random Forest: A Machine Learning Algorithm for Noisy
  Data Sets*, The Astronomical Journal 157(1):16, 2019)— encaja de fábrica con
  este dataset: los ausentes (`sigma = inf`) se reparten 50/50 en vez de
  imputarse, y variables como `vol` (segmentación automática), `psad` (que
  propaga el error de `psa/vol`) o `cspca` (salida de un detector) son
  estimaciones con error, no medidas. Está implementado en
  [`experts/prf.py`](experts/prf.py) en numpy puro —sin dependencias nuevas,
  que importa porque el contenedor va sin red— y las sigmas están declaradas
  una a una con su motivo en [`experts/uncertainty.py`](experts/uncertainty.py).
  Se deja en el repositorio como alternativa medida, no como el ganador.
* **Ni el EHR parseado ni los embeddings ayudan.** Con 91 casos, 42 o 53
  variables es demasiado: es el régimen que la regla de eventos por variable
  (Peduzzi et al., *A simulation study of the number of events per variable in
  logistic regression analysis*, J Clin Epidemiol 49(12), 1996) desaconseja, y
  la medición lo confirma. Los embeddings de MRI aportan +0.007 ± 0.015, que es
  ruido — coherente con que la etiqueta sea **la decisión de un urólogo**, que
  miró el PI-RADS del informe, no un vector de 1024 dimensiones.

### La incertidumbre que se entrega, y por qué así

Un veredicto sin incertidumbre no le sirve a un LLM: si no sabe cuánto fiarse,
no puede integrarlo. Se reportan **dos magnitudes distintas, por separado**:

* **epistémica** `dp` — desviación típica de la probabilidad entre los miembros
  del bagging: cuánto se movería la respuesta con otra muestra de
  entrenamiento. Es la receta de los *deep ensembles* (Lakshminarayanan,
  Pritzel y Blundell, *Simple and Scalable Predictive Uncertainty Estimation
  using Deep Ensembles*, NeurIPS 2017) aplicada a un estimador clásico.
* **aleatoria** `H` — entropía normalizada de la predicción media: cuánto se
  contradijo el urólogo entre pacientes que el modelo no distingue. No baja con
  más datos del mismo tipo.

La separación sigue a Depeweg et al. (*Decomposition of Uncertainty in Bayesian
Deep Learning for Efficient and Risk-sensitive Learning*, ICML 2018). **No se
suman en cuadratura**: mezclar la varianza de Bernoulli con un error estándar
produce una barra de ±0.45 en todos los casos, que no informa de nada (se probó
y se descartó).

La **escalera operativa** que sale de ahí es lo que de verdad usa el presidente,
y está medida sobre los 91 casos:

| tramo | criterio | casos | acierto |
|---|---|---|---|
| `firm` | `p ± 1.96·dp` no cruza 0.5 | 28 | **1.000** |
| `supports` | `p ± dp` no cruza 0.5 | 20 | 0.800 |
| `discuss` | `p ± dp` cruza 0.5 | 43 | 0.488 |

Es decir: en el 31 % de los casos el clasificador se moja y **no falló ninguno**;
en el 47 % declara que no distingue, y ahí la decisión tiene que salir de los
documentos. Eso es abstención informada, que es la propiedad que Guo et al.
(*On Calibration of Modern Neural Networks*, ICML 2017) y Niculescu-Mizil y
Caruana (*Predicting Good Probabilities With Supervised Learning*, ICML 2005)
señalan como la diferencia entre una probabilidad útil y un número.

---

## 5. Los tres ficheros de entrada, cada uno por su vía

| fichero | quién lo usa | cómo |
|---|---|---|
| `structured-prompt.json` | INTAKE (renderizado) y EXPERT-PRIOR (crudo) | el panel visible, íntegro |
| `prostate-…-clinical-data.json` | LLM-2 vía herramientas MCP | sólo lo que la agenda pide; produce `reveal_sequence` |
| `prostate-modality-level-neural-representations.json` | EXPERT-IMAGE | `FeatureStore` + `run_predictor`; devuelve un escalar, nunca los vectores |

`features.py` sabe además extraer el bloque C (el EHR parseado con expresiones
regulares) y el bloque B (embeddings), porque la ablación tenía que poder
probarlos. **La configuración desplegada no los usa** por lo que dice §4, pero
el código queda para cuando haya más casos etiquetados.

Un punto de transparencia: `reveal_sequence` se deriva de las llamadas MCP que
hace el agente, no de lo que lea un experto en el disco. Si un día se activara
el bloque C en el clasificador, el experto vería el expediente sin declararlo
como revelación — igual que el `tools/predictor.py` del baseline lee los
embeddings directamente. Lo que se puntúa sigue siendo lo que el agente pide y
cita; se declara aquí para que no haya ambigüedad.

---

## 6. Lo que se hereda de la v1 porque estaba medido

* **El criterio de protocolo por cubo clínico**
  ([`experts/protocol.py`](experts/protocol.py)): sin biopsiar → PI-RADS ≥ 3
  (24/24 aciertos); biopsia previa negativa → PI-RADS ≥ 4 (16/18); biopsia
  previa positiva → **el panel no lo determina** y el experto se abstiene
  explícitamente. Ver `../solution_task_one/CRITERIO_DIAGNOSTICO.md`.
* **`reveal_sequence` derivada de los `ToolMessage` reales**, honesta por
  construcción.
* **Respaldo determinista** en `decide.py`: ningún caso se queda sin salida.
  Un caso perdido cuesta doble en Grand Challenge.
* **No llamar a `get_family_history`**: el urólogo la reveló 0 de 91 veces.
* **La guardia anti-fabricación de L2**: si escribe un informe sin haber
  abierto nada, se le devuelve el turno.

---

## 7. Cómo se corre

```bash
source .venv/bin/activate

# estudio de ablación (CPU, ~1 min con 28 núcleos)
python delete_solution_one/solution_task_one_correction_claude/ablation/run_ablation.py
python delete_solution_one/solution_task_one_correction_claude/ablation/stability.py

# Monte Carlo: 3 muestras aleatorias de 30 casos, modelo cargado una sola vez
delete_solution_one/solution_task_one_correction_claude/runs/launch.sh mc \
    "--sample 30 --seeds 0 1 2"

# la corrida final sobre los 91 casos etiquetados
delete_solution_one/solution_task_one_correction_claude/runs/launch.sh full ""

# comparar contra el baseline sobre exactamente los mismos casos
python delete_solution_one/solution_task_one_correction_claude/analysis/montecarlo.py \
    --auto delete_solution_one/solution_task_one_correction_claude/runs

# la nota oficial
python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_solution_one/solution_task_one_correction_claude/runs/full/output
```

### Por qué Monte Carlo sobre 30 casos

Una corrida de los 91 cuesta cerca de una hora de GPU, e iterar sobre ella
invita a dos errores: mirar siempre los mismos casos —que acaban memorizados en
las decisiones de diseño— y confundir una diferencia de dos casos con una
mejora. Muestrear 30 al azar con una semilla distinta cada vez ataca las dos
cosas, y **el baseline se puntúa sobre exactamente los mismos casos de cada
muestra**, de modo que la comparación es pareada y la variabilidad de qué
pacientes tocaron se cancela.

---

## 7bis. Las cuatro iteraciones de Monte Carlo, y qué midió cada una

Tres muestras aleatorias de 30 casos por iteración, con el baseline puntuado
**sobre exactamente los mismos casos** (comparación pareada). El criterio de
parada era el que fijó el encargo: ventaja consistente, no una media favorable.

| it. | Δ vs baseline | gana | sd | qué se midió y qué se cambió después |
|---|---|---|---|---|
| 1 | +0.0226 | 2/3 | 0.032 | El moderador **nunca reabría** pese a no haber consenso: el LLM devolvía `reopen: false` en el 100 % de los casos. Y pedía las 4 secciones. → techo de agenda determinista + reapertura determinista |
| 2 | +0.0018 | 2/3 | 0.011 | El detector de postura de L2 leía la **cabecera** «AGAINST sampling this patient now» como si fuera la conclusión: marcaba `defer` en **88 de 90** casos, con lo que el consenso salía invertido. Además el presidente pesaba `dre` sin abrir el laboratorio (grounding 0.79). → token explícito `LEAN:` + guardia de grounding |
| 3 | +0.0233 | **3/3** | 0.012 | Con el consenso ya legible, apareció la fuga de fondo: en el cubo indeterminado el clasificador acertaba **0.900** en su tramo `supports` y el presidente lo anulaba hasta **0.400**. → standing medido del clasificador en el prompt del presidente |
| **4** | **+0.0453** | **3/3** | 0.012 | El standing arregló el tramo `firm` (0.5 → 1.0) pero no `supports`. → **reto mecánico**: si el presidente anula a un experto con historial y su razonamiento no cita ningún valor procedente de un documento recuperado, se le devuelve el turno. Se disparó en 2 de 64 casos y movió `supports` de 0.500 a 0.700 |

Progresión del cubo que decide la tarea (biopsia previa positiva, ~53 % de los
casos): 0.52 → 0.44 → 0.53 → **0.59**.

### Lo que las cuatro iteraciones enseñan sobre el diseño

**Ninguna de las cuatro correcciones fue un cambio de prompt "a ver si mejora".**
Las cuatro salieron de una medición que señalaba un mecanismo concreto, y tres
de ellas fueron a parar a **código determinista**, no a texto:

1. el LLM no sabe decidir si su expediente necesita otra ronda → lo decide una regla;
2. el LLM no sabe declarar su propia postura de forma parseable → escribe un token;
3. el LLM no respeta la regla de aterrizaje que su prompt enuncia → se comprueba;
4. el LLM anula a un experto con historial sin justificarlo → se le exige y se verifica.

Es la lección de Huang et al. (ICLR 2024) aplicada cuatro veces: donde el juicio
del modelo es verificable, verifícalo; donde no lo es, déjaselo. El resultado no
es "menos agente", es un agente cuyas afirmaciones son auditables.

---

## 7ter. La corrida completa

| componente | baseline T=0 | pizarra v1 | **pizarra v2** |
|---|---|---|---|
| `ranking_score` | 0.6428 | 0.6749 | **0.7125** |
| `mean_case_score` | 0.4913 | 0.5499 | **0.6006** |
| puerta de decisión | 0.6813 | 0.6923 | **0.7473** |
| F1(`yes`) | 0.7943 | 0.8000 | **0.8244** |
| `variable_weight_score` | 0.6516 | **0.8365** | 0.8088 |
| `confidence_score` | **0.7661** | 0.7063 | 0.7500 |
| `important_decisive_factor_score` | 0.5609 | **0.7421** | 0.7264 |
| `section_grounding_score` | **0.9960** | 0.9138 | 0.8887 |
| `tool_score` | 0.6468 | 0.7698 | **0.8664** |

Exactitud por cubo clínico: `bx = None` **1.000** (24 casos) · `bx = Negative`
**0.889** (18) · `bx = Positive` **0.571** (49). El cubo indeterminado sube de
0.469 en la v1 a 0.571, que es de donde sale la mayor parte de la ganancia.

Comportamiento del moderador sobre los 91: **25 casos corrieron una segunda
ronda** (los 25 sin consenso), 85 casos se resolvieron con exactamente **tres**
revelaciones, la guardia de grounding actuó en 85 y el reto al presidente se
disparó en 3.

### Dónde gana y dónde pierde

Gana en lo que domina la nota: la **puerta** (+0.066 sobre el baseline) y el
`tool_score` (+0.220), porque el moderador convierte "abrir todo" en "abrir tres
documentos con una pregunta cada uno".

Pierde, y hay que decirlo, en **`section_grounding_score`** (0.889 frente al
0.996 del baseline). La causa está localizada y es deliberada: pesar `bx` por
encima de `not_used`. En la tarea 1 esa variable se aterriza con
`pathology_report`, que **no existe** en el vocabulario de
`Task1Output.reveal_sequence`, así que es un ungrounded inevitable. Sale a
cuenta —lo que gana en `variable_weight_score` (+0.157) y en
`important_decisive_factor_score` (+0.166) supera de largo lo que cuesta— y con
el juez del reto activo la ventaja se multiplica, porque entonces el grounding
pesa 0.05 frente a 0.25 y 0.15. El baseline saca 0.996 ahí simplemente porque
casi nunca pesa `bx`.

---

## 8. Mapa de ficheros

| fichero | qué contiene |
|---|---|
| `blackboard.py` | la pizarra con rondas: entradas tipadas, render, volcado a disco |
| `moderator.py` | agenda, posturas, consenso y la regla determinista de reapertura |
| `prompts.py` | los prompts de L1/L2/L3 y los dos del moderador |
| `graph.py` | el grafo LangGraph con el bucle de rondas |
| `decide.py` | `reveal_sequence`, parseo del JSON y respaldo determinista |
| `features.py` | bloques A (panel), C (EHR parseado) y B (embeddings) |
| `experts/classifier_expert.py` | el experto de clasificación, con la incertidumbre separada |
| `experts/prf.py` | Probabilistic Random Forest (Reis et al. 2019), numpy puro |
| `experts/uncertainty.py` | la sigma de cada variable, declarada y justificada |
| `experts/protocol.py` | criterio EAU por cubo clínico |
| `experts/image_predictor.py` | `FeatureStore` + `run_predictor` |
| `ablation/run_ablation.py` | 15 familias × 6 conjuntos, 5×5 CV |
| `ablation/stability.py` | los finalistas sobre 10 semillas |
| `analysis/montecarlo.py` | comparación pareada contra el baseline |
| `analysis/scoring.py` | envoltura del evaluador oficial (juez apagado) |
| `runs/launch.sh` | lanza una corrida en tmux |

---

## 9. Bibliografía

**Arquitectura de pizarra**
- Erman, Hayes-Roth, Lesser, Reddy (1980). *The Hearsay-II Speech-Understanding System: Integrating Knowledge to Resolve Uncertainty.* ACM Computing Surveys 12(2).
- Hayes-Roth (1985). *A blackboard architecture for control.* Artificial Intelligence 26(3).
- Nii (1986). *Blackboard Systems.* AI Magazine 7(2).

**Colaboración entre LLM**
- Du, Li, Torralba, Tenenbaum, Mordatch (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* arXiv:2305.14325.
- Liang et al. (2023). *Encouraging Divergent Thinking in LLMs through Multi-Agent Debate.* arXiv:2305.19118.
- Chen, Saha, Bansal (2023). *ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs.* arXiv:2309.13007.
- Wu et al. (2023). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation.* arXiv:2308.08155.
- Hong et al. (2023). *MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework.* arXiv:2308.00352.
- Tang et al. (2023). *MedAgents: LLMs as Collaborators for Zero-shot Medical Reasoning.* arXiv:2311.10537.
- Kim et al. (2024). *MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making.* NeurIPS 2024.
- Wang et al. (2024). *Rethinking the Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key?* ACL 2024.

**Límites de la auto-corrección**
- Huang et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR 2024.
- Turpin, Michael, Perez, Bowman (2023). *Language Models Don't Always Say What They Think.* NeurIPS 2023.
- Yao et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023.

**Clasificación e incertidumbre**
- Breiman (2001). *Random Forests.* Machine Learning 45(1).
- Geurts, Ernst, Wehenkel (2006). *Extremely randomized trees.* Machine Learning 63(1).
- Reis, Baron, Shahaf (2019). *Probabilistic Random Forest: A Machine Learning Algorithm for Noisy Data Sets.* The Astronomical Journal 157(1):16.
- Lakshminarayanan, Pritzel, Blundell (2017). *Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.* NeurIPS 2017.
- Depeweg, Hernández-Lobato, Doshi-Velez, Udluft (2018). *Decomposition of Uncertainty in Bayesian Deep Learning.* ICML 2018.
- Guo, Pleiss, Sun, Weinberger (2017). *On Calibration of Modern Neural Networks.* ICML 2017.
- Niculescu-Mizil, Caruana (2005). *Predicting Good Probabilities With Supervised Learning.* ICML 2005.
- Angelopoulos, Bates (2021). *A Gentle Introduction to Conformal Prediction.* arXiv:2107.07511.
- Peduzzi et al. (1996). *A simulation study of the number of events per variable in logistic regression analysis.* J Clin Epidemiol 49(12).

**Recuperación**
- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020.

> Las referencias se dan por autor, año, título y sede. Si van a un artículo,
> conviene verificar páginas y DOI en la fuente original.
