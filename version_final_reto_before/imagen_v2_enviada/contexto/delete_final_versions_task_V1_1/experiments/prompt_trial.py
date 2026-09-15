"""Generate a frozen chair comparison from actual patient documents, using delivery vLLM."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time
from delete_final_versions_task_V1_1.common.chimera_experts.io import Case,CLINICAL_FILENAME
from delete_final_versions_task_V1_1.common import guards,prompt_kit
from delete_final_versions_task_V1_1.common.sampling import speak_as,VOICES
from delete_final_versions_task_V1_1.common.telemetry import ConferenceMeter,ResourceMonitor
from delete_final_versions_task_V1_1.common.runtime import configure
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task',type=int,choices=[2,3],required=True)
    p.add_argument('--split',choices=['dev','val','all'],default='dev')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--coverage',type=Path,required=True)
    args=p.parse_args()
    if (args.out/'manifest.json').exists():raise SystemExit('Frozen generation already exists')
    ids=sorted(set((ROOT/f'dev/splits/task{args.task}_{args.split}.txt').read_text().splitlines())) if args.split!='all' else sorted(p.name for p in (ROOT/f'data/task{args.task}/ground_truth').iterdir() if p.is_dir())
    from hydra import compose,initialize_config_dir
    from chimera_agent_baseline.models import load_model
    from langchain_core.messages import SystemMessage,HumanMessage
    with initialize_config_dir(config_dir=str(ROOT/'configs'),version_base=None):
        cfg=compose(config_name='config',overrides=['+experiment=local_paths'])
    configure(cfg);model=load_model(cfg);meter=ConferenceMeter(getattr(model,'tokenizer',None))
    voice=speak_as(model,VOICES['chair']);rows=[]
    args.out.mkdir(parents=True,exist_ok=True)
    if args.task==3:
        from delete_final_versions_task_V1_1.task_3.agent.graph import LocalChair,create_conference_graph
        from delete_final_versions_task_V1_1.task_3.agent.protocol import Panel
        panel=Panel('deployed',spokesperson='capra')
    with ResourceMonitor() as resources:
        for cid in ids:
            folder=ROOT/f'data/task{args.task}/agent_input'/cid
            case=Case(cid,args.task,prompt=json.loads((folder/'structured-prompt.json').read_text()),
                      clinical=json.loads((folder/CLINICAL_FILENAME[args.task]).read_text()))
            for variant in ('baseline','candidate'):
                meter.start_case(cid);start=time.monotonic()
                os.environ[f'CHIMERA_T{args.task}_PROMPT']='enhanced' if variant=='candidate' else 'baseline'
                if args.task==3:
                    from delete_final_versions_task_V1_1.task_3.agent.decide import to_gc_outputs
                    os.environ['CHIMERA_T3_ADVICE']='enhanced' if variant=='candidate' else 'baseline'
                    # Same frozen experts in both variants; input embeddings do not affect the CAPRA horizon.
                    emb=folder/'prostate-modality-level-neural-representations.json'
                    case.embeddings=json.loads(emb.read_text()) if emb.exists() else {}
                    result=create_conference_graph(panel,LocalChair(model,meter)).invoke(case)
                    files=to_gc_outputs(result['payload'],result['event']);fallback=result['fallback']
                    board=result['board'].to_dict()
                else:
                    from delete_final_versions_task_V1_1.task_2.agent import decide,prompts,protocol
                    # Copy the actual retrieved view, decision and form from the coverage board.
                    matches=list((args.coverage/'task_2').rglob(f'boards/{cid}.json'))
                    if len(matches)!=1:raise ValueError(f'Expected one coverage board for {cid}, found {len(matches)}')
                    source=json.loads(matches[0].read_text())
                    registrar=[it for it in source['interventions'] if it['speaker']=='REGISTRAR'][-1]
                    opened=registrar['data']['opened']
                    documents={k:case.clinical[k] for k in opened if k in case.clinical}
                    proto=[it['data'] for it in source['interventions'] if it['speaker']=='PANEL-PROTOCOL'][-1]
                    digest=prompts.clinical_digest(case.prompt,documents,proto['decision'])
                    if variant=='candidate':digest+=prompt_kit.chair_context(2,case.prompt,cid)
                    attempts=[];note=None
                    for _ in range(3):
                        reply=voice.invoke([SystemMessage(content=prompts.CHAIR_SYSTEM),HumanMessage(content=digest)],config={'callbacks':[meter]})
                        raw=reply.content if isinstance(reply.content,str) else json.dumps(reply.content)
                        candidate=guards.parse_json(raw).get('reasoning')
                        issues=decide.note_faults(candidate,case.prompt,documents) if isinstance(candidate,str) and len(candidate.strip())>=40 else ['invalid note JSON']
                        attempts.append({'text':candidate,'issues':issues})
                        if not issues:note=candidate;break
                        digest+='\n'+prompt_kit.chair_challenge(issues)
                    payload,_=decide.build_output(cid,case.prompt,proto,opened,note)
                    decision,reasoning=decide.to_gc_outputs(payload)
                    files={'prostate-treatment-decision.json':decision,'prostate-treatment-decision-reasoning.json':reasoning}
                    fallback=note is None;board={'case_id':cid,'attempts':attempts}
                dest=args.out/variant/'output'/f'task{args.task}'/cid;dest.mkdir(parents=True,exist_ok=True)
                for name,value in files.items():(dest/name).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
                (dest/'acta.json').write_text(json.dumps(board,ensure_ascii=False)+'\n')
                row={'case_id':cid,'variant':variant,'seconds':time.monotonic()-start,'fallback_note':fallback,**meter.summary()}
                rows.append(row)
                with (args.out/'telemetry.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            print(f'T{args.task} {args.split}: {len(rows)//2}/{len(ids)}',flush=True)
        manifest={'backend':'vllm','model_id':cfg.model.model_id,'task':args.task,'split':args.split,
                  'case_ids':ids,'gpu_fraction':cfg.generation.gpu_memory_utilization,**resources.summary(),
                  'variants':{'baseline':'V1 delivery chair','candidate':'shared frame, examples, literal report quotes; T3 also narrative experience and deterministic guideline'},
                  'labels_read_for_inference':False,'numeric_policy':'fixed across variants'}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
