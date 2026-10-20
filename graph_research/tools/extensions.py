"""Generate/test/register computational tools in a bounded Python AST subset.

Generated Python is interpreted, never passed to exec/eval/import. New packages
require host approval and implement pure JSON algorithms. Legacy manifests may
use call_tool; new-tool orchestration belongs in the outer session instead.
"""
import ast
import copy
import hashlib
import json
import math
import operator
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
import zipfile
from functools import wraps

import jsonschema


class _Return(Exception):
    def __init__(self, value): self.value = value


class RestrictedPython:
    BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
              ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
              ast.Mod: operator.mod, ast.Pow: operator.pow}
    COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
               ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
               ast.In: lambda a,b: a in b, ast.NotIn: lambda a,b: a not in b,
               ast.Is: operator.is_, ast.IsNot: operator.is_not}
    ALLOWED = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
               ast.Assign, ast.AugAssign, ast.If, ast.For, ast.While, ast.Expr,
               ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple,
               ast.Dict, ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp,
               ast.Compare, ast.BoolOp, ast.IfExp, ast.Call, ast.keyword,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
               ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq,
               ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
               ast.Pass, ast.Break, ast.Continue)

    def __init__(self, source, registry, budget=50000):
        if len(source) > 20000: raise ValueError("Generated source too large")
        self.tree = ast.parse(source)
        if len(self.tree.body) != 1 or not isinstance(self.tree.body[0], ast.FunctionDef):
            raise ValueError("Source must contain exactly def run(args)")
        function = self.tree.body[0]
        if function.name != "run" or function.decorator_list or function.returns is not None:
            raise ValueError("Expected undecorated def run(args)")
        if ([a.arg for a in function.args.args] != ["args"] or function.args.defaults
                or function.args.vararg or function.args.kwarg or function.args.kwonlyargs
                or function.args.posonlyargs or function.args.args[0].annotation):
            raise ValueError("Only one unannotated args parameter is supported")
        def bounded_range(*args):
            result = range(*args)
            if len(result) > 10000: raise ValueError("range too large")
            return list(result)
        def base_tool(name, arguments):
            if name not in registry.tools or registry.tools[name].status != "native_tested":
                raise ValueError("Generated tools may call only native catalog tools")
            return registry.call(name, arguments)
        self.functions = {"len":len,"sum":sum,"min":min,"max":max,"abs":abs,
                          "range":bounded_range,"sqrt":math.sqrt,"prod":math.prod,
                          "sorted":sorted,"int":int,"float":float,"round":round,
                          "call_tool":base_tool}
        for node in ast.walk(self.tree):
            if not isinstance(node, self.ALLOWED):
                raise ValueError(f"Unsupported generated syntax: {type(node).__name__}")
            if isinstance(node, ast.FunctionDef) and node is not function:
                raise ValueError("Nested function definitions are not supported")
            if isinstance(node, ast.Name) and node.id.startswith("_"):
                raise ValueError("Private names are not allowed")
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in self.functions):
                raise ValueError("Only documented computational helpers can be called")
        self.locals = {}
        self.budget = budget

    def tick(self, value=None):
        self.budget -= 1
        if self.budget < 0: raise RuntimeError("Generated tool exceeded instruction budget")
        if isinstance(value, (list, tuple, dict, str)) and len(value) > 10000:
            raise ValueError("Generated value too large")
        if type(value) is int and value.bit_length() > 4096:
            raise ValueError("Generated integer too large")
        if isinstance(value,float) and not math.isfinite(value):
            raise ValueError("Generated nonfinite number")
        return value

    def evaluate(self, node):
        self.tick()
        if isinstance(node, ast.Constant): return self.tick(node.value)
        if isinstance(node, ast.Name): return self.locals[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return self.tick([self.evaluate(n) for n in node.elts])
        if isinstance(node, ast.Dict): return self.tick({self.evaluate(k):self.evaluate(v) for k,v in zip(node.keys,node.values)})
        if isinstance(node, ast.Slice):
            return slice(*(self.evaluate(n) if n is not None else None for n in (node.lower,node.upper,node.step)))
        if isinstance(node, ast.Subscript): return self.evaluate(node.value)[self.evaluate(node.slice)]
        if isinstance(node, ast.BinOp):
            left, right = self.evaluate(node.left), self.evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 64: raise ValueError("Exponent too large")
            if isinstance(node.op, ast.Mult):
                if isinstance(left, (list, str)) and isinstance(right, int) and len(left)*right > 10000: raise ValueError("Sequence repetition too large")
                if isinstance(right, (list, str)) and isinstance(left, int) and len(right)*left > 10000: raise ValueError("Sequence repetition too large")
            return self.tick(self.BINARY[type(node.op)](left,right))
        if isinstance(node, ast.UnaryOp):
            value = self.evaluate(node.operand)
            return {ast.Not:operator.not_,ast.USub:operator.neg,ast.UAdd:operator.pos}[type(node.op)](value)
        if isinstance(node, ast.BoolOp):
            value = self.evaluate(node.values[0])
            for expression in node.values[1:]:
                if (isinstance(node.op,ast.And) and not value) or (isinstance(node.op,ast.Or) and value): return value
                value = self.evaluate(expression)
            return value
        if isinstance(node, ast.Compare):
            left = self.evaluate(node.left)
            for comparison, expression in zip(node.ops,node.comparators):
                right = self.evaluate(expression)
                if not self.COMPARE[type(comparison)](left,right): return False
                left = right
            return True
        if isinstance(node, ast.IfExp): return self.evaluate(node.body if self.evaluate(node.test) else node.orelse)
        if isinstance(node, ast.Call):
            return self.tick(self.functions[node.func.id](*[self.evaluate(a) for a in node.args],
                             **{kw.arg:self.evaluate(kw.value) for kw in node.keywords}))
        raise ValueError(f"Unsupported expression {type(node).__name__}")

    def assign(self, target, value):
        if isinstance(target, ast.Name):
            if target.id in self.functions: raise ValueError("Helper names cannot be overwritten")
            self.locals[target.id] = self.tick(value)
        elif isinstance(target, (ast.List,ast.Tuple)):
            if len(target.elts) != len(value): raise ValueError("Unpacking length mismatch")
            for name,item in zip(target.elts,value): self.assign(name,item)
        elif isinstance(target, ast.Subscript):
            container = self.evaluate(target.value)
            container[self.evaluate(target.slice)] = value
            self.tick(container)
        else: raise ValueError("Unsupported assignment")

    def statements(self, statements):
        for node in statements:
            self.tick()
            if isinstance(node, ast.Return): raise _Return(self.evaluate(node.value) if node.value else None)
            if isinstance(node, ast.Assign):
                value = self.evaluate(node.value)
                for target in node.targets: self.assign(target,value)
            elif isinstance(node, ast.AugAssign):
                left = self.evaluate(node.target)
                right = self.evaluate(node.value)
                if isinstance(node.op,ast.Pow) and abs(right)>64: raise ValueError("Exponent too large")
                if isinstance(node.op,ast.Mult):
                    if isinstance(left,(list,str)) and isinstance(right,int) and len(left)*right>10000: raise ValueError("Sequence too large")
                self.assign(node.target,self.tick(self.BINARY[type(node.op)](left,right)))
            elif isinstance(node, ast.If): self.statements(node.body if self.evaluate(node.test) else node.orelse)
            elif isinstance(node, (ast.For,ast.While)):
                if isinstance(node,ast.For):
                    for value in self.evaluate(node.iter):
                        self.tick(); self.assign(node.target,value); self.statements(node.body)
                else:
                    while self.evaluate(node.test): self.tick(); self.statements(node.body)
                self.statements(node.orelse)
            elif isinstance(node,ast.Expr): self.evaluate(node.value)
            elif isinstance(node,ast.Pass): pass
            else: raise ValueError("break/continue are not supported; use loop conditions")

    def run(self, arguments):
        self.locals = {"args":copy.deepcopy(arguments)}
        try: self.statements(self.tree.body[0].body)
        except _Return as result: return result.value
        return None


def close_enough(actual, expected):
    if type(expected) is bool:return type(actual) is bool and actual is expected
    if isinstance(expected, dict):
        return bool(expected) and isinstance(actual, dict) and all(k in actual and close_enough(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list): return isinstance(actual,list) and len(actual)==len(expected) and all(close_enough(a,b) for a,b in zip(actual,expected))
    if type(expected) in (int,float): return type(actual) in (int,float) and math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-10)
    return actual == expected


def isolated_evaluate(proposal, arguments, timeout=15,*,cancel=None,cancel_file=None,limits=None,include_receipt=False):
    from graph_research.runtime.guard import active
    if not active():
        from graph_research.runtime.runner import run_worker,TaskLimits
        from dataclasses import asdict
        defaults=asdict(TaskLimits(wall_seconds=timeout,cpu_seconds=15))
        if limits is not None:defaults={key:min(value,asdict(limits)[key]) for key,value in defaults.items()}
        return run_worker('extension',{'proposal':proposal,'arguments':arguments},limits=TaskLimits(**defaults),cancel=cancel,cancel_file=cancel_file,include_receipt=include_receipt)
    if include_receipt:raise PermissionError('Validation receipts require the trusted protected host entry')
    payload = json.dumps({"proposal":proposal,"arguments":arguments},allow_nan=False).encode()
    env = {key:value for key,value in os.environ.items() if not any(word in key.upper() for word in ("API_KEY","ACCESS_TOKEN","SECRET"))}
    process = subprocess.run([sys.executable,"-m","graph_research.tools.extension_worker"],input=payload,
                             capture_output=True,timeout=timeout,env=env)
    try: result = json.loads(process.stdout)
    except ValueError as exc: raise RuntimeError("Generated tool worker did not return JSON") from exc
    if not result.get("ok"): raise ValueError(result.get("error","Generated tool failed"))
    return result["result"]


def _publication_lock(function):
    @wraps(function)
    def locked(self,*args,**kwargs):
        from .change_control import InstallAuthorization
        authorization=kwargs.get('authorization',args[2] if len(args)>2 else None)
        if not isinstance(authorization,InstallAuthorization):raise PermissionError('Assess resource use and obtain host/user approval before installing an extension')
        from graph_research.runtime.storage import exclusive_lock
        with exclusive_lock(self.directory/'.library.lock'):
            from .library import ToolLibrary
            ToolLibrary(self.directory).state()
            return function(self,*args,**kwargs)
    return locked


class ToolStore:
    def __init__(self, directory,*,allow_legacy=False):
        from .change_control import external_directory
        self.directory = external_directory(directory)
        self.allow_legacy=allow_legacy;self.load_errors=[]

    @_publication_lock
    def install(self, proposal, registry, authorization=None,*,cancel=None,cancel_file=None,validation_limits=None):
        """Validate and publish one independently approved algorithm package.

        JSON/model booleans are not authorizations. New algorithms are pure
        JSON computations; existing-tool orchestration stays in the session.
        """
        from graph_research.tools.registry import Tool
        from .change_control import InstallAuthorization,core_fingerprint
        if not isinstance(authorization,InstallAuthorization):
            raise PermissionError('Assess resource use and obtain host/user approval before installing an extension')
        assessment=authorization.verify(proposal,registry)
        protected_before=core_fingerprint()
        required = {"name","description","parameters","source","tests"}
        if not isinstance(proposal,dict) or not required <= proposal.keys(): raise ValueError("Incomplete tool proposal")
        name = proposal["name"]
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,63}",name): raise ValueError("Invalid tool name")
        replacing=assessment['request'].get('replaces')
        if name in registry.tools and not replacing: raise ValueError("Cannot overwrite an existing tool")
        if not isinstance(proposal["description"],str) or not proposal["description"].strip(): raise ValueError("Tool description is required")
        encoded_schema = json.dumps(proposal["parameters"])
        if len(json.dumps(proposal)) > 100000 or any('"'+key+'"' in encoded_schema for key in ("$ref","$dynamicRef","$recursiveRef")): raise ValueError("Proposal too large or external schemas unsupported")
        jsonschema.Draft202012Validator.check_schema(proposal["parameters"])
        if proposal["parameters"].get("type") != "object": raise ValueError("Parameters must be an object schema")
        RestrictedPython(proposal["source"],registry)
        if not isinstance(proposal["tests"],list) or not 2 <= len(proposal["tests"]) <= 12: raise ValueError("At least two acceptance fixtures are required")
        receipts = []
        seen_inputs = set()
        for fixture in proposal["tests"]:
            arguments = fixture["arguments"]
            jsonschema.validate(arguments,proposal["parameters"])
            seen_inputs.add(json.dumps(arguments,sort_keys=True))
            execution = isolated_evaluate(proposal,arguments,cancel=cancel,cancel_file=cancel_file,limits=validation_limits,include_receipt=True)
            actual=execution['result']
            if not close_enough(actual,fixture["expected"]): raise ArithmeticError("Generated tool failed acceptance fixture")
            from graph_research.runtime.storage import read_json,safe_path
            receipt,_=read_json(safe_path(Path(execution['execution']['directory'])/'execution.json'),max_bytes=1024*1024)
            evidence={key:receipt[key] for key in ('protection','environment','core_manifest_sha256','request_sha256','result_sha256','limits')}
            evidence['receipt_sha256']=execution['execution']['receipt_sha256']
            receipts.append({"arguments":arguments,"expected":fixture["expected"],"actual":actual,"passed":True,'execution_evidence':evidence})
        if len(seen_inputs) < 2: raise ValueError("Acceptance fixtures must use distinct inputs")
        record = {**proposal,"status":"fixture_tested_experimental",
                  "source_sha256":hashlib.sha256(proposal["source"].encode()).hexdigest(),"test_results":receipts,
                  "validation_scope":"Passed these fixtures only; not a proof of general mathematical correctness"}
        record['assessment_id']=assessment['id']
        record['approval_scope_sha256']=assessment['scope_sha256']
        record['approved_new_algorithm']=True
        record['validation_format']='protected-fixtures/1'
        from .library import ToolLibrary,package_id,metadata
        record['library_metadata']=metadata(assessment['request'].get('library_metadata'))
        record['replaces']=replacing
        version=package_id(record)
        if len(json.dumps(record,ensure_ascii=False).encode())>200000:raise ValueError('Extension with actual validation evidence exceeds200KB; request smaller reviewable fixtures')
        destination = ((self.directory/'.versions'/version[:24]) if replacing else (self.directory/name)).resolve()
        archive=destination.with_suffix('.zip')
        stage=(self.directory/'.staging'/uuid.uuid4().hex).resolve()
        if not destination.is_relative_to(self.directory) or not stage.is_relative_to(self.directory):
            raise ValueError('Extension publication paths must stay inside their store')
        if destination.exists() or archive.exists():raise FileExistsError('Existing extension packages cannot be overwritten')
        stage.mkdir(parents=True,exist_ok=False)
        (stage/"tool.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
        (stage/"tool.py").write_text(proposal["source"],encoding="utf-8")
        (stage/'assessment.json').write_text(json.dumps(assessment,ensure_ascii=False,indent=2),encoding='utf-8')
        approval=authorization.controller._approved(assessment['id'])[1]
        (stage/'approval.json').write_text(json.dumps(approval,ensure_ascii=False,indent=2),encoding='utf-8')
        (stage/'tests.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
        (stage/'README.md').write_text(f"# {name}\n\n{proposal['description']}\n\n仅通过所列验收样例，状态为实验性。\n\n需求：{assessment['request']['requirements']}\n\n纯JSON算法；复用原工具由外层会话编排。\n",encoding='utf-8')
        if core_fingerprint()!=protected_before:
            raise RuntimeError('Original package changed during validation; extension was not published')
        # Both resolved paths were checked above; this move is confined to the
        # externally supplied extension store, never the original package.
        if (cancel is not None and cancel.is_set()) or (cancel_file is not None and Path(cancel_file).exists()):raise InterruptedError('Cancelled before extension publication')
        destination.parent.mkdir(parents=True,exist_ok=True);stage.rename(destination)
        from .change_control import digest
        publication={'source_sha256':record['source_sha256'],'assessment_id':assessment['id'],'record_sha256':digest(record)}
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as bundle:
            for file in sorted(destination.iterdir()):bundle.write(file,name+'/'+file.name)
            # Transport bundles deliberately omit the local ready marker.
            # Importing into another store requires a new host approval.
        if replacing:registry.tools.pop(name,None)
        self._register(record,registry)
        result={"name":name,"status":record["status"],"tests_passed":len(receipts),"path":str(destination),
                "archive":str(archive),'core_unchanged':core_fingerprint()==protected_before,'assessment_id':assessment['id'],'package_id':version}
        authorization.complete(result)
        (destination/'ready.json').write_text(json.dumps(publication),encoding='utf-8')
        ToolLibrary(self.directory)._select(name,version)
        return result

    def _register(self, record, registry):
        from graph_research.tools.registry import Tool
        if hashlib.sha256(record["source"].encode()).hexdigest() != record["source_sha256"]: raise ValueError("Tool source checksum changed")
        runner=RestrictedPython(record["source"],registry)
        if record.get('approved_new_algorithm') and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='call_tool' for n in ast.walk(runner.tree)):
            raise ValueError('New algorithm packages cannot contain tool orchestration')
        def run(**arguments): return isolated_evaluate(record,arguments)
        documentation = {"source_sha256":record['source_sha256'],
                         "examples":[{"arguments":fixture['arguments'],"expected":fixture['expected']} for fixture in record['tests']],
                         "validation_scope":record.get('validation_scope','Passed listed acceptance fixtures only'),
                         "approval_status":"approved_new_algorithm" if record.get('approved_new_algorithm') else 'legacy_unreviewed'}
        from .library import metadata,package_id
        details=metadata(record.get('library_metadata'))
        documentation.update(details,package_id=package_id(record))
        registry.register(Tool(record["name"],record["description"],record["parameters"],run,record["status"],documentation))

    def load_into(self, registry):
        self.load_errors=[]
        if self.directory.exists():
            from .library import ToolLibrary
            try:rows,self.load_errors=ToolLibrary(self.directory).selected()
            except (OSError,ValueError,KeyError,TypeError) as exc:
                self.load_errors=[{'package':'library','error':str(exc)[:512],'action':'quarantined'}];return self.load_errors
            for index,row in enumerate(rows):
                manifest=row['path']
                if index>=128:
                    self.load_errors.append({'package':'remaining_packages','error':'Extension count exceeds128; remaining packages disabled','action':'quarantined'});break
                try:self._load_manifest(manifest,registry)
                except (OSError,ValueError,KeyError,TypeError,SyntaxError) as exc:
                    self.load_errors.append({'package':manifest.parent.name,'error':(type(exc).__name__+': '+str(exc))[:512],'action':'quarantined'})
        return self.load_errors

    def _load_manifest(self,manifest,registry):
        from graph_research.runtime.storage import safe_path
        safe_path(manifest,root=self.directory)
        if manifest.stat().st_size>200000:raise ValueError('Extension manifest exceeds200KB')
        record=json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(record,dict):raise ValueError('Extension manifest must be an object')
        if not record.get('approved_new_algorithm') and not self.allow_legacy:
            self.load_errors.append({'package':manifest.parent.name,'error':'Legacy package needs independent review before enabling','action':'disabled_legacy'})
            return
        self._load_validated(manifest,registry)

    def _load_validated(self,manifest,registry):
        from graph_research.runtime.storage import safe_path
        record=json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(record,dict):raise ValueError('Extension manifest must be an object')
        for filename in ('ready.json','assessment.json','approval.json','tool.py','tests.json'):
            candidate=safe_path(manifest.parent/filename,root=self.directory)
            if candidate.exists() and candidate.stat().st_size>200000:raise ValueError('Extension audit/source file too large')
        if record.get('approved_new_algorithm'):
            from .change_control import digest
            ready=safe_path(manifest.parent/'ready.json',root=self.directory)
            if not ready.is_file():return
            marker=json.loads(ready.read_text(encoding='utf-8'))
            if not isinstance(marker,dict):raise ValueError('Extension ready marker must be an object')
            if marker.get('source_sha256')!=record.get('source_sha256') or marker.get('assessment_id')!=record.get('assessment_id'):
                raise ValueError('Extension publication marker does not match its source')
            if marker.get('record_sha256') is not None and marker['record_sha256']!=digest(record):raise ValueError('Extension published record changed')
            assessment=json.loads(safe_path(manifest.parent/'assessment.json',root=self.directory).read_text(encoding='utf-8'))
            approval=json.loads(safe_path(manifest.parent/'approval.json',root=self.directory).read_text(encoding='utf-8'))
            if not isinstance(assessment,dict) or not isinstance(assessment.get('request'),dict) or not isinstance(approval,dict):raise ValueError('Invalid extension approval audit')
            if approval.get('decision')!='approved' or approval.get('assessment_sha256')!=digest(assessment) or record.get('approval_scope_sha256')!=assessment.get('scope_sha256'):
                raise ValueError('Extension approval audit does not match its assessed scope')
            expected=[{'arguments':case['arguments'],'expected':case['expected']} for case in assessment['request']['acceptance_tests']]
            if record['name']!=assessment['request']['name'] or digest(record['parameters'])!=digest(assessment['request']['parameters']) or digest(record['tests'])!=digest(expected):
                raise ValueError('Extension interface/tests differ from the approved scope')
            if digest(record.get('library_metadata',{}))!=digest(assessment['request'].get('library_metadata',{})):raise ValueError('Extension documentation differs from approved scope')
            if record.get('validation_format')=='protected-fixtures/1':
                results=json.loads(safe_path(manifest.parent/'tests.json',root=self.directory).read_text(encoding='utf-8'))
                if not isinstance(results,list) or any(not isinstance(row,dict) for row in results) or digest(results)!=digest(record.get('test_results')) or len(results)!=len(expected):raise ValueError('Extension validation evidence changed')
                for actual,wanted in zip(results,expected):
                    if actual.get('passed') is not True or digest(actual.get('arguments'))!=digest(wanted['arguments']) or digest(actual.get('expected'))!=digest(wanted['expected']) or not close_enough(actual.get('actual'),wanted['expected']):raise ValueError('Extension fixture result does not match approved tests')
                    proof=actual.get('execution_evidence',{})
                    if proof.get('protection')!='windows_low_integrity_and_job' or not re.fullmatch(r'[0-9a-f]{64}',proof.get('receipt_sha256','')):raise ValueError('Extension lacks protected fixture evidence')
            if safe_path(manifest.parent/'tool.py',root=self.directory).read_text(encoding='utf-8')!=record['source']:
                raise ValueError('Extension source file differs from its approved manifest')
        if record.get('status')=='fixture_tested_experimental':
            existing=registry.tools.get(record['name'])
            if existing is not None:
                if (existing.documentation or {}).get('source_sha256')==record['source_sha256']:return
                raise ValueError('Existing tool cannot be replaced while loading extensions')
            self._register(record,registry)
