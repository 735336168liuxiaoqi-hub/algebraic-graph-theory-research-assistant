import json
import sys
from graph_research.tools.extensions import RestrictedPython
from graph_research.tools.registry import ToolRegistry, json_value


def main():
    try:
        request = json.load(sys.stdin)
        result = RestrictedPython(request["proposal"]["source"],ToolRegistry()).run(request["arguments"])
        value = json.dumps({"ok":True,"result":json_value(result)},allow_nan=False)
        if len(value) > 100000: raise ValueError("Generated output too large")
        print(value)
    except Exception as exc:
        print(json.dumps({"ok":False,"error":f"{type(exc).__name__}: {exc}"}))
        return 1
    return 0


if __name__ == "__main__": sys.exit(main())
