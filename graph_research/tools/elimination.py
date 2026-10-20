"""Bound exact elimination in a native Python subprocess, never in Sage."""
import json
import os
import subprocess
import sys


def run_elimination(request,timeout=20):
    from graph_research.runtime.guard import active
    if not active():
        from graph_research.runtime.runner import run_worker,TaskLimits
        try:return run_worker('elimination',request,limits=TaskLimits(wall_seconds=timeout,cpu_seconds=20))
        except TimeoutError as exc:raise RuntimeError(f'Exact elimination exceeded {timeout}s; no partial polynomial was accepted') from exc
    env={k:v for k,v in os.environ.items() if not any(word in k.upper() for word in ("API_KEY","ACCESS_TOKEN","SECRET"))}
    try:
        process=subprocess.run([sys.executable,"-m","graph_research.tools.elimination_worker"],
                    input=json.dumps(request,allow_nan=False).encode(),capture_output=True,
                    timeout=timeout,env=env)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Exact elimination exceeded {timeout}s; no partial polynomial was accepted") from exc
    try: payload=json.loads(process.stdout)
    except ValueError as exc: raise RuntimeError("Elimination worker did not return a valid result") from exc
    if not payload.get("ok"): raise RuntimeError(payload.get("error","Exact elimination failed"))
    return payload["result"]


def hypergraph_tensor_charpoly(edges,n=None,rank=None,matrix="A",alpha=0,symbolic_alpha=False,
                              weights=None,vertex_degrees=None,estimate_only=False):
    if n is not None and not 1<=n<=32: raise ValueError("Model tool dimension must be in[1,32]")
    if symbolic_alpha and matrix!="alpha": raise ValueError("symbolic_alpha requires matrix='alpha'")
    return run_elimination({"mode":"hypergraph","edges":edges,"n":n,"rank":rank,"matrix":matrix,
                            "alpha":alpha,"symbolic_alpha":symbolic_alpha,"weights":weights,
                            "vertex_degrees":vertex_degrees,"estimate_only":estimate_only})


def tensor_charpoly(data,estimate_only=False):
    return run_elimination({"mode":"tensor","data":data,"estimate_only":estimate_only})


def elimination_tool_definitions(obj):
    scalar={"anyOf":[{"type":"number"},{"type":"string","pattern":r"^[+-]?(?:[0-9]+/[0-9]+|[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)$","maxLength":128}]}
    return [
      ("hypergraph_tensor_charpoly","精确Macaulay消元计算一般k一致超图A/L/Q/alpha张量特征多项式，保留代数重数；不等于匹配或E特征多项式。支持孤立点、精确分数和符号alpha。默认Macaulay阶<=4096、SCC块<=256；符号alpha限512/64，硬超时20秒。estimate_only只估算。",hypergraph_tensor_charpoly,
       obj({"edges":{"type":"array","items":{"type":"array","items":{"type":"integer","minimum":0,"maximum":31},"minItems":2,"maxItems":5},"maxItems":64},
            "n":{"type":"integer","minimum":1,"maximum":32},"rank":{"type":"integer","minimum":2,"maximum":5},
            "matrix":{"enum":["A","L","Q","alpha"]},"alpha":scalar,"symbolic_alpha":{"type":"boolean"},
            "weights":{"type":"array","items":scalar,"maxItems":64},"vertex_degrees":{"type":"array","items":scalar,"maxItems":32},
            "estimate_only":{"type":"boolean"}},["edges"])),
      ("tensor_charpoly","精确计算小规模立方张量的普通特征多项式，允许非对称/负系数。数据可用分数字符串；浮点按十进制精确有理数解释。不是E特征多项式。estimate_only只估算。",tensor_charpoly,
       obj({"data":{"type":"array","minItems":1,"maxItems":8},"estimate_only":{"type":"boolean"}},["data"]))
    ]
