"""Desktop data operations using the existing protected offline sessions."""
import copy
import json
from pathlib import Path
import shutil
import uuid

from graph_research.assistant.offline import OfflineToolSession,grouped_tools
from graph_research.assistant.results import _execution,verify_bundle
from graph_research.runtime.storage import safe_path,write_json,read_json,staged_file,StateRecoveryError
from graph_research.tools.change_control import external_directory


class DesktopWorkspace:
    RESULT_MODE='offline'
    def __init__(self,directory,*,session_directory=None,tool_directory=None,graph_directory=None,results_preferences=None):
        self.directory=external_directory(directory)
        from graph_research.assistant.result_catalog import ResultPreferences
        self.results_preferences=results_preferences or ResultPreferences(self.directory/'results-preferences.json',self.directory/'成果')
        self.tool_directory=external_directory(tool_directory or self.directory/'tool_packages')
        from graph_research.graph_input import GraphLibrary
        self.graph_library=GraphLibrary(graph_directory or self.directory/'graph-library')
        self.session=None
        self.recovery_warning=None
        if session_directory is not None:self.open_session(session_directory)
        else:
            try:
                index,_=read_json(self.directory/'desktop.json',max_bytes=16384)
                name=index['last_session']
                if not isinstance(name,str) or not name.startswith('session_') or len(name)!=20 or any(c not in '0123456789abcdef' for c in name[8:]):raise ValueError('Invalid session index')
                path=safe_path(self.directory/name,root=self.directory)
                if not (path/'session.json').is_file():raise ValueError('No saved session')
                self.open_session(path)
            except StateRecoveryError as exc:
                self.recovery_warning=str(exc);self.new_session()
            except (OSError,ValueError,KeyError):self.new_session()

    def _bind(self,session):
        if session.results_directory is None:session.results_directory=self.results_preferences.active;session.results_mode=self.RESULT_MODE
        self.results_preferences.remember(session.results_directory)
        self.session=session
        registry=session._registry()
        self.registry=registry;self.groups=grouped_tools(registry)
        if session.directory.parent==self.directory:
            write_json(self.directory/'desktop.json',{'version':1,'last_session':session.directory.name})
        return session

    def new_session(self):
        return self._bind(OfflineToolSession(self.directory/('session_'+uuid.uuid4().hex[:12]),self.tool_directory,results_directory=self.results_preferences.active))

    def refresh_tools(self):
        registry=self.session._registry();self.registry=registry;self.groups=grouped_tools(registry)
        return self.groups

    def open_session(self,directory):
        return self._bind(OfflineToolSession(directory,results_directory=self.results_preferences.active))

    def history(self):return copy.deepcopy(self.session.state.get('observations',[]))

    def artifacts(self,observation):
        if not observation.get('ok'):return []
        if not observation.get('execution'):return []
        _,_,attachments,_=_execution(self.session,observation,'desktop',False,[])
        return list(dict.fromkeys(item.path for item in attachments.values()))

    def export_bundle(self,destination):
        bundle=self.session.result_bundle or self.session.export_results()
        if self.session.results_directory:
            from graph_research.assistant.result_catalog import resolve_bundle
            bundle=resolve_bundle(bundle,source_directory=self.session.directory,results_root=self.session.results_directory)
            if bundle.get('availability','ready')!='ready':raise ValueError('成果包当前不可用，请在成果中心查看或恢复。')
        verify_bundle(bundle['archive'],bundle['sha256'])
        source=Path(bundle['archive']);target=safe_path(destination)
        if source.resolve()==target:return target
        with staged_file(target,overwrite=True) as temporary:
            shutil.copyfile(source,temporary)
            verify_bundle(temporary,bundle['sha256'])
        return target

    def save_record(self,observation,destination):
        target=safe_path(destination)
        with staged_file(target,overwrite=True) as temporary:
            temporary.write_text(json.dumps(observation,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        return target
