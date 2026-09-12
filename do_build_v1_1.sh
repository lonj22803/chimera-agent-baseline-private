#!/usr/bin/env bash
# Construye y empaqueta la imagen de entrega V1.1.
#
# La V1 no se toca: su Dockerfile, su imagen y su tag siguen donde estaban, así que
# volver atrás es reenviar la imagen anterior y nada más.
set -euo pipefail

DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TAG="${DOCKER_IMAGE_TAG:-chimera_agent_baseline_v1_1}"
cd "$DIR"

echo "== Construyendo $TAG desde Dockerfile_V1_1 =="
docker build \
  --platform=linux/amd64 \
  --file Dockerfile_V1_1 \
  --tag "$TAG" \
  ${DOCKER_QUIET_BUILD:+--quiet} \
  "$DIR" 2>&1

echo
echo "== Comprobación antes de empaquetar =="
echo "   Un caso por interfaz, 4 núcleos y un case_id que la caché de expertos no"
echo "   conoce, que es la única ruta que existe en el test real:"
echo
echo "     python3 delete_final_versions_task_V1_1/verification/gc_profile.py \\"
echo "         --cpuset 0-3 --interfaces 0,1,2 --image $TAG \\"
echo "         --package delete_final_versions_task_V1_1 --tag entrega"
echo
echo "   Y el empaquetado, cuando el perfilador dé exit 0 y dos ficheros por interfaz:"
echo
echo "     DOCKER_IMAGE_TAG=$TAG ./do_save_v1.sh"
echo
echo "   Instancia en Grand Challenge: A10G de 24 GiB. En una T4 de 16 GiB no entran"
echo "   9,9 GiB de pesos más el KV de 32 k de contexto y todos los casos caen al respaldo."
