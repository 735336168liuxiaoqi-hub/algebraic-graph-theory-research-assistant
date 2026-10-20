"""Bound native and experimental model-selected tool execution in a process."""
import json
import sys
from graph_research.tools.registry import ToolRegistry
from graph_research.tools.extensions import ToolStore
from graph_research.runtime.observability import measure,annotate


def main():
    try:
        request=json.load(sys.stdin)
        with measure('worker.registry'):registry=ToolRegistry()
        with measure('worker.extension_discovery'):ToolStore(request["tool_directory"]).load_into(registry)
        tool=registry.tools.get(request['name'])
        if request.get('expected_tool'):
            expected=request['expected_tool'];doc=tool.documentation if tool else {}
            if not doc or any(doc.get(key)!=value for key,value in expected.items()):raise ValueError('Extension version changed before execution; inspect the current tool contract again')
        if request.get('graph_inputs'):
            from graph_research.graph_input.adapters import validate_sources
            validate_sources(registry.describe(request['name']),request['arguments'],request['graph_inputs'])
        if request.get('research_refs'):
            from graph_research.assistant.research_objects import validate_execution_refs
            validate_execution_refs(request['research_refs'],request.get('graph_inputs'))
        with measure('worker.tool_dispatch'):result=registry.call(request["name"],request["arguments"])
        tool=registry.tools[request['name']]
        provenance={'name':tool.name,'status':tool.status,'source_sha256':(tool.documentation or {}).get('source_sha256'),'package_id':(tool.documentation or {}).get('package_id')}
        print(json.dumps({"ok":True,"result":result,'tool_provenance':provenance},allow_nan=False))
    except Exception as exc:
        # Structured once here; entry/runner pass it through without re-prefixing.
        error={'type':type(exc).__name__,'message':str(exc),**annotate(exc)}
        if getattr(exc,'code',None) is not None:error['code']=exc.code
        print(json.dumps({"ok":False,"error":error}))
        return 1
    return 0


if __name__=="__main__": sys.exit(main())
