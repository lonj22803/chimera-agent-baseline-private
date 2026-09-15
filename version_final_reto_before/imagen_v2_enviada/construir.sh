#!/usr/bin/env bash
# Reconstruye la imagen enviada a la fase Test (12-sep-2026):
#     chimera_agent_baseline_v2_2026-09-12_21-45-57.tar.gz
#
# `contexto/` es el /opt/app de esa imagen, extraído de ella el 15-sep-2026 y
# comprobado fichero a fichero contra `huella_opt_app.sha256`. No depende del
# resto del repositorio: el paquete que lleva (`delete_final_versions_task_V1_1`
# + `delete_final_versions_task_V2`) ya no existe en main, y los .joblib de los
# expertos no están en git.
#
# `Dockerfile_V2` es el de la rama `pre-limpieza`, sin tocar.
#
#   ./construir.sh            construye la imagen chimera_agent_baseline_v2
#   ./construir.sh --save     y además escribe el tarball con su nombre original
set -euo pipefail

KIT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
REPO=$(cd -- "$KIT/../.." && pwd)
TAG="${DOCKER_IMAGE_TAG:-chimera_agent_baseline_v2}"
NOMBRE="${TARBALL_NAME:-chimera_agent_baseline_v2_2026-09-12_21-45-57.tar.gz}"

echo "== Construyendo $TAG desde $KIT/Dockerfile_V2 =="
docker build --platform=linux/amd64 --file "$KIT/Dockerfile_V2" --tag "$TAG" \
    ${DOCKER_QUIET_BUILD:+--quiet} "$KIT/contexto"

echo "== Comprobando /opt/app contra la huella de la imagen enviada =="
docker run --rm --network none --entrypoint bash "$TAG" -c '
  cd /opt/app
  find . -path ./model -prune -o -type f ! -path "*/__pycache__/*" -print0 | sort -z | xargs -0 sha256sum
' | diff - "$KIT/huella_opt_app.sha256" && echo "   /opt/app idéntico"

echo "== Dependencias frente a las de la imagen enviada =="
# vLLM resuelve sus dependencias el día que se construye; esto las devuelve a las
# del 12-sep si la caché ya no las tiene (ver el propio script).
"$REPO/do_fijar_dependencias.sh" "$TAG" "$KIT/pip_freeze_imagen_v2.txt"

if [[ "${1:-}" == "--save" ]]; then
    libre_mib=$(df -Pm "$REPO" | awk 'NR==2 {print $4}')
    (( libre_mib >= 12288 )) || { echo "Sólo hay ${libre_mib} MiB libres; hacen falta ~12 GiB."; exit 1; }
    echo "== Empaquetando $REPO/$NOMBRE =="
    docker save "$TAG" | gzip -c > "$REPO/$NOMBRE"
    echo "   hecho: $(du -h "$REPO/$NOMBRE" | cut -f1)"
    echo "   Se sube junto a model.tar.gz, que no cambia."
fi
