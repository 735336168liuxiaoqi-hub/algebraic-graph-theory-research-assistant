"""Durable host-signed user events. IDs are references, not self-approval flags.

The local service account owns this store. Expose the parent facade to models,
and keep event issuance in the trusted UI/user handler. This is not an HTTP
authentication system and cannot protect against arbitrary trusted host code.
"""
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import time
import uuid

from graph_research.runtime.storage import safe_path,exclusive_lock,write_json,read_json
from .task_contract import canonical,check_id,TaskProtocolError


class HostEventStore:
    def __init__(self,root,owner_key,ttl_seconds=3600):
        self.root=safe_path(root);self.owner_key=owner_key
        if type(ttl_seconds) is not int or not 1<=ttl_seconds<=86400:raise ValueError('Event TTL must be1..86400 seconds')
        self.ttl=ttl_seconds
        key_path=safe_path(self.root/'.host-events.key')
        with exclusive_lock(self.root/'.host-events.lock'):
            if not key_path.exists():
                descriptor=os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,'wb') as stream:stream.write(secrets.token_bytes(32));stream.flush();os.fsync(stream.fileno())
            self._key=key_path.read_bytes()
        if len(self._key)!=32:raise TaskProtocolError('host_key_invalid','宿主事件密钥损坏，未自动重建；请恢复可信宿主数据。')
        self.directory=safe_path(self.root/'users'/owner_key[:32]/'events')

    def _path(self,event_id):return safe_path(self.directory/(check_id(event_id)+'.json'),root=self.directory)

    def _signature(self,body):return hmac.new(self._key,canonical(body).encode('utf-8'),hashlib.sha256).hexdigest()

    def read(self,event_id,*,allow_expired=False):
        try:document,_=read_json(self._path(event_id),max_bytes=256*1024)
        except (OSError,ValueError):raise TaskProtocolError('event_not_found','没有该用户的有效宿主事件。') from None
        try:
            body=document['body'];signature=document['signature']
            if not isinstance(signature,str) or not hmac.compare_digest(signature,self._signature(body)) or body['owner_key']!=self.owner_key or body['event_id']!=event_id:
                raise ValueError()
        except (ValueError,TypeError,KeyError):raise TaskProtocolError('invalid_host_event','宿主事件校验失败；JSON中的同意、角色或签名字段不能替代用户操作。') from None
        if not allow_expired and time.time()>body['expires_at']:raise TaskProtocolError('event_expired','用户操作事件已过期，请重新展示当前交互并由用户确认。')
        return body

    def issue(self,record,kind,payload,*,event_id=None):
        event_id=check_id(event_id) if event_id is not None else uuid.uuid4().hex
        semantic={'event_id':event_id,'owner_key':self.owner_key,'task_id':record['task_id'],'request_sha256':record['request_sha256'],
                  'revision':record['revision'],'interaction_id':record['pending']['interaction_id'],
                  'kind':kind,'payload':payload}
        with exclusive_lock(self.directory/'.events.lock'):
            path=self._path(event_id)
            if path.exists():
                existing=self.read(event_id,allow_expired=True)
                if any(existing.get(key)!=value for key,value in semantic.items()):raise TaskProtocolError('event_id_conflict','同一事件ID不能改成另一项用户操作。')
                body=existing
            else:
                now=time.time();body={**semantic,'issued_at':now,'expires_at':now+self.ttl,'source':'trusted_host_user_handler'}
                write_json(path,{'body':body,'signature':self._signature(body)})
        return {key:body[key] for key in ('event_id','task_id','interaction_id','revision','kind','expires_at')}
