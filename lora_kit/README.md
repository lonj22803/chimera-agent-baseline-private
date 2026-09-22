# lora_kit — fine-tuning LoRA del agente CHIMERA para las tres tareas

Copia **esta carpeta entera** a la raíz del repositorio limpio. Todo lo necesario para
entrenar y evaluar está dentro; no hace falta nada más de este repositorio.

**Empieza por** [`PLAN_FINETUNING_LORA.md`](PLAN_FINETUNING_LORA.md) (§3.1 tiene la
secuencia de comandos) y por la ficha de cada tarea en `tasks/`.

```
lora_kit/
  PLAN_FINETUNING_LORA.md      el plan paso a paso
  requirements-train.txt       entorno de entrenamiento (versiones probadas)
  tasks/
    task1/  README.md          biopsia sí/no: datos, herramientas, salida, qué se aprende, riesgos
            sft_react.txt      ejemplo real de lo que el modelo aprende en el bucle de herramientas
            sft_form_fill.txt  ejemplo real de lo que aprende en el formulario final
    task2/  (igual)            tratamiento, 4 clases
    task3/  (igual)            meses hasta la recurrencia + evento
  fixture_data/                un caso real por tarea con la estructura de data/
                               (el "ground_truth" de estos ejemplos es una salida de un
                               agente, no la etiqueta real: solo sirve de formato)
  contract/
    verbatim/                  copias literales del agente: prompts.py, agent_prompt.j2,
                               form_fill.py, schema.py, definitions.py, base.py,
                               mcp_server.py, case_loader.py, vllm_offline.py
    tool_schemas/              tools_task{1,2,3}.json: la lista tools= exacta que ve el modelo,
                               volcada del servidor MCP real
  pipeline/
    contract.py                carga el contrato literal
    make_folds.py              pliegues estratificados (3 tareas, agrupados por paciente)
    build_sft.py               datos de entrenamiento de las 3 tareas (react + form_fill)
    render.py                  plantilla de chat del modelo + máscara de pérdida
    check_template.py          compara token a token con vLLM (entorno de inferencia, GPU)
    train_lora.py              entrena el LoRA (un pliegue o todo); pensado para 24 GB
    merge_export.py            fusiona, comprueba la paridad y exporta para vLLM
    eval_fold.sh               agente sin tocar + evaluador oficial en el pliegue de test
    score_fold.py  report.py   puntuación y tabla final (IC bootstrap pareado, McNemar)
    dump_examples.py           vuelca ejemplos SFT legibles
    selftest.sh                prueba de humo sin GPU sobre fixture_data/
    tests/                     tokenizador y modelo de juguete para selftest.sh
  agent_baseline/              el agente del reto para evaluar el modelo entrenado
    src/ templates/ configs/ resources/guidelines_db/ tests/ docs/
    inference.py               entrypoint de GC (USE_MERGED_SOLUTION=False: agente puro)
    Dockerfile                 imagen del reto sin la solución de expertos
    dev/score_local.py         evaluador oficial en local (lo usan score_fold.py y report.py)
    dev/baseline_reference.json  números del baseline sin entrenar (brazo B0 de referencia)
```

## Lo que NO está aquí y hay que traer aparte

| Qué | De dónde | Para qué |
|---|---|---|
| Pesos de `google/gemma-4-E2B-it` | Hugging Face (aceptar la licencia) → `model/gemma-4-E2B-it/` | Base del LoRA; su tokenizador y su plantilla de chat forman parte del contrato |
| `google/embeddinggemma-300m` | Hugging Face → `agent_baseline/model/embedding_model/` | Solo si se mantiene `search_guidelines` |
| Evaluador oficial | `git clone https://github.com/DIAGNijmegen/CHIMERA-agent` (probado con el commit `92365b9`) | `evaluation/evaluate.py` |
| Datos y ground truth | tu repositorio limpio | `data/task<N>/agent_input/…` y `data/task<N>/ground_truth/…` |

## Qué está probado y qué no

- **Probado aquí, sin GPU** (`pipeline/selftest.sh`): datos de las 3 tareas, pliegues,
  máscara de pérdida, entrenamiento LoRA, fusión con paridad y puntuación con el
  evaluador oficial. Se usan un modelo diminuto aleatorio y un tokenizador de juguete.
  El cálculo de la pérdida coincide exactamente con el de Hugging Face.
- **Por probar en la máquina con GPU**, y es lo primero que hay que hacer:
  - `check_template.py` con Gemma 4 y vLLM 0.25.0, para comprobar que el prompt
    coincide token a token y que el parser `gemma4` lee las llamadas;
  - los nombres reales de las capas de Gemma 4 para `--target-regex` (si no casan, el
    script lista los módulos y para);
  - que el forward de Gemma 4 acepte `logits_to_keep` (si no, `--no-logits-to-keep`,
    que usa más memoria).
