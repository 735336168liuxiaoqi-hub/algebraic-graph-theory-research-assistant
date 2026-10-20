"""Host-owned assessment/approval records; no approval is accepted from a model."""
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from functools import wraps
from graph_research.runtime.storage import safe_path,write_json,exclusive_lock

import jsonschema


CORE=Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def core_fingerprint():
    """Ignore Python bytecode caches, protect shipped code AND resource data."""
    return digest({str(p.relative_to(CORE)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(CORE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'})


def external_directory(path):
    original=Path(path);resolved=original.resolve()
    if resolved==CORE or resolved.is_relative_to(CORE):
        raise ValueError('Extension/session directories must be outside the original package')
    return safe_path(original)


def _locked(fn):
    @wraps(fn)
    def wrapped(self,*args,**kwargs):
        with exclusive_lock(self.directory/'.approval.lock'):return fn(self,*args,**kwargs)
    return wrapped


def catalog_fingerprint(registry):
    return digest([{**{k:t.definition()[k] for k in ('name','description','parameters','status')},
                    'package_id':(t.documentation or {}).get('package_id'),'source_sha256':(t.documentation or {}).get('source_sha256')} for t in registry.tools.values()])


def estimate_consumption(request,registry,pricing=None,context_bytes=0):
    """Local heuristic ranges, NOT measured usage, a price quote or a proof."""
    calls=4 if request['complexity']=='small' else 6
    fixtures=len(request['acceptance_tests'])
    prompt_bytes=len(json.dumps(registry.catalog(detail='model'),ensure_ascii=False).encode())+len(json.dumps(request,ensure_ascii=False).encode())+context_bytes
    per_call=max(2000,math.ceil(prompt_bytes/3))
    inputs=[per_call*2,per_call*calls*2]
    outputs=[1500,12000 if calls==4 else 20000]
    seconds=[30,90*calls+15*fixtures*2+120]
    money=None
    if pricing is not None:
        rates=[pricing.get('input_per_million'),pricing.get('output_per_million')]
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in rates):
            raise ValueError('Pricing must provide finite nonnegative input/output rates')
        money={'currency':str(pricing.get('currency','unspecified')),
               'range':[round((inputs[i]*rates[0]+outputs[i]*rates[1])/1_000_000,6) for i in (0,1)],
               'basis':'User-configured rates; provider invoice may differ'}
    return {'kind':'heuristic_not_measured','scope':'Future work after approval; excludes the clarification/assessment already performed',
            'input_tokens_range':inputs,'output_tokens_range':outputs,'wall_seconds_range':seconds,
            'money':money,'money_note':'未配置模型单价时不估算金额；token与时间为启发式范围，不是服务商账单保证。',
            'limits':{'model_calls':calls,'implementation_attempts':2,'fixture_count':fixtures,
                      'fixture_timeout_seconds':15,'instruction_budget_per_run':50000,'max_source_characters':20000}}


@dataclass(frozen=True)
class InstallAuthorization:
    """Only obtained from host approval; never serialized into model context."""
    controller: object
    assessment_id: str
    reservation_id: str | None = None

    def verify(self,proposal,registry):
        return self.controller.verify_install(self.assessment_id,proposal,registry,reservation_id=self.reservation_id)

    def complete(self,result):
        self.controller.complete(self.assessment_id,result)


class ChangeController:
    def __init__(self,directory,pricing=None):
        self.directory=external_directory(directory)
        self.pricing=pricing

    def _path(self,assessment_id):
        if not isinstance(assessment_id,str) or not re.fullmatch(r'[0-9a-f]{32}',assessment_id):
            raise ValueError('Invalid assessment ID')
        path=(self.directory/assessment_id).resolve()
        if not path.is_relative_to(self.directory):raise ValueError('Assessment path escaped its directory')
        return path

    def _write(self,path,data):
        write_json(path,data)

    def read(self,assessment_id):
        return json.loads((self._path(assessment_id)/'assessment.json').read_text(encoding='utf-8'))

    def assess(self,request,registry,context_bytes=0):
        if not isinstance(request,dict) or 'source' in request:
            raise ValueError('Assessment must describe requirements before code generation')
        if request.get('composition_possible') is True:
            return {'kind':'composition','message':'现有工具联动即可完成，不创建扩展包；请继续调用现有工具。'}
        required={'name','goal','requirements','checked_tools','why_not_composition','new_algorithm','parameters','acceptance_tests','complexity','composition_possible'}
        if not required<=request.keys():raise ValueError('Assessment lacks required scope/gap/test fields')
        if type(request['composition_possible']) is not bool:raise ValueError('composition_possible must be boolean')
        if not re.fullmatch(r'[a-z][a-z0-9_]{2,63}',str(request['name'])):
            raise ValueError('Extension name is invalid or already registered')
        from .library import metadata
        metadata(request.get('library_metadata'))
        existing=registry.tools.get(request['name']);replaces=request.get('replaces')
        if existing:
            if existing.status=='native_tested' or not replaces or replaces!=(existing.documentation or {}).get('package_id'):raise ValueError('Existing tool requires an explicit current package_id to create an independent new version')
        elif replaces:raise ValueError('Upgrade target is not currently enabled')
        if request['complexity'] not in ('small','medium'):raise ValueError('Automatic extension currently supports small/medium restricted algorithms only')
        for key in ('goal','requirements','why_not_composition','new_algorithm'):
            if not isinstance(request[key],str) or not request[key].strip():raise ValueError(f'{key} must explain the requested scope')
        checked=request['checked_tools']
        if not isinstance(checked,list) or not checked or any(not isinstance(t,dict) or t.get('tool') not in registry.tools or not isinstance(t.get('reason'),str) or not t['reason'].strip() for t in checked):
            raise ValueError('List existing tools checked and explain each capability gap')
        schema=request['parameters']
        if not isinstance(schema,dict):raise ValueError('Extension input schema must be an object schema')
        encoded=json.dumps(schema)
        if len(json.dumps(request))>100000 or any('"'+k+'"' in encoded for k in ('$ref','$dynamicRef','$recursiveRef')):
            raise ValueError('Assessment too large or external schemas unsupported')
        jsonschema.Draft202012Validator.check_schema(schema)
        if schema.get('type')!='object':raise ValueError('Extension input schema must be an object')
        fixtures=request['acceptance_tests']
        if not isinstance(fixtures,list) or not 2<=len(fixtures)<=12:raise ValueError('Need2..12 acceptance fixtures before approval')
        for case in fixtures:
            if not isinstance(case,dict) or not {'arguments','expected','basis'}<=case.keys() or not isinstance(case['basis'],str) or not case['basis'].strip():
                raise ValueError('Every acceptance fixture needs arguments, expected and an independently reviewable basis')
            jsonschema.validate(case['arguments'],schema)
        if len({digest(f['arguments']) for f in fixtures})<2:raise ValueError('Fixtures must use distinct inputs')
        assessment_id=uuid.uuid4().hex
        if type(context_bytes) is not int or context_bytes<0:raise ValueError('Invalid assessment context size')
        record={'id':assessment_id,'kind':'new_algorithm','request':request,'estimate':estimate_consumption(request,registry,self.pricing,context_bytes),
                'core_sha256':core_fingerprint(),'catalog_sha256':catalog_fingerprint(registry),
                'scope_sha256':digest(request),'created_at':datetime.now(timezone.utc).isoformat(),
                'caveat':'工具缺口与可行性为待人工确认的分析；验收样例不构成一般数学正确性证明。'}
        self._write(self._path(assessment_id)/'assessment.json',record)
        return record

    @_locked
    def approve(self,assessment_id,registry):
        """Host/UI/CLI action only. Do not expose this method as a model tool."""
        record=self.read(assessment_id)
        if digest(record['request'])!=record['scope_sha256']:raise ValueError('Assessment scope was modified')
        if record['core_sha256']!=core_fingerprint() or record['catalog_sha256']!=catalog_fingerprint(registry):
            raise ValueError('Package/catalog changed; reassess before approving')
        path=self._path(assessment_id)/'approval.json'
        if path.exists():raise ValueError('Assessment already has an approval decision; create a new assessment')
        receipt={'assessment_id':assessment_id,'assessment_sha256':digest(record),'decision':'approved',
                 'confirmed_at':datetime.now(timezone.utc).isoformat(),'model_calls_used':0,'implementation_attempts':0,'consumed':False}
        self._write(path,receipt)
        return InstallAuthorization(self,assessment_id)

    @_locked
    def reject(self,assessment_id,reason='User declined'):
        self.read(assessment_id)
        path=self._path(assessment_id)/'approval.json'
        if path.exists():raise ValueError('Approval already decided')
        self._write(path,{'assessment_id':assessment_id,'decision':'rejected','reason':str(reason)})

    def _approved(self,assessment_id):
        record=self.read(assessment_id)
        path=self._path(assessment_id)/'approval.json'
        if not path.is_file():raise PermissionError('Human approval is required')
        receipt=json.loads(path.read_text(encoding='utf-8'))
        if receipt.get('decision')!='approved' or receipt.get('assessment_sha256')!=digest(record) or digest(record['request'])!=record['scope_sha256']:
            raise PermissionError('Approval is rejected, stale or bound to another scope')
        return record,receipt

    def authorize(self,assessment_id):
        self._approved(assessment_id)
        return InstallAuthorization(self,assessment_id)

    @_locked
    def consume_model_call(self,assessment_id):
        record,receipt=self._approved(assessment_id)
        limit=record['estimate']['limits']['model_calls']
        if receipt['model_calls_used']>=limit:raise RuntimeError('Approved follow-up model-call budget exhausted; request a new assessment')
        receipt['model_calls_used']+=1
        self._write(self._path(assessment_id)/'approval.json',receipt)

    @_locked
    def verify_install(self,assessment_id,proposal,registry,*,reservation_id=None,reserve_only=False):
        import ast
        record,receipt=self._approved(assessment_id)
        if receipt.get('consumed'):raise PermissionError('Approval has already installed one package')
        if record['core_sha256']!=core_fingerprint() or record['catalog_sha256']!=catalog_fingerprint(registry):
            raise PermissionError('Core/catalog changed after assessment; reassessment is required')
        request=record['request']
        if proposal.get('name')!=request['name'] or digest(proposal.get('parameters'))!=digest(request['parameters']):
            raise PermissionError('Generated package differs from the approved name/input scope')
        expected=[{'arguments':f['arguments'],'expected':f['expected']} for f in request['acceptance_tests']]
        actual=[{'arguments':f['arguments'],'expected':f['expected']} for f in proposal.get('tests',[])]
        if digest(actual)!=digest(expected):raise PermissionError('Generated tests differ from the approved acceptance fixtures')
        if not isinstance(proposal.get('source'),str) or len(proposal['source'])>record['estimate']['limits']['max_source_characters']:
            raise ValueError('Generated source exceeds the approved size budget')
        # Reuse belongs in the outer workflow. A package is a new pure algorithm,
        # not a saved wrapper around call_tool, even if it hides calls in loops.
        if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='call_tool' for n in ast.walk(ast.parse(proposal.get('source','')))):
            raise ValueError('Tool composition must stay in the workflow; new packages accept prepared JSON data and cannot call_tool')
        if reservation_id is not None:
            if not re.fullmatch(r'[0-9a-f]{32}',reservation_id):raise ValueError('Invalid implementation reservation')
            reservations=receipt.setdefault('implementation_reservations',{})
            reservation=reservations.get(reservation_id)
            if reservation is not None:
                if reserve_only or reservation['status']!='reserved' or reservation['proposal_sha256']!=digest(proposal):raise PermissionError('Implementation reservation already consumed or changed')
                reservation['status']='executing'
                self._write(self._path(assessment_id)/'approval.json',receipt);return record
            if not reserve_only:raise PermissionError('No reserved implementation attempt')
        if receipt['implementation_attempts']>=record['estimate']['limits']['implementation_attempts']:
            raise RuntimeError('Approved implementation attempt budget exhausted')
        receipt['implementation_attempts']+=1
        if reservation_id is not None:reservations[reservation_id]={'status':'reserved','proposal_sha256':digest(proposal)}
        self._write(self._path(assessment_id)/'approval.json',receipt)
        return record

    @_locked
    def complete(self,assessment_id,result):
        _,receipt=self._approved(assessment_id)
        receipt['consumed']=True;receipt['result']=result
        self._write(self._path(assessment_id)/'approval.json',receipt)

    def approval_card(self,assessment):
        r=assessment['request'];e=assessment['estimate']
        money='未配置单价，金额未知' if e['money'] is None else str(e['money']['range'])+' '+e['money']['currency']
        return (f"拟新增：{r['name']}\n需求：{r['requirements']}\n现有工具不足：{r['why_not_composition']}\n"
                f"新增算法：{r['new_algorithm']}\n预计后续模型调用最多{e['limits']['model_calls']}次；"
                f"输入token约{e['input_tokens_range']}，输出约{e['output_tokens_range']}；"
                f"时间约{e['wall_seconds_range'][0]}–{e['wall_seconds_range'][1]}秒；费用：{money}。\n"
                f"验收样例{len(r['acceptance_tests'])}项；独立封包，不修改核心包。上述为估计，不保证数学可解或账单准确。\n"
                f"确认后才生成代码。评估ID：{assessment['id']}")
