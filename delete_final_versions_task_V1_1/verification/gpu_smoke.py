"""Three real GPU container calls; preserve evidence and restore Ollama residency."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'delete_final_versions_task_V1_1/verification' / ('gpu_smoke_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
RUN.mkdir(parents=True)
IMAGE = 'chimera_agent_baseline_debug'

def command(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)

def api(route, data=None):
    request = urllib.request.Request('http://localhost:11434/api/' + route,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)

initial = api('ps')
(RUN/'ollama_before.json').write_text(json.dumps(initial, indent=2))
summary = {'image': command(['docker','image','inspect',IMAGE,'--format','{{.Id}}']).stdout.strip(),
           'run_dir': str(RUN), 'cases': []}
print('RUN_DIR=' + str(RUN), flush=True)
active = None
try:
    for model in initial['models']:
        command(['ollama','stop',model['name']], check=True)
    time.sleep(3)
    print(command(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free','--format=csv']).stdout, flush=True)
    for interface in map(int, os.environ.get('CHIMERA_SMOKE_INTERFACES', '0,1,2').split(',')):
        name = f'chimera-smoke-{RUN.name}-{interface}'
        folder = RUN/f'interf{interface}'
        output = folder/'output'
        output.mkdir(parents=True)
        output.chmod(0o777)
        args = ['docker','run','-d','--name',name,'--gpus','device=0','--network','none',
                '--platform=linux/amd64','--memory=32g','--memory-swap=32g',
                '-e','CHIMERA_SLUG_STRICT=canonical',
                '-e','CHIMERA_GPU_MEMORY_UTILIZATION=0.8',
                '-e','CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=100',
                '-v',f"{os.environ.get('CHIMERA_SMOKE_SOURCE', ROOT/'delete_final_versions_task_V1_1')}:/opt/app/delete_final_versions_task_V1_1:ro",
                # Junto al entrypoint real, no encima: montarlo sobre inference.py haría
                # que el envoltorio se importase a sí mismo.
                '-v',f'{ROOT}/delete_final_versions_task_V1_1/verification/inference_v1_1.py:/opt/app/inference_v1_1.py:ro',
                '--entrypoint','python3',
                '-v',f'{ROOT}/test/input/interf{interface}:/input:ro',
                '-v',f'{output}:/output','-v',f'{ROOT}/model:/opt/ml/model:ro',
                '--mount','type=volume,destination=/tmp',IMAGE,'inference_v1_1.py']
        (folder/'command.json').write_text(json.dumps(args,indent=2))
        start = time.monotonic()
        command(args, check=True)
        active = name
        timed_out = False
        samples = []
        print(f'START interf{interface}', flush=True)
        while True:
            state = json.loads(command(['docker','inspect',name,'--format','{{json .State}}'],check=True).stdout)
            if not state['Running']:
                break
            gpu = command(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits']).stdout.strip()
            stats = command(['docker','stats','--no-stream','--format','{{json .}}',name]).stdout.strip()
            samples.append({'elapsed_s':round(time.monotonic()-start,2),'gpu_used_mib_util_percent':gpu,
                            'docker':json.loads(stats) if stats else {}})
            (folder/'metrics.json').write_text(json.dumps(samples,indent=2))
            if time.monotonic()-start > 900:
                timed_out = True
                command(['docker','stop','-t','10',name])
                continue
            time.sleep(5)
        logs = command(['docker','logs',name])
        (folder/'container.log').write_text(logs.stdout + logs.stderr)
        (folder/'state.json').write_text(json.dumps(state,indent=2))
        row = {'interface':interface,'seconds':round(time.monotonic()-start,2),
               'exit_code':state['ExitCode'],'oom_killed':state['OOMKilled'],'timed_out':timed_out,
               'dispatch_fallback':'writing fallback' in (logs.stdout+logs.stderr),
               'files':sorted(p.name for p in output.iterdir()),
               'peak_gpu_used_mib':max((int(s['gpu_used_mib_util_percent'].split(',')[0]) for s in samples),default=None)}
        summary['cases'].append(row)
        (RUN/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(row), flush=True)
        command(['docker','rm','-v',name],check=True)
        active = None
finally:
    if active:
        command(['docker','stop','-t','10',active])
        command(['docker','rm','-v',active])
    restored = []
    for model in initial['models']:
        try:
            api('generate', {'model':model['name'],'keep_alive':-1,'stream':False,
                             'options':{'num_ctx':model.get('context_length',32768)}})
            restored.append(model['name'])
        except Exception as exc:
            summary['ollama_restore_error'] = str(exc)
    summary['ollama_restored'] = restored
    (RUN/'summary.json').write_text(json.dumps(summary,indent=2))
    print('FINISHED ' + str(RUN), flush=True)
