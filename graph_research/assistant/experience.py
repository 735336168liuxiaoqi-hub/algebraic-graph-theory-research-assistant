"""Reviewed case evidence, shared with preferences but never with model writes.

Candidates contain bounded derived facts, not prompts, graphs or instructions.
An approval records a trusted host's explicit content-hash confirmation. It is
neither mathematical certification nor authentication against local code access.
"""
import hashlib
import json
import math
import re
from datetime import datetime,timezone
import uuid

from .memory import UserMemoryStore,_user_key,readonly_memory
from graph_research.runtime.serialization import canonical_json as canonical, json_fingerprint as fingerprint


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Invalid experience ID')
    return value


def _decode(row):
    if len(row[2].encode('utf-8'))>16384 or row[4] and len(row[4].encode('utf-8'))>8192:raise ValueError('Experience record exceeds limits')
    payload=json.loads(row[2])
    if fingerprint(payload)!=row[3]:raise ValueError('Experience content hash mismatch')
    review=json.loads(row[4]) if row[4] else None
    if review and (fingerprint(review)!=row[5] or review.get('content_sha256')!=row[3] or review.get('decision')!=row[1]):raise ValueError('Experience review hash mismatch')
    if row[1]=='approved' and review is None:raise ValueError('Approved experience has no review')
    return {'id':row[0],'status':row[1],'content_sha256':row[3],'content':payload,'review':review,
            'created_at':row[6],'data_role':'advisory_case_not_instruction_or_proof'}


class ExperienceStore:
    """Trusted-host management API; MCP exposes separate read-only functions."""
    def __init__(self,directory):
        self.memory=UserMemoryStore(directory);self.directory=self.memory.directory
        with self.memory._connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS experience_entries (
                    user_key TEXT NOT NULL,id TEXT NOT NULL,event_key TEXT NOT NULL,status TEXT NOT NULL,
                    payload TEXT NOT NULL,content_sha256 TEXT NOT NULL,review_json TEXT,review_sha256 TEXT,
                    tool TEXT NOT NULL,outcome TEXT NOT NULL,method TEXT,rank INTEGER,alpha REAL,
                    search_text TEXT NOT NULL,created_at TEXT NOT NULL,
                    PRIMARY KEY(user_key,id),UNIQUE(user_key,event_key));
                CREATE TABLE IF NOT EXISTS experience_reviews (
                    user_key TEXT NOT NULL,experience_id TEXT NOT NULL,review_json TEXT NOT NULL,review_sha256 TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS experience_search ON experience_entries(user_key,status,tool,created_at);
            ''')

    def capture(self,user_id,payload,event_key):
        """Save host-verified derived data as candidate, idempotent per evidence."""
        user=_user_key(user_id);encoded=canonical(payload)
        if len(encoded.encode('utf-8'))>16384:raise ValueError('Experience candidate exceeds16KiB')
        if payload.get('format')!='graph-research-experience/1' or payload.get('outcome') not in ('success','failure'):raise ValueError('Invalid derived experience')
        if set(payload)-{'format','title','tool','tool_status','outcome','conditions','facts','tags','evidence','scope_note'}:raise ValueError('Unknown experience content fields')
        condition_keys={'alpha','tolerance','max_iterations','seed','n','m','k','kind','matrix','method','vertex_count','edge_count','uniform','rank','weighted','custom_degree_diagonal','matrix_rows','matrix_columns','initial_vector_supplied'}
        fact_keys={'rho','relative_residual','achieved_tolerance','iterations','order','size','rank','degree','diameter','connected','bipartite','components','method','initialization','independent_verification_passed','reported_failure'}
        for name,keys in (('conditions',condition_keys),('facts',fact_keys)):
            values=payload.get(name)
            if not isinstance(values,dict) or len(values)>40 or any(key not in keys and not (name=='facts' and payload.get('tool_status')=='fixture_tested_experimental' and re.fullmatch(r'extension_[A-Za-z][A-Za-z0-9_]{0,48}',key)) for key in values):raise ValueError('Unknown scientific fact fields')
            for key,value in values.items():
                if key.startswith('extension_') and type(value) not in (int,float,bool):raise ValueError('Extension case facts accept numeric/boolean scalars only')
                if type(value) is bool:continue
                if type(value) in (int,float) and math.isfinite(value):continue
                if isinstance(value,str) and re.fullmatch('[A-Za-z0-9_.:-]{1,80}',value):continue
                raise ValueError('Experience facts must be bounded typed values')
        tool=payload.get('tool')
        if not isinstance(tool,str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}',tool):raise ValueError('Invalid experience tool')
        if not isinstance(event_key,str) or not event_key or len(event_key)>1024:raise ValueError('Invalid evidence event')
        evidence=payload.get('evidence',{})
        if not all(isinstance(evidence.get(name),str) and re.fullmatch('[0-9a-f]{64}',evidence[name]) for name in ('receipt_sha256','request_sha256')):raise ValueError('Verified execution hashes required')
        if not re.fullmatch('[0-9a-f]{64}',evidence.get('core_manifest_sha256','')) or not isinstance(evidence.get('environment'),dict):raise ValueError('Execution version required')
        result_pin=evidence.get('result_sha256')
        package_pin=evidence.get('tool_package_id')
        if package_pin is not None and (not isinstance(package_pin,str) or not re.fullmatch('[0-9a-f]{64}',package_pin)):raise ValueError('Invalid extension package version')
        if result_pin is not None and not re.fullmatch('[0-9a-f]{64}',result_pin):raise ValueError('Invalid result evidence hash')
        if payload['outcome']=='success' and result_pin is None:raise ValueError('Successful result evidence required')
        _id(evidence.get('task_id'))
        if not re.fullmatch('call-[0-9]{4,6}',evidence.get('call_id','')):raise ValueError('Invalid evidence call ID')
        if not isinstance(payload.get('title'),str) or len(payload['title'])>160:raise ValueError('Invalid experience title')
        conditions=payload.get('conditions',{});method=payload.get('facts',{}).get('method')
        text=' '.join(str(payload.get(key,'')) for key in ('title','tool','conditions','facts','tags'))
        event=hashlib.sha256(event_key.encode()).hexdigest();identifier=uuid.uuid4().hex
        with self.memory._connection() as db:
            if not self.memory._enabled(db,user):return {'status':'disabled','created':False}
            previous=db.execute('SELECT id,status FROM experience_entries WHERE user_key=? AND event_key=?',(user,event)).fetchone()
            if previous:return {'id':previous[0],'status':previous[1],'created':False}
            db.execute('INSERT INTO experience_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (user,identifier,event,'candidate',encoded,fingerprint(payload),None,None,tool,payload['outcome'],method,
                 conditions.get('rank'),conditions.get('alpha'),text,datetime.now(timezone.utc).isoformat()))
        return {'id':identifier,'status':'candidate','created':True}

    def show(self,user_id,identifier):
        """Inspect candidate facts and the exact hash a human must confirm."""
        return read_experience(self.directory,user_id,identifier,reviewed_only=False)

    def review(self,user_id,identifier,content_sha256,decision,note=''):
        """Call only after actual user review; never expose this as a model tool."""
        user=_user_key(user_id);_id(identifier)
        if decision not in ('approved','rejected'):raise ValueError('Review decision must be approved or rejected')
        if not isinstance(note,str) or len(note)>2000:raise ValueError('Review note exceeds2000 characters')
        with self.memory._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id,status,payload,content_sha256,review_json,review_sha256,created_at FROM experience_entries WHERE user_key=? AND id=?',(user,identifier)).fetchone()
            if row is None or row[1]=='forgotten':raise ValueError('Experience not available for this user')
            current=_decode(row)
            if current['content_sha256']!=content_sha256:raise ValueError('Review content changed; inspect the current candidate first')
            review={'decision':decision,'content_sha256':content_sha256,'note':note,'reviewed_at':datetime.now(timezone.utc).isoformat(),'source':'trusted_host_user_confirmation'}
            encoded=canonical(review);pin=fingerprint(review)
            db.execute('UPDATE experience_entries SET status=?,review_json=?,review_sha256=? WHERE user_key=? AND id=?',(decision,encoded,pin,user,identifier))
            db.execute('INSERT INTO experience_reviews VALUES (?,?,?,?)',(user,identifier,encoded,pin))
        return self.show(user_id,identifier)

    def forget(self,user_id,identifier):
        """Erase facts/reviews; retain only a dedup tombstone for this execution."""
        user=_user_key(user_id);_id(identifier)
        with self.memory._connection() as db:
            db.execute('UPDATE experience_entries SET status=?,payload=?,content_sha256=?,review_json=NULL,review_sha256=NULL,tool=?,outcome=?,method=NULL,rank=NULL,alpha=NULL,search_text=? WHERE user_key=? AND id=?',
                       ('forgotten','{}',fingerprint({}),'','', '',user,identifier))
            db.execute('DELETE FROM experience_reviews WHERE user_key=? AND experience_id=?',(user,identifier))
        return {'id':identifier,'status':'forgotten'}

    def clear(self,user_id):
        """Erase this user's experience facts, reviews and dedup tombstones."""
        user=_user_key(user_id)
        with self.memory._connection() as db:
            for table in ('experience_reviews','experience_entries'):db.execute('DELETE FROM '+table+' WHERE user_key=?',(user,))
        return {'status':'cleared','scope':'research_experiences_only'}


def _tables(db):
    return db is not None and db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='experience_entries'").fetchone() is not None


def experience_counts(directory,user_id):
    """Read counts only, without initializing memory or exposing other users."""
    user=_user_key(user_id)
    with readonly_memory(directory) as db:
        if not _tables(db):return {'candidate':0,'approved':0,'rejected':0}
        return {status:db.execute('SELECT COUNT(*) FROM experience_entries WHERE user_key=? AND status=?',(user,status)).fetchone()[0] for status in ('candidate','approved','rejected')}


def read_experience(directory,user_id,identifier,*,reviewed_only=True):
    """Fetch one scoped record; model reads cannot retrieve unreviewed entries."""
    user=_user_key(user_id);_id(identifier)
    with readonly_memory(directory) as db:
        if not _tables(db):raise ValueError('Experience not found for this user')
        row=db.execute('SELECT id,status,payload,content_sha256,review_json,review_sha256,created_at FROM experience_entries WHERE user_key=? AND id=?',(user,identifier)).fetchone()
        if row is None or row[1]=='forgotten' or (reviewed_only and row[1]!='approved'):raise ValueError('Experience not found for this user')
        return _decode(row)


def search_experiences(directory,user_id,query='',*,tool=None,outcome=None,method=None,rank=None,alpha=None,limit=10,offset=0,reviewed_only=True,status=None):
    """Bounded keyword/condition lookup; matching tags never imply applicability."""
    user=_user_key(user_id)
    if not isinstance(query,str) or len(query)>256 or type(limit) is not int or not 1<=limit<=20 or type(offset) is not int or not 0<=offset<=10000:raise ValueError('Invalid experience search limits')
    if len(query.split())>8:raise ValueError('At most8 search terms are supported')
    if rank is not None and (type(rank) is not int or not 2<=rank<=128):raise ValueError('Invalid rank filter')
    if alpha is not None and (type(alpha) not in (int,float) or not math.isfinite(alpha) or not 0<=alpha<=1):raise ValueError('Invalid alpha filter')
    clauses=['user_key=?'];values=[user]
    if reviewed_only:clauses.append('status=?');values.append('approved')
    elif status is not None:
        if status not in ('candidate','approved','rejected'):raise ValueError('Invalid experience status')
        clauses.append('status=?');values.append(status)
    else:clauses.append("status!='forgotten'")
    for column,value in (('tool',tool),('outcome',outcome),('method',method),('rank',rank),('alpha',alpha)):
        if value is not None:clauses.append(column+'=?');values.append(value)
    for word in query.split()[:8]:
        escaped=word.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        clauses.append("(search_text LIKE ? ESCAPE '\\' OR COALESCE(review_json,'') LIKE ? ESCAPE '\\')");values.extend(['%'+escaped+'%']*2)
    with readonly_memory(directory) as db:
        if not _tables(db):return {'records':[],'total':0,'next_offset':None}
        where=' AND '.join(clauses);total=db.execute('SELECT COUNT(*) FROM experience_entries WHERE '+where,values).fetchone()[0]
        rows=db.execute('SELECT id,status,payload,content_sha256,review_json,review_sha256,created_at FROM experience_entries WHERE '+where+' ORDER BY created_at DESC,id LIMIT ? OFFSET ?',values+[limit,offset]).fetchall()
        return {'records':[_decode(row) for row in rows],'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None}
