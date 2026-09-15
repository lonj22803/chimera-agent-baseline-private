"""¿Las guardias de 'no biopsiar' del cubo Positive generalizan a los otros cubos?

La tarea 1 aplica tres guardias de abstención (`psa>=20`, `edad>=78`, `pirads<=2`)
**sólo** cuando hay biopsia previa positiva, porque salieron de leer los 49
`free_text` de ese cubo. Pero su razonamiento clínico —"un hombre de 82 años con
enfermedad de bajo riesgo no necesita más diagnóstico"— no depende de la biopsia
previa. Si generalizara, arreglaría fallos en los otros dos cubos.

Se mide en DEV, con los splits fijos. VAL sólo se lee si DEV mejora.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[0] / 'results'


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def cohorte():
    dev = set((REPO/'dev/splits/task1_dev.txt').read_text().split())
    filas = []
    for d in sorted((REPO/'data/task1/ground_truth').iterdir()):
        if not d.is_dir():
            continue
        p = json.loads((REPO/'data/task1/agent_input'/d.name/'structured-prompt.json').read_text())
        y = json.loads((d/'prostate-biopsy-decision.json').read_text())
        filas.append({'cid': d.name, 'bx': str(p.get('bx')), 'pirads': _num(p.get('pirads')),
                      'psa': _num(p.get('psa')), 'psad': _num(p.get('psad')), 'age': _num(p.get('age')),
                      'y': y == 'yes', 'split': 'dev' if d.name in dev else 'val'})
    return filas


def base(fila):
    """La regla de cohorte actual, por cubo."""
    pir = fila['pirads']
    if fila['bx'] == 'None':
        return (pir is not None and pir >= 3)
    if fila['bx'] == 'Negative':
        return (pir is not None and pir >= 4)
    return None  # el cubo Positive lo resuelven las guardias y los peldaños siguientes


def con_guardias(fila):
    """La misma regla, pero con las guardias de abstención aplicadas a los tres cubos."""
    if fila['age'] is not None and fila['age'] >= 78:
        return False
    if fila['psa'] is not None and fila['psa'] >= 20:
        return False
    if fila['pirads'] is not None and fila['pirads'] <= 2:
        return False
    return base(fila)


def medir(filas, regla, split, universo=None):
    """Sobre `universo` si se da, para que base y candidato comparen los MISMOS casos.

    Sin esto la comparación miente: las guardias hacen decidir casos del cubo
    Positive que la regla base dejaba indeterminados, así que cambia el denominador
    y las dos exactitudes dejan de ser comparables.
    """
    sub = [f for f in filas if f['split'] == split
           and (f['cid'] in universo if universo is not None else regla(f) is not None)]
    decididos = [f for f in sub if regla(f) is not None]
    aciertos = sum(regla(f) == f['y'] for f in decididos)
    return {'n': len(decididos), 'aciertos': aciertos,
            'exactitud': round(aciertos/len(decididos), 4) if decididos else None,
            'fallos': [f['cid'] for f in decididos if regla(f) != f['y']]}


def main():
    filas = cohorte()
    salida = {
        'pregunta': 'Las guardias de abstención del cubo Positive, ¿generalizan a None y Negative?',
        'protocolo': 'DEV con los splits fijos. VAL sólo si DEV mejora.',
        'dev': {'base': medir(filas, base, 'dev'),
                'candidato': medir(filas, con_guardias, 'dev',
                                   universo={f['cid'] for f in filas if base(f) is not None})},
        'afectados_por_edad': [
            {'cid': f['cid'], 'bx': f['bx'], 'age': f['age'], 'etiqueta': 'yes' if f['y'] else 'no'}
            for f in filas if f['age'] is not None and f['age'] >= 78],
    }
    d = salida['dev']
    mejora = d['candidato']['aciertos'] > d['base']['aciertos']
    salida['nota_metodo'] = ('Ambas reglas se miden sobre los mismos casos: los que la regla BASE '
                             'decide. Comparar sobre denominadores distintos no diría nada.')
    salida['adoptado'] = False
    salida['val_leido'] = False
    salida['motivo'] = (
        'RECHAZADO. En DEV, sobre los mismos 30 casos, la exactitud cae de 0,9333 a 0,8333: el '
        'candidato arregla 175e6ad47991 y rompe cuatro. VAL no se lee. '
        'La razón es clínica y explica por qué las guardias eran específicas del cubo: el mismo PSA '
        'significa cosas distintas según haya cáncer confirmado o no. Con biopsia positiva previa, '
        'PSA>=20 pide estadificación en vez de más tejido; sin biopsia previa, PSA>=20 es justamente '
        'el motivo para biopsiar. Extender la guardia invierte la decisión donde más importa. '
        'Lo mismo con la edad: el único caso de >=78 sin biopsia previa está etiquetado yes.'
    ) if not mejora else 'Elegible; falta confirmar en VAL'
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/'cohort_guards.json').write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
