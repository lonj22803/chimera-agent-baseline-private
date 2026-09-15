"""Full-cohort nested replay after successful frozen DEV/VAL selection; no VAL retuning."""
import json
import pickle
from pathlib import Path
import numpy as np
from . import nested_survival as N
from version_final_reto.common.chimera_experts.io import load_cases
from version_final_reto.common.chimera_experts import dataset_task3 as ds

OUT=Path(__file__).parent/'results/survival_total.json'
ART=N.ROOT/'version_final_reto/task_3/experts_3/train/artifacts'


def main():
    prior=json.loads(N.OUT.read_text())
    if not prior['eligible_for_adoption']: raise SystemExit('DEV/VAL gate failed')
    if OUT.exists(): raise SystemExit('Total result already frozen')
    cases=load_cases(N.ROOT/'data/task3',3,labelled_only=True)
    t=np.array([c.label['months_to_recurrence'] for c in cases],float)
    e=np.array([c.label['event'] for c in cases],int)
    risk=np.array([ds._surgical(c)['capra_s'] for c in cases])
    predictions=[];folds=[]
    for seed in N.SEEDS:
        p=np.empty(len(cases))
        for fold,(tr,te) in enumerate(N.P.folds(e,seed)):
            train=[cases[i] for i in tr];test=[cases[i] for i in te]
            winner,choices,model=N.select(train,t[tr],e[tr],risk[tr],seed+fold+1000)
            trp=N.predict(winner,model,train,risk[tr]);tep=N.predict(winner,model,test,risk[te])
            p[te]=[(np.sum(trp<v)+.5*np.sum(trp==v))/len(tr) for v in tep]
            folds.append({'seed':seed,'fold':fold,'train':[cases[i].case_id for i in tr],
                          'test':[cases[i].case_id for i in te],'winner':winner,'inner_choices':choices})
            print(seed,fold,winner,flush=True)
        predictions.append(p)
    p=np.mean(predictions,axis=0)
    score=N.P.concordance(t,p,e);base=N.P.concordance(t,-risk,e)
    winner,choices,model=N.select(cases,t,e,risk,4444)
    train_raw=N.predict(winner,model,cases,risk)
    result={'protocol':'Same nested spokesperson selection as DEV; 3 seeds x 5 outer folds, 3 inner folds, preprocessing fitted in each training fold',
            'case_ids':[c.case_id for c in cases], 'n':len(cases),'events':int(e.sum()),
            'baseline_c_index':base,'candidate_c_index':score,'paired_ci95':N.P.interval(t,p,e,other=-risk),
            'percentiles':p.tolist(),'folds':folds,'final_selection':winner,'final_choices':choices,
            'adopted':False,'eligible':bool(score>base),
            'limitations':'Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold.'}
    # The numerical map is fixed before this full evaluation, so cannot invert ranks.
    result['months']=(90*np.exp(-.1*12*(1-p))).tolist()
    result['time_score']=N.P.time_score(t,np.asarray(result['months']),e)
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (ART/'spokesperson_candidate.json').write_text(json.dumps({
        'case_ids':result['case_ids'],'percentiles':result['percentiles'],'months':result['months'],
        'final_selection':winner,'train_raw':train_raw.tolist(),'a':90.,'b':.1,'risk_scale':12.,
        'evaluation':{k:result[k] for k in ('n','events','baseline_c_index','candidate_c_index','paired_ci95','eligible','adopted','limitations')}
    },indent=2)+'\n')
    (ART/'spokesperson_candidate.joblib').write_bytes(pickle.dumps(model,protocol=5))
    print(json.dumps({k:result[k] for k in ('baseline_c_index','candidate_c_index','paired_ci95','final_selection','time_score','eligible')},indent=2))


if __name__=='__main__':main()
