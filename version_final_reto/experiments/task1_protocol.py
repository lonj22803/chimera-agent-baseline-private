"""DEV-only threshold exploration with OOF experts and self exclusion."""
from collections import Counter
import json
from pathlib import Path
import numpy as np
from version_final_reto.task_1.analysis import simulate as S
from version_final_reto.task_1.agent import protocol as P
from version_final_reto.task_1.experts_1.panel import Panel
from version_final_reto.common.chimera_experts.io import load_case
from dev.score_local import load_evaluator, DEFAULT_EVAL_REPO

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'results/task1_protocol.json'


def main():
    if OUT.exists(): raise SystemExit('Frozen result already exists; no repeated VAL selection')
    dev=set((ROOT/'dev/splits/task1_dev.txt').read_text().splitlines())
    val=set((ROOT/'dev/splits/task1_val.txt').read_text().splitlines())
    panel=Panel(S.CACHE); ev=load_evaluator(DEFAULT_EVAL_REPO)
    def run(ids, threshold):
        rows=S.simulate('honest',True,3,{**P.PARAMS,'threshold':threshold},'model+mode',panel,only=ids)
        score=S.score(rows)
        return rows,{k:v for k,v in score.items() if k!='rows'}
    grid=[]
    for threshold in np.arange(.30,.651,.025):
        _,score=run(dev,float(threshold))
        grid.append({'threshold':round(float(threshold),3),**score})
    baseline_rows, baseline=run(dev,.45)
    # Threshold affects decisions; use decision F1 to select, not redistributed rationale weights.
    best=max(grid,key=lambda r:(r['f1_yes'],-abs(r['threshold']-.45)))
    result={'protocol':__doc__,'dev_grid':grid,'baseline_dev':baseline,'selected':best,'adopted':False,
            'caveat':'OOF cache is historical. Cohort/grade rules and form priors were already fitted on this cohort; not independent external performance.'}
    if best['f1_yes']>baseline['f1_yes'] and best['threshold']!=.45:
        _,b=run(val,.45);_,c=run(val,best['threshold'])
        result['val']={'baseline':b,'candidate':c}
        result['eligible_for_paired_judge']=bool(c['f1_yes']>b['f1_yes'])
    else:
        result['val']={'status':'not evaluated: no DEV improvement'}
        result['eligible_for_paired_judge']=False
    # Confidence modes are fitted per DEV query excluding its label.
    cases={cid:load_case(ROOT/'data/task1',cid,1) for cid in dev}
    measures=[]
    for row in baseline_rows:
        cid=row['case_id'];case=cases[cid]
        pool=[c for key,c in cases.items() if key!=cid and c.prompt.get('bx')==case.prompt.get('bx')]
        if not pool: pool=[c for key,c in cases.items() if key!=cid]
        mode=Counter(c.reasoning['confidence'] for c in pool).most_common(1)[0][0]
        measures.append({'case_id':cid,'agreement':ev.confidence_score(case.reasoning,row['pred']),
                         'bucket_mode':ev.confidence_score(case.reasoning,{'confidence':mode}),
                         'clear':ev.confidence_score(case.reasoning,{'confidence':'clear'})})
    result['confidence_dev']={k:float(np.mean([r[k] for r in measures])) for k in ('agreement','bucket_mode','clear')}
    result['confidence_rows']=measures
    result['confidence_adopted']=False
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('dev_grid','confidence_rows')},indent=2))


if __name__=='__main__': main()
