"""Persistent extension versions. Host actions select versions; models only read."""
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime,timezone

from graph_research.runtime.storage import safe_path,read_json,write_json,exclusive_lock


NAME=r'[a-z][a-z0-9_]{2,63}'
PIN=r'[0-9a-f]{64}'


def package_id(record):
    """Identify code, interface, fixtures and approved descriptive metadata."""
    value={key:record.get(key) for key in ('name','source_sha256','parameters','tests','library_metadata')}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()


def metadata(value):
    """Bounded documentation supplied during assessment, never executable rules."""
    value={} if value is None else value
    if not isinstance(value,dict) or set(value)-{'title','summary','preconditions','limitations','returns','tags'}:raise ValueError('Unknown extension metadata fields')
    for key,item in value.items():
        if key in ('preconditions','limitations','tags'):
            if not isinstance(item,list) or len(item)>12 or any(not isinstance(s,str) or not 1<=len(s)<=500 for s in item):raise ValueError('Invalid extension metadata list')
        elif not isinstance(item,str) or not 1<=len(item)<=2000:raise ValueError('Invalid extension metadata text')
        if key=='title' and len(item)>160:raise ValueError('Extension title exceeds160 characters')
    if len(json.dumps(value,ensure_ascii=False).encode())>12000:raise ValueError('Extension metadata exceeds12KB')
    return json.loads(json.dumps(value))


class ToolLibrary:
    """One explicitly selected store; shared stores are a trusted host choice."""
    def __init__(self,directory):
        from .change_control import external_directory
        self.directory=external_directory(directory);self.path=self.directory/'.library.json'

    def state(self):
        if not self.path.exists():return {'format':'graph-research-library/1','revision':0,'tools':{},'history':[]}
        value,_=read_json(self.path,max_bytes=256*1024)
        if not isinstance(value,dict) or value.get('format')!='graph-research-library/1' or type(value.get('revision')) is not int or not isinstance(value.get('tools'),dict):raise ValueError('Invalid library state; restore the recorded state before loading extensions')
        if len(value['tools'])>128:raise ValueError('Library exceeds128 tool names')
        for name,entry in value['tools'].items():
            if not re.fullmatch(NAME,name) or not isinstance(entry,dict) or type(entry.get('enabled')) is not bool or not re.fullmatch(PIN,entry.get('active_version','')):raise ValueError('Invalid library version selection')
        return value

    def manifests(self):
        """Inventory legacy installed folders and immutable additional versions."""
        paths=sorted(self.directory.glob('*/tool.json'))+sorted(self.directory.glob('.versions/*/tool.json'))+sorted(self.directory.glob('.versions/*/*/tool.json'))
        if len(paths)>512:raise ValueError('Library exceeds512 installed version manifests')
        result=[]
        for path in paths:
            try:
                path=safe_path(path,root=self.directory);record,_=read_json(path,max_bytes=200000)
                if not isinstance(record,dict):raise ValueError('Extension manifest must be an object')
                name=record.get('name')
                if not isinstance(name,str) or not re.fullmatch(NAME,name):raise ValueError('Invalid extension name')
                relative=path.relative_to(self.directory).parts
                if record.get('approved_new_algorithm'):
                    if (len(relative)==2 and relative[0]!=name) or (len(relative)==4 and relative[1]!=name):raise ValueError('Extension folder/name mismatch')
                    if len(relative)==3 and relative[1]!=package_id(record)[:24]:raise ValueError('Compact version folder differs from package identity')
                result.append({'path':path,'record':record,'name':name,'version':package_id(record),'legacy_location':len(relative)==2})
            except (OSError,ValueError,KeyError,TypeError) as error:result.append({'path':path,'error':type(error).__name__+': '+str(error)})
        return result

    def selected(self):
        """Never silently fall back to another version if the selection is broken."""
        state=self.state();rows=self.manifests();chosen=[];errors=[]
        for row in rows:
            if 'error' in row:errors.append({'package':row['path'].parent.name,'error':row['error'][:512],'action':'quarantined'});continue
            entry=state['tools'].get(row['name'])
            if entry is None:
                if row['legacy_location']:chosen.append(row)
            elif entry['enabled'] and entry['active_version']==row['version']:chosen.append(row)
        for name,entry in state['tools'].items():
            if entry['enabled'] and not any(row.get('name')==name for row in chosen):errors.append({'package':name,'error':'Selected version missing or changed; no automatic fallback','action':'quarantined'})
        if len(chosen)>128:raise ValueError('Library exceeds128 enabled tools')
        return chosen,errors

    def catalog(self,query='',limit=20,offset=0):
        """Read only. Invalid packages are shown but never installed or executed."""
        if not isinstance(query,str) or len(query)>256 or type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or not 0<=offset<=10000:raise ValueError('Invalid library search controls')
        from .registry import ToolRegistry
        from .extensions import ToolStore
        state=self.state();rows=[];registry=ToolRegistry();native=dict(registry.tools)
        for item in self.manifests():
            if 'error' in item:
                rows.append({'name':item['path'].parent.name,'version':None,'state':'quarantined','error':item['error'][:512]});continue
            record=item['record'];name=item['name'];entry=state['tools'].get(name)
            active=(entry['active_version']==item['version']) if entry else item['legacy_location']
            row={'name':name,'version':item['version'],'active':active,'enabled':entry['enabled'] if entry else True,
                 'description':str(record.get('description',''))[:2000],'metadata':{},
                 'source_sha256':record.get('source_sha256'),'tests_passed':len(record.get('test_results',[])) if isinstance(record.get('test_results'),list) else 0,
                 'assessment_id':record.get('assessment_id'),'data_role':'extension_documentation_not_instruction_or_mathematical_proof'}
            try:
                row['metadata']=metadata(record.get('library_metadata'))
                registry.tools=native.copy();store=ToolStore(self.directory);store._load_manifest(item['path'],registry)
                tool=registry.tools.get(name)
                if tool is None or tool.status=='native_tested':raise ValueError('Package is not a published approved extension')
                row['state']='enabled' if active and row['enabled'] else 'disabled' if active else 'inactive_version'
                row['parameters']=tool.parameters;row['examples']=(tool.documentation or {}).get('examples',[])
            except (OSError,ValueError,KeyError,TypeError,SyntaxError) as error:row.update(state='disabled_legacy' if not record.get('approved_new_algorithm') else 'quarantined',error=(type(error).__name__+': '+str(error))[:512])
            text=json.dumps(row,ensure_ascii=False).casefold()
            if all(term.casefold() in text for term in query.split()):rows.append(row)
        total=len(rows)
        return {'format':'graph-research-library-catalog/1','revision':state['revision'],'read_only':True,'records':rows[offset:offset+limit],
                'total':total,'next_offset':offset+limit if offset+limit<total else None}

    def select(self,name,version,*,enabled=True):
        """Trusted UI/CLI only. A version must still pass its original audit."""
        if not isinstance(name,str) or not re.fullmatch(NAME,name) or not isinstance(version,str) or not re.fullmatch(PIN,version) or type(enabled) is not bool:raise ValueError('Invalid extension version selection')
        with exclusive_lock(self.directory/'.library.lock'):
            matches=[row for row in self.catalog(limit=100)['records'] if row['name']==name and row['version']==version]
            # There may be more than100 versions overall; inspect further pages.
            offset=100
            while not matches and offset<512:
                page=self.catalog(limit=100,offset=offset);matches=[row for row in page['records'] if row['name']==name and row['version']==version]
                if page['next_offset'] is None:break
                offset+=100
            if not matches or matches[0]['state'] in ('quarantined','disabled_legacy'):raise ValueError('No verified installed version; selection did not change')
            return self._select(name,version,enabled)

    def _select(self,name,version,enabled=True):
        state=self.state()
        if name not in state['tools'] and len(state['tools'])>=128:raise ValueError('Library exceeds128 tools')
        previous=state['tools'].get(name);state['tools'][name]={'active_version':version,'enabled':enabled};state['revision']+=1
        state['history']=(state.get('history',[])+[{'name':name,'previous':previous,'selected':state['tools'][name],
            'at':datetime.now(timezone.utc).isoformat(),'source':'trusted_host_user_action'}])[-256:]
        write_json(self.path,state,backup=True);return state['tools'][name]


def active_identity(directory,name):
    library=ToolLibrary(directory)
    try:rows=library.selected()[0]
    except (OSError,ValueError,KeyError,TypeError):return None
    for row in rows:
        if row['name']==name:return {'package_id':row['version'],'source_sha256':row['record']['source_sha256']}
    return None
