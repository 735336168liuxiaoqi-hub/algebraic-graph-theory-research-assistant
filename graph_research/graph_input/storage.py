"""A local user graph library with generated identifiers and atomic snapshots."""
import re
import uuid
from graph_research.runtime.storage import safe_path,read_json,write_json,atomic_text
from .document import GraphDocument,GraphInputError,MAX_TEXT


class GraphLibrary:
    def __init__(self,directory):self.directory=safe_path(directory)

    def save(self,graph,name=None):
        if not isinstance(graph,GraphDocument):raise GraphInputError('需要经过验证的图对象。')
        if name is not None:graph=graph.with_updates(name=name)
        from itertools import islice
        if len(list(islice((self.directory/'objects').glob('*.json'),512)))>=512:raise GraphInputError('图对象库最多512项，请先整理文件夹。')
        identifier=uuid.uuid4().hex;path=self.directory/'objects'/(identifier+'.json')
        atomic_text(path,graph._serialized)
        return identifier

    def load(self,identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[0-9a-f]{32}',identifier):raise GraphInputError('图对象标识无效。')
        path=safe_path(self.directory/'objects'/(identifier+'.json'),root=self.directory)
        data,_=read_json(path,max_bytes=MAX_TEXT)
        return GraphDocument(data)

    def entries(self):
        result=[];folder=self.directory/'objects'
        if not folder.exists():return result
        for path in sorted(folder.glob('*.json'),key=lambda p:p.name):
            if len(result)>=512:raise GraphInputError('图对象库超过512项，请先整理文件夹。')
            try:
                graph=self.load(path.stem)
                result.append({'id':path.stem,'name':graph.name,'summary':graph.summary()+(' · 含构图配方' if graph.to_dict().get('recipe') else ''),'valid':True})
            except (ValueError,OSError) as error:
                result.append({'id':path.stem,'name':'无法读取的图','summary':str(error),'valid':False})
        return result

    def set_current(self,graph):
        write_json(self.directory/'current.json',graph.to_dict(),backup=True)

    def current(self):
        path=self.directory/'current.json'
        if not path.exists():return None
        data,_=read_json(path,recover=True,max_bytes=MAX_TEXT)
        return GraphDocument(data)

    def export(self,graph,path,*,overwrite=False):
        return atomic_text(path,graph._serialized+'\n',overwrite=overwrite)
