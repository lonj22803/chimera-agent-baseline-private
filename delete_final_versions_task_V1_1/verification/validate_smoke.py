import json
import sys
from pathlib import Path
from delete_final_versions_task_V1_1.common.contract import validate_case
for arg in sys.argv[1:]:
    root=Path(arg)
    summary=json.loads((root/'summary.json').read_text())
    for row in summary['cases']:
        try:
            validate_case(row['interface']+1,root/f'interf{row["interface"]}/output')
            row['schema_valid']=True
        except Exception as exc:
            row['schema_valid']=False
            row['schema_error']=str(exc)
        row['resource_pass']=(row['exit_code']==0 and not row['dispatch_fallback'] and row['schema_valid']
                              and row['peak_gpu_used_mib'] is not None and row['peak_gpu_used_mib']<22*1024 and row['seconds']<900)
    summary['passed']=all(r['resource_pass'] for r in summary['cases']) and len(summary['cases'])==3
    summary['slug_confirmation']='pending user; canonical used provisionally'
    (root/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(root,summary['passed'])
    if not summary['passed']: raise SystemExit(1)
