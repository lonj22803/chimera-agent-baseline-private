# Arquitectura V1

Secuencia canónica: `INTAKE → expertos deterministas → GUÍA → MODERATOR → REGISTRAR → FUSION → PANEL-PROTOCOL → VERIFIER → CHAIR`.

| Tramo | T1 | T2 | T3 |
|---|---|---|---|
| Entrada y expertos | panel, cohorte, experiencia, traza | grado, patología pendiente, cascada, traza; experiencia candidata | CAPRA-S, cirugía, digital; experiencia candidata |
| Guía | EAU vía MCP | EAU vía MCP | inventario determinista candidato; RAG optativo |
| Moderación y registro | LLM; documentos del plan real | LLM; lectura obligatoria del plan | preguntas y lectura deterministas |
| Fusión y protocolo | voto ponderado, experiencia con peso 0 | portavoz calibrado; réplicas sin votos extra | CAPRA-S por defecto; portavoz seleccionado por validación anidada bajo bandera |
| Verificación | bucles acotados y procedencia | bucles acotados y reto de citas | guardias de grado, cifras y ganglios; dos intentos |
| Presidente | nota y formulario, corregidos por código | nota; formulario fijado por protocolo | sólo prosa; horizonte fijado por código |

`common/prompt_kit.py` aporta frontera de confianza, regla de cita, retos, marcos, ejemplos y lista negra (`common/vocab.py`). `common/sampling.py` configura presupuestos por papel. Los documentos y precedentes son datos no confiables.

T3 conserva su grafo secuencial: no tiene ramas de ToolNode ni reveal_sequence. Con `CHIMERA_T3_ADVICE=enhanced` añade dos intervenciones, de 11 a 13. La experiencia no se pasa a `Panel.horizon`: sus meses y eventos históricos nunca son un estimador de supervivencia.

Las variantes de prompts se activan con `CHIMERA_T2_PROMPT=enhanced` y `CHIMERA_T3_PROMPT=enhanced`. El valor por defecto sigue siendo `baseline` hasta superar dos pases pareados del juez. `CHIMERA_T2_FORM=experience` permite medir el formulario candidato, que se ha descartado por empeorar en DEV LOO. `CHIMERA_T3_SPOKESPERSON=selected` ejecuta el selector anidado ya medido; `CHIMERA_T3_HORIZON=105` es la calibración monótona alternativa sólo para CAPRA-S. No se combinan sus métricas: cambian el orden de riesgo y el mapa temporal de maneras distintas.

## Correcciones a supuestos del plan

- `features_grading.py` representa estratificación clínica previa al tratamiento. No define un grupo EAU/NCCN posoperatorio validado. T3 declara su grupo clínico como desconocido cuando falta cT, y registra los hallazgos quirúrgicos por separado. Véanse [clasificación EAU](https://uroweb.org/guidelines/prostate-cancer/chapter/classification-and-staging-systems) y [seguimiento EAU](https://uroweb.org/guidelines/prostate-cancer/chapter/followup), consultados el 11-09-2026.
- T3 carece de notas de referencia. Sus ejemplos nuevos están etiquetados como sintéticos y sirven sólo de estilo; no se inventa un ground truth.
- `TASK3_TOOLS` es el registro de documentos. `search_guidelines` lo registra el servidor MCP como herramienta compartida. La ruta reutiliza `--tool-registry task3`.
- Dos alias y dos ficheros exactos son requisitos incompatibles sin elegir slug. El smoke usa grafía canónica provisional; la confirmación remota sigue pendiente.
- Los splits tienen exposición histórica. Una validación interna nueva reduce sesgo de selección; no convierte estos casos en una cohorte externa nunca vista.

## Integridad de la inferencia

T1 excluye el propio ID al recuperar experiencia. T2 y T3 congelan las memorias nuevas sólo con casos DEV; no leen ground truth del paciente consultado. La selección de portavoz T3 ajusta imputación, proyección, hiperparámetros y familia dentro de cada fold externo. Las predicciones OOF se usan sólo en modo `oof`; `deployed` calcula desde las entradas.

La generación vLLM y el juez Ollama se serializan. Los errores de contrato no se presentan como éxitos del modelo. El control de cobertura y el de calidad son evidencias diferentes.
