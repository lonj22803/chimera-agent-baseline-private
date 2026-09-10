"""Run all 423 real cases, serial GPU ownership, frozen code and resource evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(os.environ['CHIMERA_COVERAGE_SOURCE'])
RUN=ROOT/'delete_final_versions_task_V1/verification'/('coverage_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
RUN.mkdir(parents=True)
RUN.chmod(0o777)
IMAGE='chimera_agent_baseline_debug'


def command(args,**kwargs):return subprocess.run(args,text=True,capture_output=True,**kwargs)


def api(route,data=None):
    req=urllib.request.Request('http://localhost:11434/api/'+route,
        data=json.dumps(data).encode() if data else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)


initial=api('ps');active=None
summary={'source':str(SOURCE),'source_sha256':{str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*.py')},
         'image':command(['docker','image','inspect',IMAGE,'--format','{{.Id}}']).stdout.strip(),
         'runs':[],'ollama_before':initial,'scope':'real vLLM batch graphs, deployed experts, self excluded; coverage is not unbiased model evaluation'}
print('RUN_DIR='+str(RUN),flush=True)
try:
    for model in initial['models']:command(['ollama','stop',model['name']],check=True)
    for task in [3,1,2]:
        name=f'chimera-v1-coverage-{task}-{RUN.name}'
        args=['docker','run','-d','--name',name,'--gpus','device=0','--network','none',
              '--memory=32g','--memory-swap=32g','--platform=linux/amd64',
              '-e','CHIMERA_GPU_MEMORY_UTILIZATION=0.8','-e','CHIMERA_VLLM_MAX_GIB=19',
              '-e','CHIMERA_SLUG_STRICT=canonical',
              '-v',f'{SOURCE}:/opt/app/delete_final_versions_task_V1:ro',
              '-v',f'{ROOT}/data:/opt/app/data:ro','-v',f'{ROOT}/model:/opt/ml/model:ro',
              '-v',f'{RUN}:/output','--mount','type=volume,destination=/tmp',
              '--entrypoint','python3',IMAGE,'-m',f'delete_final_versions_task_V1.task_{task}.agent.run_task{task}',
              '--out-root',f'/output/task_{task}','--split','all']
        if task==3:args+=['--backend','vllm','--mode','deployed']
        (RUN/f'task{task}_command.json').write_text(json.dumps(args,indent=2)+'\n')
        command(args,check=True);active=name;start=time.monotonic();samples=[]
        while True:
            state=json.loads(command(['docker','inspect',name,'--format','{{json .State}}'],check=True).stdout)
            if not state['Running']:break
            gpu=command(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits']).stdout.strip()
            stats=command(['docker','stats','--no-stream','--format','{{json .}}',name]).stdout.strip()
            samples.append({'seconds':time.monotonic()-start,'gpu_mib':int(gpu) if gpu.isdigit() else None,
                            'docker':json.loads(stats) if stats else {}})
            (RUN/f'task{task}_resources.json').write_text(json.dumps(samples,indent=2)+'\n')
            progress=sum(1 for p in (RUN/f'task_{task}').rglob('*-reasoning.json'))
            print(f'T{task}: {progress} cases, {time.monotonic()-start:.0f}s, VRAM {gpu} MiB',flush=True)
            if time.monotonic()-start>6*3600:
                command(['docker','stop','-t','10',name]);break
            time.sleep(30)
        logs=command(['docker','logs',name]);(RUN/f'task{task}.log').write_text(logs.stdout+logs.stderr)
        state=json.loads(command(['docker','inspect',name,'--format','{{json .State}}'],check=True).stdout)
        row={'task':task,'exit_code':state['ExitCode'],'oom_killed':state['OOMKilled'],
             'seconds':time.monotonic()-start,'peak_gpu_mib':max((s['gpu_mib'] for s in samples if s['gpu_mib'] is not None),default=None)}
        summary['runs'].append(row);(RUN/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        command(['docker','rm','-v',name],check=True);active=None
        print(json.dumps(row),flush=True)
finally:
    if active:
        command(['docker','stop','-t','10',active]);command(['docker','rm','-v',active])
    for model in initial['models']:
        try:api('generate',{'model':model['name'],'keep_alive':-1,'stream':False,'options':{'num_ctx':model.get('context_length',32768)}})
        except Exception as exc:summary['restore_error']=str(exc)
    (RUN/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('FINISHED '+str(RUN),flush=True)
raise SystemExit(0 if len(summary['runs'])==3 and all(r['exit_code']==0 for r in summary['runs']) else 1)
