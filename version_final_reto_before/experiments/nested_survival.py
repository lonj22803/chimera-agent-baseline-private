"""Select CAPRA-S versus fusion INSIDE DEV outer folds; confirm VAL at most once.

No stored OOF scores are used to select a spokesperson. Every Cox imputer,
projection and penalty is fitted within the corresponding training fold.
Historical labels have already been inspected by previous work: fixed VAL is
therefore a confirmation set, not a previously unseen external cohort.
"""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import numpy as np
from version_final_reto.common.chimera_experts.io import load_cases
from version_final_reto.common.chimera_experts import dataset_task3 as ds
from version_final_reto.task_3.experts_3.train import protocol as P

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'results/nested_survival.json'
SEEDS=(111, 223, 337)
FAMILIES=('CAPRA-S', 'S+anchor', 'ASGDE')


def select(cases, times, events, risk, seed):
    candidates=[{'family':'CAPRA-S','score':P.concordance(times,-risk,events)}]
    matrices={}
    for family, blocks in [('S+anchor','S'),('ASGDE','ASGDE')]:
        x,names=ds.build_matrix(cases,blocks,drop_constant=False)
        matrices[family]=(x,names)
        (k,alpha),scores=P.select(x,times,events,names,seed)
        candidates.append({'family':family,'k':k,'alpha':alpha,'score':max(scores)})
    # Ties prefer the predeclared anchor and then the smaller surgical model.
    winner=max(candidates,key=lambda c:(c['score'], -FAMILIES.index(c['family'])))
    if winner['family']=='CAPRA-S':
        return winner,candidates,None
    x,names=matrices[winner['family']]
    model=P.CoxPipeline().fit(x,times,events,names,winner['k'],winner['alpha'])
    return winner,candidates,model


def predict(winner,model,cases,risk):
    if winner['family']=='CAPRA-S':
        return -risk
    x,names=ds.build_matrix(cases,'S' if winner['family']=='S+anchor' else 'ASGDE',drop_constant=False)
    x=x[:,[names.index(n) for n in model.names]]
    return -model.risk(x)


def main():
    if OUT.exists():
        raise SystemExit('Experiment already frozen; do not tune repeatedly against VAL')
    all_cases=load_cases(ROOT/'data/task3',3,labelled_only=True)
    dev_ids=set((ROOT/'dev/splits/task3_dev.txt').read_text().splitlines())
    val_ids=set((ROOT/'dev/splits/task3_val.txt').read_text().splitlines())
    assert not dev_ids&val_ids
    cases=[c for c in all_cases if c.case_id in dev_ids]
    t=np.array([c.label['months_to_recurrence'] for c in cases],float)
    e=np.array([c.label['event'] for c in cases],int)
    risk=np.array([ds._surgical(c)['capra_s'] for c in cases])
    predictions=[]; audits=[]; family_predictions={f:[] for f in FAMILIES}
    for seed in SEEDS:
        p=np.empty(len(cases)); by_family={f:np.empty(len(cases)) for f in FAMILIES}
        for fold,(tr,te) in enumerate(P.folds(e,seed)):
            train=[cases[i] for i in tr]; test=[cases[i] for i in te]
            winner,choices,model=select(train,t[tr],e[tr],risk[tr],seed+fold+1000)
            # Transform arbitrary model scales into training-cohort percentiles
            # before pooling predictions from different spokesperson families.
            raw=predict(winner,model,test,risk[te])
            train_raw=predict(winner,model,train,risk[tr])
            p[te]=[(np.sum(train_raw<v)+.5*np.sum(train_raw==v))/len(tr) for v in raw]
            for choice in choices:
                family=choice['family']
                if family=='CAPRA-S':
                    by_family[family][te]=-risk[te]
                    continue
                x,names=ds.build_matrix(train,'S' if family=='S+anchor' else 'ASGDE',drop_constant=False)
                fm=P.CoxPipeline().fit(x,t[tr],e[tr],names,choice['k'],choice['alpha'])
                by_family[family][te]=predict(choice,fm,test,risk[te])
            audit={'seed':seed,'fold':fold,'train':[cases[i].case_id for i in tr],
                   'test':[cases[i].case_id for i in te],'winner':winner,'inner_choices':choices}
            audits.append(audit)
            print(f"seed {seed} fold {fold}: {winner}",flush=True)
        predictions.append(p)
        for family in FAMILIES: family_predictions[family].append(by_family[family])
    pred=np.mean(predictions,axis=0)
    baseline=P.concordance(t,-risk,e)
    candidate=P.concordance(t,pred,e)
    result={'protocol':__doc__,'dev_n':len(cases),'dev_events':int(e.sum()),'seeds':SEEDS,
            'families':{f:{'c_index':P.concordance(t,np.mean(ps,axis=0),e),
                          'paired_ci95':P.interval(t,np.mean(ps,axis=0),e,other=-risk)}
                        for f,ps in family_predictions.items()},
            'dev':{'baseline_c_index':baseline,'selected_c_index':candidate,
                   'paired_ci95':P.interval(t,pred,e,other=-risk)},
            'winner_counts':dict(Counter(a['winner']['family'] for a in audits)), 'folds':audits,
            'dev_ids':[c.case_id for c in cases], 'dev_predictions':pred.tolist(),
            'adopted':False,'warning':'19 events overall; intervals are wide. VAL has historical exposure.'}
    # Read VAL labels only after DEV selection succeeds; never search again on VAL.
    if candidate>baseline:
        winner,choices,model=select(cases,t,e,risk,4444)
        val=[c for c in all_cases if c.case_id in val_ids]
        vt=np.array([c.label['months_to_recurrence'] for c in val],float)
        ve=np.array([c.label['event'] for c in val],int)
        vr=np.array([ds._surgical(c)['capra_s'] for c in val])
        vp=predict(winner,model,val,vr)
        result['val']={'selected':winner,'n':len(val),'events':int(ve.sum()),
                       'baseline_c_index':P.concordance(vt,-vr,ve),'candidate_c_index':P.concordance(vt,vp,ve),
                       'paired_ci95':P.interval(vt,vp,ve,other=-vr)}
        result['eligible_for_adoption']=bool(result['val']['candidate_c_index']>result['val']['baseline_c_index'])
    else:
        result['val']={'status':'not opened: DEV selection did not beat CAPRA-S'}
        result['eligible_for_adoption']=False
    # Horizons: fixed monotonic families preserve global CAPRA ordering, unlike
    # independently fitted arbitrary per-group scales. Explore ONLY on DEV.
    scale_grid=np.arange(60.,151.,5.)
    scores=[P.time_score(t,a*np.exp(-.1*risk),e) for a in scale_grid]
    a=float(scale_grid[int(np.argmax(scores))])
    thresholds=[float('inf'),*map(float,range(3,13))]
    group_predictions=np.empty(len(t),int)
    group_audits=[]
    for g in sorted(set(risk)):
        tr=risk!=g; te=~tr
        accuracies=[float(np.mean((risk[tr]>=th)==e[tr])) for th in thresholds]
        th=thresholds[int(np.argmax(accuracies))]
        group_predictions[te]=(risk[te]>=th).astype(int)
        group_audits.append({'held_out_capra':float(g),'threshold':th if np.isfinite(th) else 'never',
                             'train_n':int(tr.sum()),'test_n':int(te.sum())})
    result['horizon_dev']={'selected_a':a,'b':.1,'candidate_time_score':max(scores),
                          'constant60_time_score':P.time_score(t,np.full(len(t),60.),e),
                          'event_group_cv_accuracy':float(np.mean(group_predictions==e)),
                          'event_capra9_accuracy':float(np.mean((risk>=9)==e)),
                          'folds':group_audits,'adopted':False,
                          'status':'DEV exploration only; separate VAL confirmation required before adoption'}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k in ('dev','val','families','winner_counts','eligible_for_adoption','horizon_dev')},indent=2))


if __name__=='__main__': main()
