"""Read archived boards and emit an evidence trail, never hard-coded case rules."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'version_final_reto/investigacion/referencias_historicas'
OUT=Path(__file__).parent/'results/case_audit.json'
IDS={1:['PT-pseudo_'+s for s in ['0169468160c6','175e6ad47991','1dc32184cab6','b9f0b7018502','d7d26761c714','37d8ae9b27f1','3b6ea1920967','d217629c323a']],
     2:['T2-031','T2-032','T2-008','T2-011','T2-018','T2-043','T2-108'],
     3:['T3-019','T3-022','T3-060','T3-068','T3-072']}
result={}
for task,ids in IDS.items():
    result[task]=[]
    for cid in ids:
        path=OLD/f'task_{task}/boards/{cid}.json' if task<3 else OLD/f'task_3/output/task3/{cid}/acta.json'
        board=json.loads(path.read_text())
        turns=[{k:it[k] for k in ('speaker','body','data') if k in it} for it in board['interventions']
               if it['speaker'] in {'INTAKE','EXPERT-COHORT','REGISTRAR','PANEL-PROTOCOL','CHAIR','EXPERT-CASCADE','EXPERT-FITNESS'}]
        result[task].append({'case_id':cid,'source':str(path.relative_to(ROOT)), 'turns':turns})
result['trace_gap']=[]
for line in (OLD/'task_1/summary.jsonl').read_text().splitlines():
    row=json.loads(line)
    planned=row.get('planned') or []
    opened=row.get('reveal_sequence') or []
    if set(planned)!=set(opened):
        result['trace_gap'].append({'case_id':row['case_id'],'planned':planned,'opened':opened})
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
for task in (1,2,3):
    for row in result[task]:
        print(task,row['case_id'])
        for turn in row['turns']:
            if turn['speaker'] in ('PANEL-PROTOCOL','CHAIR'):
                d=turn.get('data',{})
                print(turn['speaker'],json.dumps({k:d[k] for k in ('decision','rule','who','grade','fallback','attempts') if k in d},ensure_ascii=False)[:2000])
print('Plan/opening gaps',len(result['trace_gap']))
