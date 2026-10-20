"""Small reproducible batches with full case records and optional contact sheets."""
import csv
import io
import json
from pathlib import Path
import time
import uuid
from graph_research.errors import PathBoundaryError
from graph_research.runtime.integrity import IntegrityError
from graph_research.runtime.storage import safe_path,atomic_text,staged_file,io_path,storage_error
from graph_research.runtime.observability import timed,measure

import networkx as nx
from jsonschema import ValidationError
from graph_research import graphs as gg,hypergraphs as hg
from graph_research.workflows.recipes import build_recipe,graph_recipe


def _case(case):
    graph_type=case.get('graph_type','graph')
    if ('recipe' in case)==('input' in case):raise ValueError('每项须且仅须提供input或recipe。')
    if 'recipe' in case:
        recipe=dict(case['recipe'])
        if recipe.get('graph_type',graph_type)!=graph_type:raise ValueError('case和recipe的graph_type必须一致。')
        recipe['graph_type']=graph_type
        graph,trace=build_recipe(**recipe)
        specification=graph_recipe(**recipe)
        return graph_type,graph,specification
    spec=case.get('input')
    if not isinstance(spec,dict):raise ValueError('每项需要input或recipe对象。')
    if graph_type=='graph':
        from graph_research.tools.registry import GRAPH_ARGS,object_schema
        import jsonschema
        jsonschema.validate(spec,object_schema(GRAPH_ARGS,['kind','n']))
        return graph_type,gg.make_graph(**spec),spec
    if graph_type=='weighted':
        from graph_research.graphs.weighted import weighted_matrices
        weighted_matrices(**spec)
        return graph_type,None,spec
    if graph_type=='hypergraph':
        if set(spec)-{'edges','vertices','weights'}:raise ValueError('超图input仅接受edges/vertices/weights。')
        if len(spec.get('vertices',[]))>128 or len(spec.get('edges',[]))>128 or sum(map(len,spec.get('edges',[])))>2048:raise ValueError('超图超过预算。')
        h=hg.Hypergraph(**spec)
        if h.order()>128:raise ValueError('超图至多128顶点。')
        return graph_type,h,spec
    raise ValueError('graph_type为graph/hypergraph/weighted。')


@timed('artifact_export')
def _plot_batch(drawings,output,seed):
    from matplotlib.figure import Figure
    from graph_research.rendering.presentation import plot_document
    from graph_research.rendering.fonts import label_font_families
    figure=Figure(figsize=(10,3.6*((len(drawings)+1)//2)));paths={}
    for index,(name,graph) in enumerate(drawings):
        ax=figure.add_subplot((len(drawings)+1)//2,2,index+1)
        plot_document(graph,seed=seed,legend=False,ax=ax)
        ax.set_title(name,fontfamily=label_font_families(name))
    figure.tight_layout();errors={}
    for ext in ('png','svg','pdf'):
        path=output/('graphs.'+ext)
        try:
            with staged_file(path,root=Path.cwd()/'outputs') as temporary:
                with temporary.open('wb') as stream:figure.savefig(stream,format=ext,dpi=160,facecolor='white')
            paths[ext]=str(path)
        except PathBoundaryError:raise
        except OSError as error:errors[ext]=storage_error(error,'export_'+ext)
    return paths,errors


def graph_batch_study(cases,calculations=None,plot=False,seed=42):
    """Keep failures per case; exports are in a fresh outputs directory.

    Hypergraph spectra remain Perron-only. Batch does not generate algorithms,
    invoke a model, or manufacture individual worker receipts for its cases.
    """
    calculations=list(calculations or ['structure','spectrum'])
    if not 1<=len(cases)<=12 or not calculations or len(set(calculations))!=len(calculations) or set(calculations)-{'structure','spectrum','charpoly'}:
        raise ValueError('批量1..12项，计算选structure/spectrum/charpoly且不能重复。')
    from graph_research.tools.registry import json_value
    rows=[];drawings=[];budget=0
    for index,case in enumerate(cases):
        started=time.monotonic();record={'case':index+1,'name':case.get('name',f'case {index+1}'),'input':case,'results':{},'errors':{}}
        try:
            kind,graph,spec=_case(case);order=spec['n'] if kind=='weighted' else graph.order()
            budget+=order
            if budget>512:raise ValueError('本批累计顶点数超过512。')
            record['resolved_input']=spec
            for operation in calculations:
                try:
                    if kind=='weighted':
                        from graph_research.graphs.weighted import weighted_graph_spectrum
                        if operation=='structure':value={'order':order,'size':len(spec['edges']),'directed':spec.get('directed',False)}
                        else:value=weighted_graph_spectrum(**spec,exact=operation=='charpoly')
                    elif kind=='graph':
                        if operation=='structure':value={'order':order,'size':graph.number_of_edges(),'degrees':[d for _,d in graph.degree()],'components':nx.number_connected_components(graph)}
                        elif operation=='charpoly':
                            if order>8:raise ValueError('批量精确多项式限8顶点。')
                            value={'polynomial':str(gg.exact_characteristic_polynomial(graph).as_expr())}
                        else:
                            import numpy as np
                            matrix=nx.to_numpy_array(graph);spectrum=np.linalg.eigvalsh(matrix)
                            value={'spectrum':spectrum,'rho':float(max(abs(spectrum),default=0)),'energy':float(sum(abs(spectrum)))}
                    elif operation=='structure':value={'order':order,'size':graph.size(),'rank':graph.rank,'uniform':graph.is_uniform(),'degrees':[graph.degree(v) for v in graph.vertices()]}
                    elif operation=='charpoly':raise ValueError('批量不执行超图张量消元；请单独调用有规模估计的消元工具。')
                    else:value=graph.alpha_spectrum(0)
                    record['results'][operation]=json_value(value)
                except (ValueError,ArithmeticError,TypeError) as error:record['errors'][operation]=str(error)
            try:
                from graph_research.graph_input.document import from_hypergraph,from_networkx
                from graph_research.graph_input.document import document
                if kind=='weighted':
                    drawing=document(list(range(spec['n'])),[{'vertices':[e['u'],e['v']],'weight':e['weight']} for e in spec['edges']],directed=spec.get('directed',False),weighted=True,name=record['name'])
                elif kind=='graph' and 'graph_spec' in spec:
                    from graph_research.graph_input.adapters import result_graph
                    drawing=result_graph({'tool':'graph_recipe','ok':True,'arguments':case['recipe'],'result':spec})
                else:drawing=from_hypergraph(graph) if kind=='hypergraph' else from_networkx(graph)
                if 'graph_document' in case:
                    from graph_research.graph_input.document import GraphDocument,same_numbered_structure
                    original=GraphDocument(case['graph_document'])
                    if not same_numbered_structure(original,drawing):raise ValueError('批量图对象与实际计算结构或原权重不一致。')
                    drawing=original
                record['graph_document']=drawing.to_dict()
                if plot:drawings.append((record['name'],drawing))
            except (ValueError,TypeError,KeyError) as error:
                record['preview_error']=str(error)
                if plot:record['errors']['plot']=str(error)
        except (ValueError,TypeError,KeyError,ValidationError) as error:record['errors']['construction']=str(error)
        record['status']='partial' if record['results'] and record['errors'] else 'failed' if record['errors'] else 'complete'
        record['elapsed_seconds']=time.monotonic()-started;rows.append(record)
    output=safe_path(Path.cwd()/'outputs'/'batch-studies'/uuid.uuid4().hex[:16])
    status='complete' if all(row['status']=='complete' for row in rows) else 'partial' if any(row['results'] for row in rows) else 'failed'
    math_complete=all(len(row['results'])==len(calculations) and not any(key!='plot' for key in row['errors']) for row in rows)
    result={'status':status,'calculation_status':'complete' if math_complete else 'partial' if any(row['results'] for row in rows) else 'failed',
            'export_status':'complete','case_count':len(rows),'rows':rows,'files':{},
            'interpretation':'逐项保留输入、实际构图、计算结果及失败原因；导出状态独立报告，数值谱不是数学证明。'}
    files=result['files']
    def failed(key,error):
        result.setdefault('export_errors',{})[key]=storage_error(error,'export_'+key)
        result['export_status']='partial' if files else 'failed'
        result['status']='partial' if any(row['results'] for row in rows) else 'failed'
    try:io_path(output).mkdir(parents=True)
    except PathBoundaryError:raise
    except OSError as error:
        failed('directory',error);return result
    if drawings:
        try:
            pictures,errors=_plot_batch(drawings,output,seed);files.update(pictures)
            for kind,error in errors.items():
                result.setdefault('export_errors',{})[kind]=error;result['status']='partial' if any(row['results'] for row in rows) else 'failed'
        except (PathBoundaryError,IntegrityError):raise
        except (ImportError,ValueError,RuntimeError,OSError) as error:
            failed('plot',error)
    if any('plot' in row['errors'] for row in rows):
        result.setdefault('export_errors',{})['plot']={'code':'plot_input_not_representable','phase':'export_plot','retryable':False}
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n');writer.writerow(['case','name','status','order','size','rho','energy','polynomial','errors'])
    markdown=['# 批量图计算对照','','| 序号 | 名称 | 状态 | 顶点 | 边 | 谱半径 | 能量 |','| --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        data={k:v for item in row['results'].values() for k,v in item.items()}
        name=row['name'];safe_name="'"+name if name.lstrip().startswith(('=','+','-','@')) else name
        writer.writerow([row['case'],safe_name,row['status'],data.get('order',''),data.get('size',''),data.get('rho',''),data.get('energy',''),data.get('polynomial',''),json.dumps(row['errors'],ensure_ascii=False)])
        escaped=name.replace('|','\\|').replace('\n',' ')
        markdown.append('| '+' | '.join(map(str,[row['case'],escaped,row['status'],data.get('order','—'),data.get('size','—'),data.get('rho','—'),data.get('energy','—')]))+' |')
    for ext,content in [('csv',stream.getvalue()),('md','\n'.join(markdown)+'\n')]:
        path=output/('comparison.'+ext)
        try:
            with measure('export.'+ext):atomic_text(path,content,root=Path.cwd()/'outputs')
            files[ext]=str(path)
        except PathBoundaryError:raise
        except OSError as error:failed(ext,error)
    result['export_status']='partial' if result.get('export_errors') else 'complete'
    path=output/'results.json';files['json']=str(path)
    try:
        with measure('export.json'):atomic_text(path,json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),root=Path.cwd()/'outputs')
    except PathBoundaryError:raise
    except OSError as error:files.pop('json',None);failed('json',error)
    return result
