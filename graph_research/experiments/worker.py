"""Fixed protected operation for finite experiment evaluation."""
import json
import sys


def main():
    from .execution_contract import INTERNAL_OPERATION
    from .adapters import evaluate_chunk
    request=json.load(sys.stdin)
    from .search_contract import OPERATION
    if set(request)!={'name','arguments'} or request['name'] not in (INTERNAL_OPERATION,OPERATION):
        raise ValueError('Invalid fixed experiment worker request')
    if request['name']==INTERNAL_OPERATION:result=evaluate_chunk(request['arguments'])
    else:
        from .search_engine import run_round
        result=run_round(request['arguments'])
    print(json.dumps({'ok':True,'result':result,'tool_provenance':{'name':request['name'],'kind':'native_experiment'}},ensure_ascii=False,allow_nan=False))
    return 0
