#!/usr/bin/env bash
# Empaqueta la imagen de entrega V1 y, si hace falta, el tarball del modelo.
#
# El nombre lleva la fecha del build, no la de ejecución: identifica la imagen, no el
# momento en que se comprimió. El modelo NO se re-empaqueta si ya existe y no ha
# cambiado — son 10 GB y comprimirlos de nuevo sin motivo sólo gasta tiempo y arriesga
# dejar un tarball a medias.
set -euo pipefail

DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TAG="${DOCKER_IMAGE_TAG:-chimera_agent_baseline_v1}"
cd "$DIR"

docker image inspect "$TAG" >/dev/null 2>&1 || { echo "No existe la imagen $TAG. Constrúyela primero."; exit 1; }

fecha=$(docker inspect --format='{{ .Created }}' "$TAG" | sed -E 's/(.*)T(.*)\..*Z?/\1_\2/' | sed 's/[-,:]/-/g')
salida="${TAG}_${fecha}.tar.gz"

echo "== Imagen =="
echo "   tag    : $TAG"
echo "   id     : $(docker images "$TAG" --format '{{.ID}}')"
echo "   tamaño : $(docker images "$TAG" --format '{{.Size}}')"
echo "   destino: $salida"
echo "   comprimiendo, esto tarda varios minutos..."
docker save "$TAG" | gzip -c > "$DIR/$salida"
echo "   hecho: $(du -h "$DIR/$salida" | cut -f1)"

echo
echo "== Modelo =="
if [[ -f "$DIR/model.tar.gz" ]]; then
    mas_nuevo=$(find "$DIR/model" -newer "$DIR/model.tar.gz" -type f -print -quit 2>/dev/null || true)
    if [[ -z "$mas_nuevo" ]]; then
        echo "   model.tar.gz está al día ($(du -h "$DIR/model.tar.gz" | cut -f1)); no se re-empaqueta."
        echo "   Los pesos no han cambiado desde que se creó."
    else
        echo "   model/ cambió después del tarball; re-empaquetando..."
        tar -czf "$DIR/model.tar.gz" -C "$DIR/model" .
        echo "   hecho: $(du -h "$DIR/model.tar.gz" | cut -f1)"
    fi
else
    echo "   no existe model.tar.gz; creándolo..."
    tar -czf "$DIR/model.tar.gz" -C "$DIR/model" .
    echo "   hecho: $(du -h "$DIR/model.tar.gz" | cut -f1)"
fi

echo
echo "== Para subir a Grand Challenge =="
echo "   1. $salida        -> Algorithm (Container Image)"
echo "   2. model.tar.gz   -> Model, aparte; GC lo extrae en /opt/ml/model"
echo "   Instancia: A10G, <=32 GB RAM, las tres interfaces."
echo "   Ver delete_final_versions_task_V1/ENTREGA_CHECKLIST.md antes de enviar."
