"""Confirm the already selected monotone CAPRA scale once on VAL; freeze the result."""
import json
from pathlib import Path
import numpy as np
from .nested_survival import ROOT,OUT as NESTED
from delete_final_versions_task_V1.common.chimera_experts.io import load_cases
from delete_final_versions_task_V1.common.chimera_experts import dataset_task3 as ds
from delete_final_versions_task_V1.task_3.agent.protocol import Panel
from delete_final_versions_task_V1.task_3.experts_3.train.protocol import time_score,concordance
OUT=Path(__file__).parent/'results/horizon.json'


def main():
    if OUT.exists():raise SystemExit('Horizon confirmation already frozen')
    selected=json.loads(NESTED.read_text())['horizon_dev']
    a,b=selected['selected_a'],selected['b']
    cases=load_cases(ROOT/'data/task3',3,labelled_only=True)
    panel=Panel('oof')
    result={'selected_on_dev':{'a':a,'b':b},'splits':{}}
    for split in ('dev','val','all'):
        ids=set((ROOT/f'dev/splits/task3_{split}.txt').read_text().splitlines()) if split!='all' else {c.case_id for c in cases}
        subset=[c for c in cases if c.case_id in ids]
        t=np.array([c.label['months_to_recurrence'] for c in subset]);e=np.array([c.label['event'] for c in subset])
        risk=np.array([ds._surgical(c)['capra_s'] for c in subset])
        baseline=np.array([panel.horizon(c,r)['months_to_recurrence'] for c,r in zip(subset,risk)])
        candidate=a*np.exp(-b*risk)
        result['splits'][split]={'n':len(subset),'baseline_time_score':time_score(t,baseline,e),
                                'candidate_time_score':time_score(t,candidate,e),
                                'baseline_c_index':concordance(t,baseline,e),'candidate_c_index':concordance(t,candidate,e)}
        assert result['splits'][split]['baseline_c_index']==result['splits'][split]['candidate_c_index']
    result['eligible']=all(r['candidate_time_score']>r['baseline_time_score'] for r in result['splits'].values())
    result['adopted']=False
    result['event_policy']='CAPRA >=9 retained: group-held-out DEV sweep did not improve'
    OUT.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
