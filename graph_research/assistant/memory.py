"""Local, user-scoped preferences and aggregate usage; no prompts or approvals.

Identity is supplied by the host. A local user ID is a partition key, not login
authentication. This module has no model or third-party dependencies.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone

PREFERENCE_SCHEMA = {
    'language': ('zh-CN', 'en'),
    'response_detail': ('concise', 'standard', 'detailed'),
    'figure_format': ('png', 'svg', 'pdf', 'tikz'),
    'layout': ('spring', 'circular'),
    'vertex_labels': (True, False),
    'edge_labels': (True, False),
}


def default_memory_directory():
    """Stable across working directories and sessions on this OS account."""
    return Path.home()/'.graph_research'/'user_memory'


@contextmanager
def readonly_memory(directory):
    """Open existing memory read-only; discovery never creates a database."""
    from graph_research.runtime.storage import safe_path
    path=safe_path(Path(directory)/'memory.sqlite3')
    if not path.is_file():yield None;return
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)
    try:yield db
    finally:db.close()


def read_memory_context(directory,user_id):
    """User-scoped, sanitized model view without writes or filesystem paths."""
    user=_user_key(user_id)
    with readonly_memory(directory) as db:
        if db is None:return {'available':False,'enabled':True,**sanitize_context({})}
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'users','preferences','usage'}<=tables:raise ValueError('Invalid user memory schema')
        enabled=UserMemoryStore._enabled(db,user)
        if not enabled:return {'available':True,'enabled':False,**sanitize_context({})}
        preferences={}
        for name,value in db.execute('SELECT name,value FROM preferences WHERE user_key=?',(user,)):
            try:preferences[name]=json.loads(value)
            except (ValueError,TypeError):continue
        tools=[{'tool':name,'successful_calls':count} for name,count in db.execute('SELECT tool,count FROM usage WHERE user_key=? ORDER BY count DESC,tool LIMIT 10',(user,))]
        return {'available':True,'enabled':True,**sanitize_context({'preferences':preferences,'frequently_used_tools':tools})}


def _user_key(user_id):
    if not isinstance(user_id, str) or not user_id.strip() or len(user_id)>128:
        raise ValueError('A nonempty stable user_id of at most 128 characters is required')
    if user_id != user_id.strip() or any(ord(c)<32 for c in user_id):
        raise ValueError('user_id cannot contain surrounding whitespace or control characters')
    return hashlib.sha256(user_id.encode('utf-8')).hexdigest()


def validate_preference(key, value):
    """Only typed presentation preferences are accepted, never free-form rules."""
    choices=PREFERENCE_SCHEMA.get(key)
    if choices is None or not any(type(value) is type(v) and value==v for v in choices):
        raise ValueError(f'Unsupported preference {key!r}; supported values: {choices}')


def sanitize_context(value):
    """Constrain even host-supplied memory to a small non-instruction schema."""
    value=value if isinstance(value, dict) else {}
    preferences={}
    supplied=value.get('preferences',{})
    if isinstance(supplied,dict):
        for key,item in supplied.items():
            try:validate_preference(key,item)
            except ValueError:continue
            preferences[key]=item
    frequent=[]
    for item in value.get('frequently_used_tools',[])[:10] if isinstance(value.get('frequently_used_tools'),list) else []:
        if not isinstance(item,dict):continue
        name,count=item.get('tool'),item.get('successful_calls')
        if isinstance(name,str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}',name) and type(count) is int and count>0:
            frequent.append({'tool':name,'successful_calls':min(count,1000000000)})
    return {'preferences':preferences,'frequently_used_tools':frequent}


class UserMemoryStore:
    """SQLite persistence with per-user isolation and explicit management APIs.

    Usage stores tool names/counts only, not inputs, results, prompts, graph data,
    model credentials, scientific parameters or consent. Writes need a trusted
    host caller; no memory mutation is exposed as an LLM tool.
    """
    def __init__(self,directory=None):
        original=Path(directory if directory is not None else default_memory_directory())
        self.directory=original.resolve()
        self.path=self.directory/'memory.sqlite3'
        # Resolve the file as well as its parent to reject a source-tree symlink.
        core=Path(__file__).resolve().parents[1]
        for target in (self.directory,self.path.resolve()):
            if target==core or target.is_relative_to(core):raise ValueError('Memory storage must be outside the original package')
        from graph_research.runtime.storage import safe_path
        safe_path(original);safe_path(original/'memory.sqlite3')
        self.directory.mkdir(parents=True,exist_ok=True)
        with self._connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    user_key TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS preferences (
                    user_key TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL,
                    source TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_key,name));
                CREATE TABLE IF NOT EXISTS usage (
                    user_key TEXT NOT NULL, tool TEXT NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY (user_key,tool));
                CREATE TABLE IF NOT EXISTS events (
                    user_key TEXT NOT NULL, event_key TEXT NOT NULL,
                    PRIMARY KEY (user_key,event_key));
            ''')

    @contextmanager
    def _connection(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()

    @staticmethod
    def _enabled(db,user):
        row=db.execute('SELECT enabled FROM users WHERE user_key=?',(user,)).fetchone()
        return row is None or bool(row[0])

    def set_enabled(self,user_id,enabled):
        """Enable or suspend reading and learning without erasing this user."""
        if type(enabled) is not bool:raise ValueError('enabled must be a boolean')
        with self._connection() as db:
            db.execute('INSERT INTO users VALUES (?,?) ON CONFLICT(user_key) DO UPDATE SET enabled=excluded.enabled',(_user_key(user_id),int(enabled)))

    def set_preference(self,user_id,key,value,source='host'):
        """Set one typed preference after an explicit user choice; not model inference."""
        validate_preference(key,value)
        if source not in ('host','cli','user_message'):raise ValueError('Unknown preference source')
        user=_user_key(user_id)
        with self._connection() as db:
            if not self._enabled(db,user):raise ValueError('Memory is disabled for this user; enable it first')
            db.execute('INSERT INTO preferences VALUES (?,?,?,?,?) ON CONFLICT(user_key,name) DO UPDATE SET value=excluded.value,source=excluded.source,updated_at=excluded.updated_at',
                       (user,key,json.dumps(value),source,datetime.now(timezone.utc).isoformat()))

    def remember_message(self,user_id,text):
        """Recognize only a whole-message explicit command, without an LLM call.

        Arbitrary research text, quoted documents, temporary instructions and
        model answers are never mined as preferences. Use set_preference for
        other wording. The exact supported forms are documented in USER_MEMORY.
        """
        if not isinstance(text,str):return {}
        command=text.strip().rstrip('。.!！').strip()
        commands={
            '记住：以后用中文回答':('language','zh-CN'),
            '记住：以后用英文回答':('language','en'),
            '记住：以后回答简洁一些':('response_detail','concise'),
            '记住：以后回答详细一些':('response_detail','detailed'),
            '记住：以后默认使用圆形布局':('layout','circular'),
            '记住：以后默认使用弹簧布局':('layout','spring'),
        }
        for fmt in ('png','svg','pdf','tikz'):
            commands[f'记住：以后默认导出{fmt.upper()}']=('figure_format',fmt)
        item=commands.get(command)
        if not item:return {}
        if not self.profile(user_id)['enabled']:return {}
        self.set_preference(user_id,*item,source='user_message')
        return dict([item])

    def observe(self,user_id,event_id,tool):
        """Count one successful call once. Host validates success and registration."""
        user=_user_key(user_id)
        if not isinstance(tool,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',tool):
            raise ValueError('Expected a registered tool name')
        if not isinstance(event_id,str) or not event_id or len(event_id)>512:raise ValueError('Invalid event ID')
        event=hashlib.sha256(event_id.encode('utf-8')).hexdigest()
        with self._connection() as db:
            if not self._enabled(db,user):return
            # Serialize the deduplication check and counter update in one transaction.
            inserted=db.execute('INSERT OR IGNORE INTO events VALUES (?,?)',(user,event)).rowcount
            if inserted:
                db.execute('INSERT INTO usage VALUES (?,?,1) ON CONFLICT(user_key,tool) DO UPDATE SET count=count+1',(user,tool))

    def profile(self,user_id):
        """Inspectable metadata; unlike context(), disabled profiles remain visible."""
        user=_user_key(user_id)
        with self._connection() as db:
            preferences={};metadata={}
            for name,value,source,updated in db.execute('SELECT name,value,source,updated_at FROM preferences WHERE user_key=? ORDER BY name',(user,)):
                preferences[name]=json.loads(value);metadata[name]={'source':source,'updated_at':updated}
            frequent=[{'tool':name,'successful_calls':count} for name,count in db.execute('SELECT tool,count FROM usage WHERE user_key=? ORDER BY count DESC,tool LIMIT 10',(user,))]
            return {'enabled':self._enabled(db,user),'preferences':preferences,'preference_metadata':metadata,'frequently_used_tools':frequent}

    def context(self,user_id):
        """Return bounded advisory model context, or empty data when disabled."""
        profile=self.profile(user_id)
        return sanitize_context(profile) if profile['enabled'] else sanitize_context({})

    def forget(self,user_id,key):
        """Remove one explicit preference for this user only."""
        if key not in PREFERENCE_SCHEMA:raise ValueError('Unknown preference')
        with self._connection() as db:
            db.execute('DELETE FROM preferences WHERE user_key=? AND name=?',(_user_key(user_id),key))

    def clear(self,user_id):
        """Erase this user's preferences, usage and experiences; keep enabled state."""
        user=_user_key(user_id)
        with self._connection() as db:
            present={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('experience_reviews','experience_entries','preferences','usage','events'):
                if table not in present:continue
                db.execute(f'DELETE FROM {table} WHERE user_key=?',(user,))
