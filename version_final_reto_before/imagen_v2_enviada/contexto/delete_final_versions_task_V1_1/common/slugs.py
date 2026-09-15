"""Nombres de los sockets de salida, confirmados contra la página del algoritmo.

Confirmado el 11-sep-2026 en las Interfaces de `blackboard-experts-and-llms`. El
detalle que importa: **el slug y el nombre de fichero no son lo mismo**. GC corta
el slug a 50 caracteres para identificarlo (`...-reas`, `...-clin`), pero el campo
"Write to" lleva el nombre entero. Los seis ficheros son:

    T1  /output/prostate-biopsy-decision.json  ·  ...-reasoning.json
    T2  /output/prostate-treatment-decision.json  ·  ...-reasoning.json
    T3  /output/prostate-time-to-recurrence-or-last-follow-up.json  ·  ...-reasoning.json

Así que no hay errata `biospy` en este algoritmo ni razonamiento truncado a
`-reas`: **canonical es lo correcto y es el valor por defecto**. Publicar además el
alias escribiría un tercer fichero que GC no declara, y un fichero de más también
es "extra output files". `CHIMERA_SLUG_STRICT=` (vacío) conserva ese modo doble
sólo como red de emergencia si otro algoritmo declarase la otra grafía.
"""
import os

DECISIONS = {
    1: 'prostate-biopsy-decision.json',
    2: 'prostate-treatment-decision.json',
    3: 'prostate-time-to-recurrence-or-last-follow-up.json',
}
REASONINGS = {t: n.replace('.json', '-reasoning.json') for t, n in DECISIONS.items()}
ALIASES = {
    1: (DECISIONS[1], 'prostate-biospy-decision.json'),
    3: (REASONINGS[3], REASONINGS[3].replace('-reasoning.json', '-reas.json')),
}


def output_filenames(task, strict=None):
    if type(task) is not int or task not in DECISIONS:
        raise ValueError('task must be 1, 2 or 3')
    strict = os.environ.get('CHIMERA_SLUG_STRICT', 'canonical') if strict is None else strict
    if strict not in ('', 'canonical', 'legacy'):
        filename = strict if strict.endswith('.json') else strict + '.json'
        matches = [(t, pair.index(filename)) for t, pair in ALIASES.items() if filename in pair]
        if not matches:
            raise ValueError('Unknown CHIMERA_SLUG_STRICT: ' + strict)
        selected_task, index = matches[0]
        strict = 'legacy' if selected_task == task and index else 'canonical'
    names = [DECISIONS[task], REASONINGS[task]]
    if task in ALIASES:
        canonical, legacy = ALIASES[task]
        if strict == 'legacy':
            names[names.index(canonical)] = legacy
        elif not strict:
            names.append(legacy)
    return names


def output_files(task, decision, reasoning, strict=None):
    return {name: reasoning if '-reasoning.' in name or '-reas.' in name else decision
            for name in output_filenames(task, strict)}
