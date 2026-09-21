#!/usr/bin/env bash
# Construye la imagen de la V2 (perfil de memoria de PLAN §13.1).
#
# Ni la V1 ni la V1.1 se tocan: sus Dockerfiles, imágenes y tags siguen donde
# estaban, así que volver atrás es reenviar la imagen anterior y nada más.
set -euo pipefail

DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TAG="${DOCKER_IMAGE_TAG:-chimera_agent_baseline_final}"
# Qué carpeta entra como `version_final_reto` (ver ESTRUCTURA.md):
#   DOCKER_IMAGE_TAG=chimera_agent_baseline_v4 ./do_build_final.sh
CODE_DIR="${CODE_DIR:-version_final_reto_send_v4}"
cd "$DIR"
[[ -d "$CODE_DIR" && ! -L "$CODE_DIR" ]] || { echo "CODE_DIR=$CODE_DIR no es una carpeta real"; exit 1; }

echo "== Construyendo $TAG desde Dockerfile_final con $CODE_DIR =="
docker build \
  --platform=linux/amd64 \
  --file Dockerfile_final \
  --build-arg "CODE_DIR=$CODE_DIR" \
  --tag "$TAG" \
  ${DOCKER_QUIET_BUILD:+--quiet} \
  "$DIR" 2>&1

echo
echo "== Compuerta E11: la imagen tal cual, SIN montar código =="
echo "   Montar el árbol sobre otra imagen comprueba el código, no la entrega."
echo
echo "     python3 version_final_reto/verification/gc_profile.py \\"
echo "         --cpuset 0-3 --interfaces 0,1,2 --image $TAG --no-mount --tag v2_e11"
