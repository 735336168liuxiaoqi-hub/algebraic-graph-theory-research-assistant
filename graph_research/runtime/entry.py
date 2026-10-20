"""Trusted child bootstrap: fixed worker modes, complete bounded JSON result."""
import contextlib
import io
import json
from pathlib import Path
import sys
import time
from .observability import Timings,recording,measure,annotate,diagnostic_id as new_id


def main(*,diagnostic_id=None,bootstrap_started=None):
    timings=Timings();identifier=new_id(diagnostic_id)
    if type(bootstrap_started) in (int,float) and 0<=bootstrap_started<=timings.started:
        duration=timings.started-bootstrap_started;timings.started=bootstrap_started
        timings.stages['worker.entry_import']={'seconds':duration,'exclusive_seconds':duration,'calls':1}
    with recording(timings,identifier):return _main(timings,identifier)


def _main(timings,identifier):
    kind,request_file,result_file=sys.argv[1:]
    root=Path(request_file).parent
    from .storage import atomic_text
    def phase(name,**extra):
        # Diagnostic-only: an antivirus scanner may briefly remove the staged
        # temp file even after atomic retries. Losing a status line must never
        # kill a computation whose result contract is result.json.
        try:atomic_text(root/'startup-status.json',json.dumps({'phase':name,'diagnostic_id':identifier,'timings':timings.snapshot(),**extra}),overwrite=True)
        except OSError:pass
    phase('python_entry')
    try:
        with measure('worker.guard_setup'):
            from .guard import install
            install(root)
            sys.stdout=open(root/'stdout.log','w',encoding='utf-8')
            sys.stderr=open(root/'stderr.log','w',encoding='utf-8')
        phase('guard_ready')
        from .integrity import assert_integrity
        with measure('worker.integrity'):assert_integrity()
        with measure('worker.request_read'):request=json.loads(Path(request_file).read_text(encoding='utf-8'))
        provenance=None
        phase('dispatch',kind=kind)
        if kind=='probe':
            with measure('worker.dispatch_import'):
                from .probe import execute
            with measure('tool_function'):result=execute(request)
        else:
            module={'tool':'graph_research.tools.worker','extension':'graph_research.tools.extension_worker','elimination':'graph_research.tools.elimination_worker'}[kind]
            from importlib import import_module
            with measure('worker.dispatch_import'):worker=import_module(module)
            buffer=io.StringIO()
            sys.stdin=io.StringIO(json.dumps(request))
            with contextlib.redirect_stdout(buffer):code=worker.main()
            payload=json.loads(buffer.getvalue())
            if code or not payload.get('ok'):
                # The worker already reported a structured error; pass it
                # through unchanged instead of re-prefixing it per layer.
                encoded=json.dumps({'ok':False,'error':payload.get('error','Calculation failed'),
                                    'diagnostics':{'diagnostic_id':identifier,'timings':timings.snapshot()}},ensure_ascii=False)
                phase('result_publication')
                with measure('worker.result_publication'):atomic_text(result_file,encoded)
                phase('result_published')
                return
            result=payload['result']
            provenance=payload.get('tool_provenance')
        with measure('worker.result_serialization'):
            encoded=json.dumps({'ok':True,'result':result,'tool_provenance':provenance,
                                'diagnostics':{'diagnostic_id':identifier,'timings':timings.snapshot()}},ensure_ascii=False,allow_nan=False)
        if len(encoded.encode('utf-8'))>4*1024*1024:raise ValueError('Worker result exceeds 4MB')
    except Exception as exc:
        phase('worker_error',error=type(exc).__name__+': '+str(exc))
        detail=annotate(exc,identifier=identifier)
        encoded=json.dumps({'ok':False,'error':{'type':type(exc).__name__,'message':str(exc),**detail},
                            'diagnostics':{'diagnostic_id':identifier,'timings':timings.snapshot()}},ensure_ascii=False)
    phase('result_publication')
    with measure('worker.result_publication'):atomic_text(result_file,encoded)
    phase('result_published')


if __name__=='__main__':main()
