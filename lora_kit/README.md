# lora_kit — lo que hay que llevarse al repositorio limpio

Copia **esta carpeta entera** a la raíz del repositorio limpio (por ejemplo, como
`lora_kit/`). No hace falta nada más de este repositorio.

```
lora_kit/
  PLAN_FINETUNING_LORA.md      el plan paso a paso (empieza por aquí)
  contract/                    lo que el modelo ve, copiado literal del agente
    verbatim/                  prompts.py, agent_prompt.j2, form_fill.py, schema.py,
                               definitions.py, base.py, mcp_server.py, case_loader.py,
                               vllm_offline.py — sin editar
    tool_schemas/              tools_task{1,2,3}.json: la lista de herramientas exacta
                               (nombre, descripción, parámetros, orden) que el agente
                               pasa a llm.chat(tools=...). Volcada del servidor MCP real
    render_example.py          renderiza los prompts de un caso con las copias literales
    example_task1/             salida de render_example.py sobre un caso de T1
  agent_baseline/              el agente baseline listo para evaluar el modelo entrenado
    src/ templates/ configs/ resources/guidelines_db/ tests/ docs/
    inference.py               entrypoint de GC (USE_MERGED_SOLUTION=False: agente puro)
    Dockerfile                 imagen del reto sin la solución de expertos
    requirements.txt pyproject.toml Makefile
    dev/score_local.py         puntuación con el evaluador oficial (juez apagado)
    dev/make_split.py          particiones estratificadas
    dev/baseline_reference.json  números del baseline sin entrenar (B0)
```

## Lo que NO está aquí y hay que traer aparte

| Qué | De dónde | Para qué |
|---|---|---|
| Pesos de `google/gemma-4-E2B-it` | Hugging Face (aceptar licencia) → `agent_baseline/model/gemma-4-E2B-it/` | Base del LoRA; su `tokenizer`/`chat_template` son parte del contrato |
| `google/embeddinggemma-300m` | Hugging Face → `agent_baseline/model/embedding_model/` | Solo si se mantiene `search_guidelines` |
| Evaluador oficial | `git clone https://github.com/DIAGNijmegen/CHIMERA-agent` (fijar commit) | `evaluation/evaluate.py`; `score_local.py` lo busca con `--eval-repo` |
| Datos de entrada y ground truth | tu repositorio limpio | `data/task<N>/agent_input/…` y `data/task<N>/ground_truth/…` |

## Uso rápido

```bash
# ver exactamente lo que verá el modelo en un caso
python lora_kit/contract/render_example.py data/task1/agent_input/<case> /tmp/prompts_case

# evaluar un modelo (base o fusionado) con el agente sin tocar
cd lora_kit/agent_baseline
python -m chimera_agent_baseline.run paths.data_root=../../data \
    paths.model_dir=<carpeta_modelo> "agent.pids=[...]"
python dev/score_local.py --eval-repo <ruta CHIMERA-agent>
```
