"""Validate real disk outputs. Missing cases, malformed shapes and aliases fail closed."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from .guards import validate_output
from .slugs import output_filenames, REASONINGS, DECISIONS, ALIASES

ROOT = Path(__file__).resolve().parents[2]


def validate_case(task, folder, strict='canonical'):
    names = output_filenames(task, strict)
    actual = {p.name for p in folder.glob('*.json') if p.name != 'acta.json'}
    if actual != set(names):
        raise ValueError(f'Missing or extra outputs: expected={names}, actual={sorted(actual)}')
    content = {n: json.loads((folder/n).read_text()) for n in names}
    decision = content.get(DECISIONS[task], content.get(ALIASES.get(task, ('', ''))[1]))
    reasoning = content.get(REASONINGS[task], content.get(ALIASES.get(task, ('', ''))[1]))
    if task in ALIASES and all(n in content for n in ALIASES[task]):
        if content[ALIASES[task][0]] != content[ALIASES[task][1]]:
            raise ValueError('Aliases contain different predictions')
    payload = {'case_id': folder.name, 'task': task}
    if task == 3:
        if not isinstance(decision, dict) or set(decision) != {'event', 'months_to_recurrence'}:
            raise ValueError('Invalid survival decision')
        if type(decision['event']) is not int or decision['event'] not in (0, 1):
            raise ValueError('Invalid event')
        if type(decision['months_to_recurrence']) not in (float, int) or not math.isfinite(decision['months_to_recurrence']):
            raise ValueError('Invalid horizon')
        payload.update(months_to_recurrence=decision['months_to_recurrence'], reasoning=reasoning)
    else:
        if not isinstance(reasoning, dict) or set(reasoning) != {'confidence', 'variable_weights', 'reveal_sequence', 'free_text'}:
            raise ValueError('Invalid reasoning fields')
        payload.update({k: reasoning[k] for k in ('confidence', 'variable_weights', 'reveal_sequence')})
        payload['reasoning'] = reasoning['free_text']
        if task == 1:
            if decision not in ('yes', 'no'):
                raise ValueError('Invalid biopsy decision')
            payload['biopsy_decision'] = decision == 'yes'
        else:
            payload['action'] = decision
    ok, why = validate_output(task, payload)
    if not ok:
        raise ValueError(why)
    return payload


def validate_run(output_root, data_root=ROOT/'data', tasks=(1, 2, 3), strict='canonical'):
    errors, counts = [], {}
    for task in tasks:
        expected = {p.name for p in (data_root/f'task{task}/agent_input').iterdir() if p.is_dir()}
        folder = output_root/f'task{task}'
        actual = {p.name for p in folder.iterdir() if p.is_dir()} if folder.exists() else set()
        if actual != expected:
            errors.append({'task': task, 'missing': sorted(expected-actual), 'extra': sorted(actual-expected)})
        valid = 0
        for cid in sorted(actual):
            try:
                validate_case(task, folder/cid, strict)
                valid += 1
            except (ValueError, KeyError, TypeError, OSError) as exc:
                errors.append({'task': task, 'case_id': cid, 'error': str(exc)})
        counts[task] = {'expected': len(expected), 'valid': valid}
    return {'passed': not errors, 'counts': counts, 'errors': errors,
            'scope': 'Output contract only; does not establish model execution or GPU budget'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--data-root', type=Path, default=ROOT/'data')
    p.add_argument('--tasks', nargs='+', type=int, default=[1, 2, 3])
    p.add_argument('--strict', choices=['canonical', 'legacy', ''], default='canonical')
    p.add_argument('--json-out', type=Path)
    args = p.parse_args()
    result = validate_run(args.output_root, args.data_root, args.tasks, args.strict)
    text = json.dumps(result, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text+'\n')
    print(text)
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
