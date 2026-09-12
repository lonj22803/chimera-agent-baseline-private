"""El ciclo de la fase 6, para que probar una idea sea un comando y no un ritual.

El protocolo es siempre el mismo y no admite atajos:

    explorar en DEV  ->  confirmar en VAL una vez  ->  correr entero  ->  BITACORA

Un candidato que sube en DEV y no reproduce en VAL se descarta; no se reajusta
contra VAL, porque entonces VAL deja de confirmar nada. Los splits son los fijos
de `dev/splits/`, no se resortean.

Cuatro motivos de rechazo automático, tomados del criterio 6.4 del plan:

- No reproduce en VAL.
- Sube sólo con el juez apagado y depende del anclaje a secciones.
- Sube sólo comparando contra un pase del juez de otra carga.
- Necesita leer una etiqueta en inferencia, o `exclude_self=False`.
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path

V1 = Path(__file__).resolve().parents[1]
REPO = V1.parent
SPLITS = REPO/'dev/splits'
RESULTS = V1/'experiments/results'

RECHAZOS = {
    'val': 'No reproduce en VAL',
    'grounding': 'Depende del anclaje a secciones con el juez apagado',
    'juez_no_pareado': 'Comparado contra un pase del juez de otra carga',
    'fuga': 'Lee etiquetas en inferencia o usa exclude_self=False',
}


def split_ids(task, split):
    path = SPLITS/f'task{task}_{split}.txt'
    if not path.exists():
        raise FileNotFoundError(f'No existe el split fijo {path}')
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def decidir(dev_baseline, dev_candidato, val_baseline=None, val_candidato=None, mayor_es_mejor=True):
    """La decisión de adopción, explícita y sin margen para el optimismo."""
    def mejora(b, c):
        return (c > b) if mayor_es_mejor else (c < b)
    if not mejora(dev_baseline, dev_candidato):
        return {'adoptado': False, 'motivo': 'No mejora en DEV; VAL no se lee',
                'dev': {'baseline': dev_baseline, 'candidato': dev_candidato}, 'val_leido': False}
    if val_baseline is None or val_candidato is None:
        return {'adoptado': False, 'motivo': 'Elegible en DEV; falta confirmar en VAL',
                'elegible': True, 'dev': {'baseline': dev_baseline, 'candidato': dev_candidato},
                'val_leido': False}
    reproduce = mejora(val_baseline, val_candidato)
    return {'adoptado': bool(reproduce), 'motivo': None if reproduce else RECHAZOS['val'],
            'elegible': True, 'val_leido': True,
            'dev': {'baseline': dev_baseline, 'candidato': dev_candidato},
            'val': {'baseline': val_baseline, 'candidato': val_candidato}}


def resumen_resultados(results=RESULTS):
    """Lo que ya está medido, con su veredicto tal como lo dejó cada experimento."""
    filas = []
    for path in sorted(Path(results).glob('*.json')):
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        filas.append({'experimento': path.stem,
                      'adoptado': data.get('adopted', data.get('adoptado')),
                      'elegible': data.get('eligible', data.get('eligible_for_adoption')),
                      'motivo': data.get('reason') or data.get('caveat') or data.get('warning'),
                      'archivo': str(path.relative_to(V1))})
    return filas


def anotar(entrada, bitacora=V1/'BITACORA.md'):
    """Añade la entrada al final de la bitácora. Nunca reescribe lo ya registrado."""
    texto = json.dumps(entrada, indent=2, ensure_ascii=False) if isinstance(entrada, dict) else str(entrada)
    with open(bitacora, 'a') as stream:
        stream.write(f'\n## Entrada {date.today().isoformat()}\n\n```json\n{texto}\n```\n')
    return str(bitacora)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='accion', required=True)
    s = sub.add_parser('resumen', help='veredicto de cada experimento ya medido')
    s.set_defaults(fn=lambda a: resumen_resultados())
    d = sub.add_parser('decidir', help='aplicar el criterio de adopción a unas cifras')
    for flag in ('--dev-baseline', '--dev-candidato'):
        d.add_argument(flag, type=float, required=True)
    for flag in ('--val-baseline', '--val-candidato'):
        d.add_argument(flag, type=float)
    d.add_argument('--menor-es-mejor', action='store_true')
    d.set_defaults(fn=lambda a: decidir(a.dev_baseline, a.dev_candidato, a.val_baseline,
                                        a.val_candidato, not a.menor_es_mejor))
    sp = sub.add_parser('split', help='los identificadores de un split fijo')
    sp.add_argument('--task', type=int, required=True, choices=[1, 2, 3])
    sp.add_argument('--split', required=True, choices=['dev', 'val'])
    sp.set_defaults(fn=lambda a: split_ids(a.task, a.split))
    args = p.parse_args()
    print(json.dumps(args.fn(args), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
