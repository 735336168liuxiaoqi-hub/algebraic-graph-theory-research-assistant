"""Content-free RPC accounting. Bytes are not estimated model tokens."""
import sqlite3
import time
import json
import re
from graph_research.runtime.storage import safe_path


class RPCTelemetry:
    def __init__(self,directory):self.path=safe_path(directory/'rpc-metrics.sqlite3')

    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);connection=sqlite3.connect(self.path,timeout=5)
        try:
            connection.execute('CREATE TABLE IF NOT EXISTS calls(at REAL,version TEXT,operation TEXT,task_id TEXT,status TEXT,elapsed REAL,response_bytes INTEGER)')
            connection.execute('CREATE TABLE IF NOT EXISTS diagnostics(at REAL,id TEXT,version TEXT,operation TEXT,task_id TEXT,detail TEXT)')
        except Exception:connection.close();raise
        return connection

    def record(self,operation,result,elapsed,response_bytes):
        from graph_research import __version__
        connection=self.connect()
        try:
            with connection:
                connection.execute('INSERT INTO calls VALUES(?,?,?,?,?,?,?)',(time.time(),__version__,str(operation)[:64],result.get('task_id'),result.get('status','ok'),elapsed,response_bytes))
                errors=[result.get('error'),result.get('operation',{}).get('error')]+[row.get('error_details') for row in result.get('results',[]) if isinstance(row,dict)]
                for error in errors:
                    if isinstance(error,dict) and re.fullmatch('[0-9a-f]{32}',str(error.get('diagnostic_id',''))):
                        detail={key:error[key] for key in ('diagnostic_id','code','phase','exception_type','errno','winerror','retryable','cause_code','path_length_utf16','second_path_length_utf16') if key in error}
                        connection.execute('INSERT INTO diagnostics VALUES(?,?,?,?,?,?)',(time.time(),error['diagnostic_id'],__version__,str(operation)[:64],result.get('task_id'),json.dumps(detail)))
        finally:connection.close()

    def diagnostic(self,identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('Invalid diagnostic ID')
        if not self.path.is_file():return {'found':False,'diagnostic_id':identifier}
        connection=self.connect()
        try:
            row=connection.execute('SELECT at,version,operation,task_id,detail FROM diagnostics WHERE id=? ORDER BY at DESC LIMIT 1',(identifier,)).fetchone()
        finally:connection.close()
        return {'found':True,'at':row[0],'version':row[1],'operation':row[2],'task_id':row[3],'error':json.loads(row[4])} if row else {'found':False,'diagnostic_id':identifier}

    def report(self):
        if not self.path.is_file():return {'calls':0,'rows':[],'main_model_token_usage':None}
        connection=self.connect()
        try:
            rows=[{'version':r[0],'operation':r[1],'calls':r[2],'elapsed_seconds':r[3],'response_bytes':r[4]} for r in connection.execute(
                'SELECT version,operation,COUNT(*),SUM(elapsed),SUM(response_bytes) FROM calls GROUP BY version,operation ORDER BY version,operation')]
            recent=[{'at':r[0],'version':r[1],'operation':r[2],'task_id':r[3],'error':json.loads(r[4])} for r in connection.execute('SELECT at,version,operation,task_id,detail FROM diagnostics ORDER BY at DESC LIMIT 20')]
        finally:connection.close()
        return {'calls':sum(r['calls'] for r in rows),'rows':rows,'recent_diagnostics':recent,'main_model_token_usage':None,'scope':'MCP tool calls only; resource reads and handshakes excluded; capture is best effort',
                'meaning':'本机RPC次数、服务端等待耗时及单份结构化JSON字节；非端到端时间、MCP整帧字节或模型token。未记录研究输入、密钥和回答。'}
