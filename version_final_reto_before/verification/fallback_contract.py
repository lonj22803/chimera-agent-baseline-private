"""CPU safety net for every known input and degraded input; not a GPU coverage run."""
import importlib
import json
from pathlib import Path
from version_final_reto.common.chimera_experts.io import Case, CLINICAL_FILENAME, FEATURES_FILENAME
from version_final_reto.common.contract import validate_case
from version_final_reto.common.slugs import output_files
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'version_final_reto/verification/fallback_contract'
errors=[];counts={}
for task in (1,2,3):
    runner=importlib.import_module(f'version_final_reto.task_{task}.agent.run_task{task}')
    folders=sorted(p for p in (ROOT/f'data/task{task}/agent_input').iterdir() if p.is_dir())
    counts[task]={'known_inputs':len(folders),'valid':0,'degraded_valid':0}
    for folder in [*folders,None]:
        case=Case(folder.name if folder else 'minimal',task)
        if folder:
            case.prompt=json.loads((folder/'structured-prompt.json').read_text())
            case.clinical=json.loads((folder/CLINICAL_FILENAME[task]).read_text())
        payload,event=runner.fallback_case(case)
        values=runner.to_gc_outputs(payload,event).values() if task==3 else runner.to_gc_outputs(payload)
        target=OUT/f'task{task}'/case.case_id;target.mkdir(parents=True,exist_ok=True)
        decision,reasoning=values
        for name,value in output_files(task,decision,reasoning,'canonical').items():
            (target/name).write_text(json.dumps(value,allow_nan=False)+'\n')
        try:
            validate_case(task,target)
            counts[task]['valid' if folder else 'degraded_valid']+=1
        except Exception as exc:errors.append({'task':task,'case_id':case.case_id,'error':str(exc)})
report={'scope':__doc__,'counts':counts,'errors':errors,'passed':not errors}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));raise SystemExit(1 if errors else 0)
