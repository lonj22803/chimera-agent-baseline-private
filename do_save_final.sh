#!/usr/bin/env bash
# Empaqueta la imagen de entrega V2 y, si hace falta, el tarball del modelo.
#
# Ni la V1 ni la V1.1 se tocan: sus imágenes y sus tarballs siguen donde estaban,
# así que volver atrás es reenviar el anterior y nada más.
#
# El nombre lleva la fecha del build, no la de ejecución: identifica la imagen, no el
# momento en que se comprimió. El modelo NO se re-empaqueta si ya existe y no ha
# cambiado — son 10 GB y comprimirlos de nuevo sin motivo sólo gasta tiempo y arriesga
# dejar un tarball a medias.
set -euo pipefail

DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TAG="${DOCKER_IMAGE_TAG:-chimera_agent_baseline_final}"
cd "$DIR"

docker image inspect "$TAG" >/dev/null 2>&1 || { echo "No existe la imagen $TAG. Constrúyela primero con ./do_build_final.sh"; exit 1; }

# Guarda de disco: este repo se quedó a 549 MB libres empaquetando la V2 y un
# `docker save` sin sitio deja un .tar.gz truncado que parece válido hasta que
# Grand Challenge lo rechaza. 12 GiB cubren los ~10 que ocupa comprimido.
libre_mib=$(df -Pm "$DIR" | awk 'NR==2 {print $4}')
if (( libre_mib < 12288 )); then
    echo "Sólo hay ${libre_mib} MiB libres y el tarball ronda los 10 GiB."
    echo "Libera espacio antes de empaquetar. Lo más indoloro:"
    echo "    docker builder prune -a -f      # caché regenerable, no borra imágenes"
    exit 1
fi

fecha=$(docker inspect --format='{{ .Created }}' "$TAG" | sed -E 's/(.*)T(.*)\..*Z?/\1_\2/' | sed 's/[-,:]/-/g')
salida="${TAG}_${fecha}.tar.gz"

echo "== Imagen =="
echo "   tag    : $TAG"
echo "   id     : $(docker images "$TAG" --format '{{.ID}}')"
echo "   tamaño : $(docker images "$TAG" --format '{{.Size}}')"
echo "   destino: $salida"
echo "   libre  : $((libre_mib / 1024)) GiB"
echo "   comprimiendo, esto tarda varios minutos..."
docker save "$TAG" | gzip -c > "$DIR/$salida"
echo "   hecho: $(du -h "$DIR/$salida" | cut -f1)"

echo
echo "== Modelo =="
if [[ -f "$DIR/model.tar.gz" ]]; then
    mas_nuevo=$(find "$DIR/model" -newer "$DIR/model.tar.gz" -type f -print -quit 2>/dev/null || true)
    if [[ -z "$mas_nuevo" ]]; then
        echo "   model.tar.gz está al día ($(du -h "$DIR/model.tar.gz" | cut -f1)); no se re-empaqueta."
        echo "   Los pesos no han cambiado desde que se creó, y la V2 usa los mismos."
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
echo "   1. $salida   -> Algorithm (Container Image)"
echo "   2. model.tar.gz -> Model, aparte; GC lo extrae en /opt/ml/model."
echo "      La V2 usa los MISMOS pesos que la V1.1: si ya está subido, se reutiliza."
echo
echo "   Ver version_final_reto/runtime_16gb/ENTREGA_CHECKLIST.md antes de enviar."
