#!/usr/bin/env bash
# Ejecuta un comando dentro de la imagen de inferencia (vLLM 0.25.0, la pila del reto),
# con el repositorio montado en la misma ruta y como tu usuario (los ficheros que se
# generan quedan a tu nombre).
#
#   lora_kit/pipeline/in_container.sh python3 lora_kit/pipeline/check_template.py --model model/gemma-4-E2B-it --sft runs/sft.jsonl
#   lora_kit/pipeline/in_container.sh lora_kit/pipeline/eval_fold.sh ...
#
# IMAGE (opcional): nombre de la imagen; por defecto chimera-lora-infer (ver GUIA_DESDE_CERO.md, paso 6).
set -euo pipefail
IMAGE=${IMAGE:-chimera-lora-infer}
exec docker run --rm --gpus all --ipc=host \
    --user "$(id -u):$(id -g)" -e HOME=/tmp -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
    -v "$PWD:$PWD" -w "$PWD" \
    --entrypoint bash "$IMAGE" -c "$(printf '%q ' "$@")"
