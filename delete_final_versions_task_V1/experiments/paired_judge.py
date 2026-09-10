"""Two paired passes with one official judge and one pinned Ollama residency."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def api(route,data=None):
    req=urllib.request.Request(os.environ.get('OLLAMA_BASE_URL','http://localhost:11434')+'/api/'+route,
        data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)


def runners():
    result=subprocess.run(['pgrep','-f','ollama runner'],text=True,capture_output=True)
    return sorted(result.stdout.split())


def run(baseline,candidate,task,split,out):
    if out.exists():raise ValueError('Paired experiment already frozen; choose a new scientific candidate, not a reroll')
    from dev import score_with_judge as loader
    ev=loader.load_evaluator(loader.DEFAULT_EVAL_REPO)
    data=ROOT/f'data/task{task}'
    gts=ev.load_ground_truth_records(data/'ground_truth',f'task{task}')
    ids=set((ROOT/f'dev/splits/task{task}_{split}.txt').read_text().splitlines()) if split!='all' else {ev.get_case_id(g) for g in gts}
    gts=[g for g in gts if ev.get_case_id(g) in ids]
    preds={label:loader.load_predictions(path,data,task) for label,path in [('baseline',baseline),('candidate',candidate)]}
    for label,records in preds.items():
        if ids-records.keys():raise ValueError(f'{label} missing {sorted(ids-records.keys())}')
    model=os.environ.get('JUDGE_MODEL','gemma4:e4b')
    before=api('ps')
    # This script is run only after the vLLM process has exited. Pin the judge.
    warm=api('generate',{'model':model,'keep_alive':-1,'stream':False})
    resident=api('ps');pids=runners()
    judge=ev.build_rationale_judge()
    if judge is None:raise RuntimeError('Official judge did not start')
    if not pids:raise RuntimeError('Cannot verify Ollama runner residency')
    result={'task':task,'split':split,'model':model,'resident':resident,'runner_pids':pids,
            'judge_instances':1,'passes':[], 'scope':'Official clinical_data context unchanged; no structured prompt injected',
            'evaluator_sha256':hashlib.sha256((loader.DEFAULT_EVAL_REPO/'evaluation/evaluate.py').read_bytes()).hexdigest(),
            'output_sha256':{label:{str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (path/f'task{task}').rglob('*.json') if p.parent.name in ids and p.name!='acta.json'}
                             for label,path in [('baseline',baseline),('candidate',candidate)]}}
    start=time.monotonic()
    for pass_index in (1,2):
        rows={'baseline':[],'candidate':[]}
        order=('baseline','candidate') if pass_index==1 else ('candidate','baseline')
        for index,gt in enumerate(gts,1):
            cid=ev.get_case_id(gt)
            for label in order:
                row=(ev.evaluate_recurrence_case(gt,preds[label][cid],judge) if task==3 else
                     ev.evaluate_case(gt,preds[label][cid],None,judge))
                if (task==3 or row.get('decision_score')==1.) and row.get('rationale_score') is None:
                    raise RuntimeError(f'Missing rationale score: {label}/{cid}')
                rows[label].append({k:v for k,v in row.items() if not k.startswith('_')})
            if runners()!=pids:raise RuntimeError('Ollama runner changed during paired measurement')
            print(f'T{task} {split} pass {pass_index}: {index}/{len(gts)}',flush=True)
        aggregates={label:(ev.aggregate_recurrence_metrics(values) if task==3 else ev.compute_aggregate_metrics(values)) for label,values in rows.items()}
        rationale={label:sum(r['rationale_score'] for r in values if r.get('rationale_score') is not None)/sum(r.get('rationale_score') is not None for r in values)
                   for label,values in rows.items()}
        result['passes'].append({'pass':pass_index,'order':order,'aggregates':aggregates,'rationale':rationale,'rows':rows})
    result['rationale_improves_both']=all(p['rationale']['candidate']>p['rationale']['baseline'] for p in result['passes'])
    result['ranking_improves_both']=all(p['aggregates']['candidate']['ranking_score']>p['aggregates']['baseline']['ranking_score'] for p in result['passes'])
    result['eligible']=result['rationale_improves_both'] and (task==3 or result['ranking_improves_both'])
    result['seconds']=time.monotonic()-start
    result['resident_after']=api('ps')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(json.dumps({k:result[k] for k in ('task','split','rationale_improves_both','ranking_improves_both','eligible','seconds')},indent=2))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--task',type=int,choices=[1,2,3],required=True)
    p.add_argument('--split',choices=['dev','val','all'],default='dev');p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();run(args.baseline,args.candidate,args.task,args.split,args.out)


if __name__=='__main__':main()
