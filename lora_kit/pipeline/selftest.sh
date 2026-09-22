#!/usr/bin/env bash
# Prueba de humo de toda la pipeline SIN GPU y sin Gemma, sobre fixture_data/ (un caso por tarea).
# Construye datos -> pliegues -> máscara de pérdida -> entrena un LoRA sobre un modelo
# diminuto aleatorio -> fusiona -> comprueba paridad. Si pasas la ruta del evaluador
# oficial, también puntúa (usando el propio GT como predicción: debe dar 1.0).
#
#   pipeline/selftest.sh [ruta/CHIMERA-agent]
set -euo pipefail
KIT=$(cd "$(dirname "$0")/.." && pwd)
W=$(mktemp -d)
cd "$KIT"
echo "== trabajo en $W"
python3 pipeline/make_folds.py --data-root fixture_data --out "$W/folds.json" --k 5 > /dev/null
python3 pipeline/build_sft.py --data-root fixture_data --out "$W/sft.jsonl" --folds "$W/folds.json" --permute-tools 1 > /dev/null
python3 -c "import json,sys; r=[json.loads(l) for l in open(sys.argv[1])]; t={(x['task'],x['kind']) for x in r}; assert t=={(a,b) for a in (1,2,3) for b in ('react','form_fill')}, t; print('== sft:', len(r), 'ejemplos, 3 tareas x 2 tipos')" "$W/sft.jsonl"
python3 pipeline/tests/toy_tokenizer.py "$W/sft.jsonl" "$W/tok" 2>/dev/null
python3 pipeline/tests/toy_model.py "$W/tok" "$W/model" 2>/dev/null
python3 - "$W" <<'PY'
import json, sys
sys.path.insert(0, "pipeline")
from transformers import AutoTokenizer
from render import encode_example
w = sys.argv[1]
tok = AutoTokenizer.from_pretrained(f"{w}/model")
for line in open(f"{w}/sft.jsonl"):
    r = json.loads(line)
    e = encode_example(tok, r)
    n_asst = sum(m["role"] == "assistant" for m in r["messages"])
    assert len(e["spans"]) == n_asst, (r["case_id"], r["kind"])
    for a, b in e["spans"]:
        assert tok.decode(e["input_ids"][b - 1:b], skip_special_tokens=False) == "<end_of_turn>"
print("== máscara: cada turno de asistente tiene su tramo y acaba en fin de turno")
PY
python3 pipeline/train_lora.py --model "$W/model" --sft "$W/sft.jsonl" --fold -1 --epochs 1 --grad-accum 2 \
    --out "$W/run" --target-regex '.*\.(q_proj|v_proj)$' --rank 4 --alpha 8 --max-len 8192 2>&1 | grep -E "epoch|LoRA"
python3 pipeline/merge_export.py --base "$W/model" --adapter "$W/run/adapter_epoch1" --out "$W/merged" \
    --check-sft "$W/sft.jsonl" 2>&1 | grep -E "paridad|exportado"
if [ $# -ge 1 ]; then
    for t in 1 2 3; do mkdir -p "$W/pred/task$t"; cp -r fixture_data/task$t/ground_truth/* "$W/pred/task$t/"; done
    python3 -c "import json;json.dump({'test':['PT-pseudo_0bd72f429a8b','T2-001','T3-001']},open('$W/split.json','w'))"
    python3 pipeline/score_fold.py --data-root fixture_data --output-root "$W/pred" --split "$W/split.json" \
        --eval-repo "$1" --out "$W/score.json" | tail -3
fi
echo "== OK"
