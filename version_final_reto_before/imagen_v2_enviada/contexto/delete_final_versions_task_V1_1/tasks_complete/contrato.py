"""La compuerta que hay que pasar antes de empaquetar.

Reúne en un solo comando todo lo que la fase 1 exige, porque Development falló
por contrato y por recursos, no por puntuación. Ninguna comprobación de aquí
mide calidad: todas responden a "¿esto entrega?".

Cada comprobación falla cerrada y explica qué falta. El código de salida es 0
sólo si las cuatro pasan.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from ..common.contract import validate_run
from ..common.slugs import output_filenames

V1 = Path(__file__).resolve().parents[1]
REPO = V1.parent
EXPECTED = {1: 195, 2: 153, 3: 75}
VRAM_CEILING_MIB = 22 * 1024


#: Los seis ficheros que declara la página del algoritmo, campo "Write to".
#: Confirmados el 11-sep-2026 contra las Interfaces de `blackboard-experts-and-llms`.
GC_OUTPUTS = {
    1: ['prostate-biopsy-decision.json',
        'prostate-biopsy-decision-reasoning.json'],
    2: ['prostate-treatment-decision.json',
        'prostate-treatment-decision-reasoning.json'],
    3: ['prostate-time-to-recurrence-or-last-follow-up.json',
        'prostate-time-to-recurrence-or-last-follow-up-reasoning.json'],
}


def check_slugs(strict='canonical'):
    """Lo que escribe el código contra lo que GC declara. Ya no es una apuesta."""
    names = {task: output_filenames(task, strict) for task in (1, 2, 3)}
    desajuste = {task: {'escribe': sorted(names[task]), 'gc_declara': sorted(GC_OUTPUTS[task])}
                 for task in (1, 2, 3) if sorted(names[task]) != sorted(GC_OUTPUTS[task])}
    return {'passed': not desajuste, 'strict': strict, 'filenames': names,
            'desajuste': desajuste, 'user_confirmation': True,
            'note': 'Confirmado en la página del algoritmo. El slug se trunca a 50 caracteres '
                    '(...-reas, ...-clin) pero el fichero lleva el nombre entero.'}


def check_coverage(output_root, strict='canonical'):
    """423 casos con salida válida. Un caso que revienta tumba Development entero."""
    result = validate_run(Path(output_root), REPO/'data', (1, 2, 3), strict)
    result['expected_total'] = sum(EXPECTED.values())
    result['valid_total'] = sum(v['valid'] for v in result['counts'].values())
    result['complete'] = result['valid_total'] == result['expected_total']
    result['passed'] = bool(result['passed'] and result['complete'])
    return result


def check_resources(smoke_dir=None):
    """El presupuesto real de GC: exit 0, dos ficheros, y VRAM bajo el techo."""
    runs = sorted((V1/'verification').glob('gpu_smoke_*/validation.json'))
    chosen = Path(smoke_dir)/'validation.json' if smoke_dir else (runs[-1] if runs else None)
    if chosen is None or not chosen.exists():
        return {'passed': False, 'error': 'No hay smoke de contenedor; ejecútalo antes de empaquetar.'}
    data = json.loads(chosen.read_text())
    peaks = [c.get('peak_gpu_used_mib') or 0 for c in data.get('cases', [])]
    bad = [c['interface'] for c in data.get('cases', [])
           if c.get('exit_code') != 0 or len(c.get('files') or []) != 2
           or not c.get('schema_valid') or (c.get('peak_gpu_used_mib') or 0) > VRAM_CEILING_MIB]
    return {'passed': not bad and bool(peaks), 'source': str(chosen), 'failing_interfaces': bad,
            'peak_gpu_mib': max(peaks) if peaks else None, 'ceiling_mib': VRAM_CEILING_MIB,
            'slug_confirmation': data.get('slug_confirmation')}


def check_forms(output_root):
    """`variable_weights` completo. Es la causa raíz que tumbó la entrega anterior."""
    from chimera_agent_baseline.output.schema import TASK1_VARIABLES, TASK2_VARIABLES
    expected = {1: set(TASK1_VARIABLES), 2: set(TASK2_VARIABLES)}
    bad = []
    for task in (1, 2):
        folder = Path(output_root)/f'task{task}'
        if not folder.exists():
            bad.append({'task': task, 'error': 'sin salida'})
            continue
        for case in sorted(p for p in folder.iterdir() if p.is_dir()):
            found = list(case.glob('*-reasoning.json'))
            if not found:
                bad.append({'task': task, 'case_id': case.name, 'error': 'sin reasoning'})
                continue
            weights = json.loads(found[0].read_text()).get('variable_weights', {})
            if set(weights) != expected[task]:
                bad.append({'task': task, 'case_id': case.name,
                            'missing': sorted(expected[task]-set(weights)),
                            'extra': sorted(set(weights)-expected[task])})
    return {'passed': not bad, 'offenders': bad[:20], 'n_offenders': len(bad)}


def gate(output_root=None, smoke_dir=None, strict='canonical'):
    checks = {'slugs': check_slugs(strict), 'recursos': check_resources(smoke_dir)}
    if output_root:
        checks['cobertura'] = check_coverage(output_root, strict)
        checks['formularios'] = check_forms(output_root)
    else:
        for name in ('cobertura', 'formularios'):
            checks[name] = {'passed': False, 'error': 'requiere --output-root de una corrida completa'}
    return {'passed': all(c.get('passed') for c in checks.values()), 'checks': checks,
            'scope': 'Contrato y recursos. No dice nada sobre la calidad de las predicciones.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root', type=Path, help='raíz con task1/ task2/ task3/')
    p.add_argument('--smoke-dir', type=Path, help='por defecto, el smoke más reciente')
    p.add_argument('--strict', default='canonical', choices=['canonical', 'legacy', ''])
    p.add_argument('--json-out', type=Path)
    args = p.parse_args()
    result = gate(args.output_root, args.smoke_dir, args.strict)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text+'\n')
    print(text)
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
