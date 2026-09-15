#!/usr/bin/env bash
# Deja las dependencias de una imagen reconstruida exactamente como las de la original.
#
#   ./do_fijar_dependencias.sh TAG pip_freeze_registrado.txt
#
# Por qué hace falta: `requirements.txt` está fijado entero, pero vLLM resuelve sus
# propias dependencias el día que se construye. La v2 enviada (12-sep) y la v3
# (15-sep) difieren en 10 versiones menores (anthropic, openai, grpcio, httpx2,
# uvicorn...). Si la caché de Docker ya no guarda las capas de pip de aquel día,
# reconstruir trae las de hoy.
#
# Si el `pip freeze` de la imagen coincide con el registrado, no hace nada. Si sólo
# cambian versiones, añade UNA capa encima que instala las registradas con
# `--no-deps` y vuelve a comprobar. Si falta o sobra algún paquete, se detiene:
# eso ya no es una deriva de versiones y hay que mirarlo.
set -euo pipefail
# El contenedor y el host ordenan distinto con locales distintos, y `comm` exige
# el mismo orden en las dos entradas.
export LC_ALL=C

TAG=$1
FREEZE=$2
[[ -f "$FREEZE" ]] || { echo "No existe $FREEZE"; exit 1; }

freeze() { docker run --rm --network none --entrypoint bash "$TAG" -c 'python3 -m pip freeze 2>/dev/null' | sort; }
nombres() { sed -E 's/[ =@<>!~].*//' | tr 'A-Z_' 'a-z-' | sort -u; }

actual=$(freeze)
registrado=$(sort "$FREEZE")
if [[ "$actual" == "$registrado" ]]; then
    echo "   dependencias idénticas a $FREEZE"
    exit 0
fi

faltan=$(comm -13 <(echo "$actual" | nombres) <(echo "$registrado" | nombres))
sobran=$(comm -23 <(echo "$actual" | nombres) <(echo "$registrado" | nombres))
if [[ -n "$faltan$sobran" ]]; then
    echo "No es sólo una deriva de versiones."
    [[ -n "$faltan" ]] && echo "  faltan: $faltan"
    [[ -n "$sobran" ]] && echo "  sobran: $sobran"
    exit 1
fi

pins=$(comm -13 <(echo "$actual") <(echo "$registrado") | tr '\n' ' ')
echo "== Fijando en $TAG: $pins"
docker build --platform=linux/amd64 --tag "$TAG" - <<EOF
FROM $TAG
USER root
RUN python3 -m pip install --no-cache-dir --no-deps $pins
USER user
EOF

if [[ "$(freeze)" == "$registrado" ]]; then
    echo "   dependencias idénticas a $FREEZE"
else
    echo "Tras fijar, el pip freeze sigue sin coincidir:"
    diff <(freeze) <(echo "$registrado") || true
    exit 1
fi
