"""Validate actual GC files and distinguish schema success from backend success."""
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from chimera_agent_baseline.output.schema import TASK_OUTPUT_MODELS

names = ['prostate-biopsy-decision','prostate-treatment-decision','prostate-time-to-recurrence-or-last-follow-up']
for arg in sys.argv[1:]:
    run = Path(arg)
    summary = json.loads((run/'summary.json').read_text())
    for row in summary['cases']:
        i = row['interface']
        folder = run/f'interf{i}'
        output = folder/'output'
        expected = {names[i]+'.json', names[i]+'-reasoning.json'}
        try:
            assert {p.name for p in output.iterdir()} == expected, 'Missing or extra output files'
            decision = json.loads((output/(names[i]+'.json')).read_text())
            reasoning = json.loads((output/(names[i]+'-reasoning.json')).read_text())
            payload = {'case_id':'smoke_case', 'task':i+1}
            if i == 2:
                assert set(decision) == {'event','months_to_recurrence'}
                assert type(decision['event']) is int and decision['event'] in (0,1)
                assert type(decision['months_to_recurrence']) in (int,float) and math.isfinite(decision['months_to_recurrence'])
                payload.update(months_to_recurrence=decision['months_to_recurrence'],reasoning=reasoning)
            else:
                assert set(reasoning) == {'confidence','variable_weights','reveal_sequence','free_text'}
                payload.update({k:reasoning[k] for k in ('confidence','variable_weights','reveal_sequence')})
                payload['reasoning'] = reasoning['free_text']
                if i == 0:
                    assert type(decision) is str and decision in ('yes','no')
                    payload['biopsy_decision'] = decision == 'yes'
                else:
                    payload['action'] = decision
            TASK_OUTPUT_MODELS[i+1].model_validate(payload)
            row['schema_valid'] = True
            row['decision'] = decision
            row['reasoning_characters'] = len(payload['reasoning'])
        except Exception as exc:
            row['schema_valid'] = False
            row['validation_error'] = str(exc)
        metrics = json.loads((folder/'metrics.json').read_text())
        def bytes_used(sample):
            text = sample['docker'].get('MemUsage','0B').split('/')[0].strip()
            for suffix, factor in [('GiB',2**30),('MiB',2**20),('KiB',2**10),('GB',10**9),('MB',10**6),('kB',10**3),('B',1)]:
                if text.endswith(suffix):
                    return float(text[:-len(suffix)])*factor
            raise ValueError(text)
        row['peak_container_ram_gib_sampled'] = round(max(map(bytes_used,metrics),default=0)/2**30,3)
        log = (folder/'container.log').read_text()
        row['vllm_generation_observed'] = 'Generation throughput' in log or 'Processed prompts:' in log
        row['errors_in_log'] = [line for line in log.splitlines() if 'Error:' in line or 'writing fallback' in line or 'Traceback' in line]
        print(json.dumps(row,ensure_ascii=False))
    (run/'validation.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
