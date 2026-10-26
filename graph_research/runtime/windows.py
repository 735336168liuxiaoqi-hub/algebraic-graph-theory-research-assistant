"""Windows low-integrity primary tokens and process-tree Job limits.

Only fresh task directories are labelled low. The caller's token, account and
source-tree ACLs stay unchanged. Fail closed if restrictions cannot be applied.
This is protection against accidental writes, not a general malware sandbox.
"""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import time


class SID_ATTRIBUTES(c.Structure):
    _fields_=[('Sid',c.c_void_p),('Attributes',w.DWORD)]

class STARTUP(c.Structure):
    _fields_=[('cb',w.DWORD),('reserved',w.LPWSTR),('desktop',w.LPWSTR),('title',w.LPWSTR),
              ('x',w.DWORD),('y',w.DWORD),('xsize',w.DWORD),('ysize',w.DWORD),('xchars',w.DWORD),('ychars',w.DWORD),
              ('fill',w.DWORD),('flags',w.DWORD),('show',w.WORD),('reserved2size',w.WORD),('reserved2',c.c_void_p),
              ('stdin',w.HANDLE),('stdout',w.HANDLE),('stderr',w.HANDLE)]


class STARTUP_EX(c.Structure):
    _fields_=[('startup',STARTUP),('attributes',c.c_void_p)]


class SECURITY_ATTRIBUTES(c.Structure):
    _fields_=[('length',w.DWORD),('descriptor',c.c_void_p),('inherit',w.BOOL)]

class PROCESS(c.Structure):
    _fields_=[('process',w.HANDLE),('thread',w.HANDLE),('pid',w.DWORD),('tid',w.DWORD)]

class BASIC_LIMIT(c.Structure):
    _fields_=[('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),
              ('min_working',c.c_size_t),('max_working',c.c_size_t),('processes',w.DWORD),
              ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]

class IO_COUNTERS(c.Structure):
    _fields_=[(name,c.c_ulonglong) for name in ('reads','writes','others','read_bytes','write_bytes','other_bytes')]

class EXTENDED_LIMIT(c.Structure):
    _fields_=[('basic',BASIC_LIMIT),('io',IO_COUNTERS),('process_memory',c.c_size_t),('job_memory',c.c_size_t),
              ('peak_process',c.c_size_t),('peak_job',c.c_size_t)]


class BASIC_ACCOUNTING(c.Structure):
    _fields_=[(name,c.c_longlong) for name in ('user','kernel','period_user','period_kernel')]+[
              (name,w.DWORD) for name in ('page_faults','total_processes','active_processes','terminated_processes')]


class PROCESS_IDS(c.Structure):
    _fields_=[('assigned',w.DWORD),('count',w.DWORD),('ids',c.c_size_t*64)]


class WindowsTask:
    """Prepare a suspended, restricted process; assign limits before resuming."""
    @property
    def startup_phase(self):return self._startup_phase

    @startup_phase.setter
    def startup_phase(self,name):
        now=time.perf_counter()
        if not hasattr(self,'startup_seconds'):self.startup_seconds={}
        if hasattr(self,'_startup_phase') and self._startup_phase!='running':
            self.startup_seconds[self._startup_phase]=self.startup_seconds.get(self._startup_phase,0)+max(0.0,now-self._phase_started)
        self._startup_phase=name;self._phase_started=now

    def __init__(self,argv,workspace,env,*,memory_mb=1024,cpu_seconds=30,max_processes=8,prepare=None,protected_paths=()):
        if os.name!='nt':raise RuntimeError('Windows restricted execution is unavailable on this platform')
        self.k=c.WinDLL('kernel32',use_last_error=True);self.a=c.WinDLL('advapi32',use_last_error=True)
        self.handles=[];self.allocations=[];self.process=PROCESS();self.job=None;self.closed=False;self.cpu_budget_ticks=int(cpu_seconds*10_000_000)
        self.attribute_buffer=None;self.attribute_list=None;self.inherited_handles=None
        self.startup_phase='check_protected_files'
        self._bind()
        try:
            for path in protected_paths:self._check_protected_label(path)
            sid=c.c_void_p()
            text='S-1-16-4096'
            self._ok(self.a.ConvertStringSidToSidW(text,c.byref(sid)))
            self.allocations.append(sid)
            self.startup_phase='prepare_workspace';self._low_directory(Path(workspace).resolve())
            if prepare is not None:prepare()
            original=w.HANDLE();restricted=w.HANDLE()
            self.startup_phase='create_restricted_token'
            self._ok(self.a.OpenProcessToken(self.k.GetCurrentProcess(),0x0001|0x0002|0x0008|0x0080,c.byref(original)))
            self.handles.append(original)
            attrs=SID_ATTRIBUTES(sid,0x20)
            self._ok(self.a.CreateRestrictedToken(original,0x1,0,None,0,None,0,None,c.byref(restricted)))
            self.handles.append(restricted)
            self._ok(self.a.SetTokenInformation(restricted,25,c.byref(attrs),c.sizeof(attrs)+self.a.GetLengthSid(sid)))
            self.job=self.k.CreateJobObjectW(None,None);self._ok(self.job);self.handles.append(self.job)
            self.startup_phase='configure_job'
            limit=EXTENDED_LIMIT()
            limit.basic.flags=0x2000|0x100|0x200|0x4|0x8
            limit.basic.job_time=int(cpu_seconds*10_000_000)
            limit.basic.processes=max_processes
            limit.process_memory=int(memory_mb*1024*1024)
            limit.job_memory=int(memory_mb*1024*1024)
            self._ok(self.k.SetInformationJobObject(self.job,9,c.byref(limit),c.sizeof(limit)))
            # Block cross-process UI handles, clipboard, desktops and settings.
            ui=w.DWORD(0xff)
            self._ok(self.k.SetInformationJobObject(self.job,4,c.byref(ui),c.sizeof(ui)))
            self.startup_phase='prepare_standard_handles'
            startup=self._standard_handles(Path(workspace))
            command=c.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in argv]))
            environment=c.create_unicode_buffer('\0'.join(f'{key}={value}' for key,value in sorted(env.items(),key=lambda kv:kv[0].upper()))+'\0\0')
            self.startup_phase='create_process'
            self._ok(self.a.CreateProcessAsUserW(restricted,str(argv[0]),command,None,None,True,
                         0x08000000|0x400|0x4|0x80000,environment,str(workspace),c.byref(startup.startup),c.byref(self.process)))
            self.handles.extend([self.process.process,self.process.thread])
            self.startup_phase='assign_job'
            self._ok(self.k.AssignProcessToJobObject(self.job,self.process.process))
            self.startup_phase='resume_process'
            if self.k.ResumeThread(self.process.thread)==0xffffffff:raise c.WinError(c.get_last_error())
            self.startup_phase='running'
        except BaseException as error:
            self.startup_phase=self.startup_phase
            error.protected_startup_seconds=dict(self.startup_seconds)
            error.protected_startup_phase=self.startup_phase
            if self.process.process:self.k.TerminateProcess(self.process.process,1)
            self.close()
            raise

    def _bind(self):
        signatures={
            'k':{'GetCurrentProcess':([],w.HANDLE),'CloseHandle':([w.HANDLE],w.BOOL),
                 'LocalFree':([c.c_void_p],c.c_void_p),'CreateJobObjectW':([c.c_void_p,w.LPCWSTR],w.HANDLE),
                 'SetInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),
                 'QueryInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.c_void_p],w.BOOL),
                 'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
                 'CreateFileW':([w.LPCWSTR,w.DWORD,w.DWORD,c.POINTER(SECURITY_ATTRIBUTES),w.DWORD,w.DWORD,w.HANDLE],w.HANDLE),
                 'InitializeProcThreadAttributeList':([c.c_void_p,w.DWORD,w.DWORD,c.POINTER(c.c_size_t)],w.BOOL),
                 'UpdateProcThreadAttribute':([c.c_void_p,w.DWORD,c.c_size_t,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p],w.BOOL),
                 'DeleteProcThreadAttributeList':([c.c_void_p],None),
                 'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'ResumeThread':([w.HANDLE],w.DWORD),
                 'WaitForSingleObject':([w.HANDLE,w.DWORD],w.DWORD),'GetExitCodeProcess':([w.HANDLE,c.POINTER(w.DWORD)],w.BOOL),
                 'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL),'TerminateProcess':([w.HANDLE,w.UINT],w.BOOL)},
            'a':{'GetLengthSid':([c.c_void_p],w.DWORD),
                 'ConvertStringSecurityDescriptorToSecurityDescriptorW':([w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.c_void_p],w.BOOL),
                 'GetSecurityDescriptorSacl':([c.c_void_p,c.POINTER(w.BOOL),c.POINTER(c.c_void_p),c.POINTER(w.BOOL)],w.BOOL),
                 'GetNamedSecurityInfoW':([w.LPCWSTR,c.c_int,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(c.c_void_p)],w.DWORD),
                 'GetAce':([c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)],w.BOOL),
                 'GetSidSubAuthorityCount':([c.c_void_p],c.POINTER(c.c_ubyte)),
                 'GetSidSubAuthority':([c.c_void_p,w.DWORD],c.POINTER(w.DWORD)),
                 'OpenProcessToken':([w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],w.BOOL),
                 'CreateRestrictedToken':([w.HANDLE,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,c.c_void_p,w.DWORD,c.c_void_p,c.POINTER(w.HANDLE)],w.BOOL),
                 'ConvertStringSidToSidW':([w.LPCWSTR,c.POINTER(c.c_void_p)],w.BOOL),
                 'SetNamedSecurityInfoW':([w.LPWSTR,c.c_int,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p],w.DWORD),
                 'GetTokenInformation':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],w.BOOL),
                 'SetTokenInformation':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),
                 'CreateProcessAsUserW':([w.HANDLE,w.LPCWSTR,w.LPWSTR,c.c_void_p,c.c_void_p,w.BOOL,w.DWORD,c.c_void_p,w.LPCWSTR,c.POINTER(STARTUP),c.POINTER(PROCESS)],w.BOOL)}}
        for library,definitions in signatures.items():
            for name,(args,result) in definitions.items():
                fn=getattr(getattr(self,library),name);fn.argtypes=args;fn.restype=result

    @staticmethod
    def _ok(result):
        if not result:raise c.WinError(c.get_last_error())

    def _standard_handles(self,workspace):
        """Capture launcher failures before Python starts; inherit exactly 3 handles.

        STARTUPINFOEX HANDLE_LIST avoids leaking unrelated inheritable handles
        from a desktop/MCP host when enabling bInheritHandles. No relaxed token,
        environment, filesystem permissions, or Job breakaway is introduced.
        """
        security=SECURITY_ATTRIBUTES(c.sizeof(SECURITY_ATTRIBUTES),None,True)
        handles=[]
        for name,access,creation in [('NUL',0x80000000,3),
                                     (str(workspace/'bootstrap-stdout.log'),0x40000000,1),
                                     (str(workspace/'bootstrap-stderr.log'),0x40000000,1)]:
            handle=self.k.CreateFileW(name,access,7,c.byref(security),creation,0,None)
            if handle==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
            self.handles.append(handle);handles.append(handle)
        size=c.c_size_t()
        self.k.InitializeProcThreadAttributeList(None,1,0,c.byref(size))
        if not size.value:raise c.WinError(c.get_last_error())
        self.attribute_buffer=c.create_string_buffer(size.value)
        self._ok(self.k.InitializeProcThreadAttributeList(self.attribute_buffer,1,0,c.byref(size)))
        self.attribute_list=c.cast(self.attribute_buffer,c.c_void_p)
        self.inherited_handles=(w.HANDLE*3)(*handles)
        self._ok(self.k.UpdateProcThreadAttribute(self.attribute_list,0,0x20002,self.inherited_handles,c.sizeof(self.inherited_handles),None,None))
        startup=STARTUP_EX();startup.startup.cb=c.sizeof(startup);startup.startup.flags=0x100
        startup.startup.stdin,startup.startup.stdout,startup.startup.stderr=handles
        startup.attributes=self.attribute_list
        return startup

    def _low_directory(self,path):
        if not path.is_dir() or any(path.iterdir()):raise ValueError('Restricted workspace must be a new empty directory')
        descriptor=c.c_void_p()
        self._ok(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW('S:(ML;OICI;NW;;;LW)',1,c.byref(descriptor),None))
        self.allocations.append(descriptor)
        present=w.BOOL();default=w.BOOL();acl=c.c_void_p()
        self._ok(self.a.GetSecurityDescriptorSacl(descriptor,c.byref(present),c.byref(acl),c.byref(default)))
        error=self.a.SetNamedSecurityInfoW(str(path),1,0x10,None,None,None,acl)
        if error:raise c.WinError(error)

    def _check_protected_label(self,path):
        """Refuse a core placed in an OS-writable low-integrity location."""
        acl=c.c_void_p();descriptor=c.c_void_p()
        error=self.a.GetNamedSecurityInfoW(str(path),1,0x10,None,None,None,c.byref(acl),c.byref(descriptor))
        if error:raise c.WinError(error)
        try:
            if not acl.value:return  # Unlabelled objects are medium by Windows policy.
            count=c.c_ushort.from_address(acl.value+4).value
            for index in range(count):
                ace=c.c_void_p();self._ok(self.a.GetAce(acl,index,c.byref(ace)))
                if c.c_ubyte.from_address(ace.value).value!=0x11:continue
                mask=w.DWORD.from_address(ace.value+4).value
                sid=c.c_void_p(ace.value+8)
                rid=self.a.GetSidSubAuthority(sid,self.a.GetSidSubAuthorityCount(sid)[0]-1)[0]
                if rid<8192 or not mask&1:raise PermissionError('Core files need medium-or-higher integrity with no-write-up protection')
        finally:
            if descriptor:self.k.LocalFree(descriptor)

    def wait(self,timeout,cancel=None,monitor=None):
        deadline=time.monotonic()+timeout
        while True:
            if cancel is not None and cancel.is_set():raise InterruptedError('Task cancelled; process tree terminated')
            if time.monotonic()>=deadline:raise TimeoutError('Task wall-time limit reached; process tree terminated')
            if monitor is not None:monitor()
            # Keep the kernel Job limit, and also check actual accumulated CPU.
            # Kernel limit notifications can be delayed relative to wall time.
            accounting=BASIC_ACCOUNTING()
            self._ok(self.k.QueryInformationJobObject(self.job,1,c.byref(accounting),c.sizeof(accounting),None))
            if accounting.user+accounting.kernel>=self.cpu_budget_ticks:self._ok(self.k.TerminateJobObject(self.job,1))
            status=self.k.WaitForSingleObject(self.process.process,50)
            if status==0:
                code=w.DWORD();self._ok(self.k.GetExitCodeProcess(self.process.process,c.byref(code)))
                return code.value
            if status!=258:raise c.WinError(c.get_last_error())

    def close(self):
        if self.closed:return
        self.closed=True
        try:
            descendants=[]
            if self.job:
                # Capture SYNCHRONIZE handles before termination. Job accounting
                # can reach zero just before a child's process object signals.
                ids=PROCESS_IDS();self._ok(self.k.QueryInformationJobObject(self.job,3,c.byref(ids),c.sizeof(ids),None))
                if ids.count>64:raise RuntimeError('Unexpected process count in bounded job')
                for pid in ids.ids[:ids.count]:
                    handle=self.k.OpenProcess(0x100000,False,pid)
                    if handle:self.handles.append(handle);descendants.append(handle)
                    elif c.get_last_error()!=87:raise c.WinError(c.get_last_error())
            if self.job:self._ok(self.k.TerminateJobObject(self.job,1))
            # Termination is asynchronous. Keep handles until the entire job
            # exits, so cancelled workers cannot retain workspace handles.
            deadline=time.monotonic()+5
            if self.process.process:
                status=self.k.WaitForSingleObject(self.process.process,5000)
                if status==258:raise RuntimeError('Restricted process did not exit after termination')
                if status!=0:raise c.WinError(c.get_last_error())
            if self.job:
                while True:
                    accounting=BASIC_ACCOUNTING()
                    self._ok(self.k.QueryInformationJobObject(self.job,1,c.byref(accounting),c.sizeof(accounting),None))
                    if not accounting.active_processes:break
                    if time.monotonic()>=deadline:raise RuntimeError('Restricted process tree did not exit after termination')
                    time.sleep(.01)
            for handle in descendants:
                status=self.k.WaitForSingleObject(handle,max(0,int((deadline-time.monotonic())*1000)))
                if status==258:raise RuntimeError('Restricted descendant did not signal exit after termination')
                if status!=0:raise c.WinError(c.get_last_error())
            self.final_usage=self.usage()
        finally:
            if self.attribute_list:
                self.k.DeleteProcThreadAttributeList(self.attribute_list);self.attribute_list=None
            for handle in reversed(self.handles):self.k.CloseHandle(handle)
            for pointer in reversed(self.allocations):self.k.LocalFree(pointer)

    def usage(self):
        """Actual Job accounting, sampled after process-tree exit when closing."""
        accounting=BASIC_ACCOUNTING();limits=EXTENDED_LIMIT()
        if not self.k.QueryInformationJobObject(self.job,1,c.byref(accounting),c.sizeof(accounting),None):return {'available':False}
        if not self.k.QueryInformationJobObject(self.job,9,c.byref(limits),c.sizeof(limits),None):return {'available':False}
        return {'available':True,'cpu_seconds':(accounting.user+accounting.kernel)/10_000_000,
                'user_cpu_seconds':accounting.user/10_000_000,'kernel_cpu_seconds':accounting.kernel/10_000_000,
                'peak_job_memory_bytes':limits.peak_job,'processes':accounting.total_processes,'source':'Windows Job accounting after tree exit'}
