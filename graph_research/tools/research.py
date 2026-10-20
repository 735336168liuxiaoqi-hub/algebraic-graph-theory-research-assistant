"""Reviewed research workflow definitions shared by manual and model callers."""
from graph_research.graphs.weighted import weighted_graph_spectrum
from graph_research.graphs.classification import graph_class_certificate
from graph_research.workflows.recipes import graph_recipe
from graph_research.workflows.internal_paths import hypergraph_path_analysis
from graph_research.workflows.batch import graph_batch_study
from graph_research.workflows.energy import graph_energy_study
from graph_research.workflows.environment import research_environment
from graph_research.algebra.analysis import symbolic_analysis
from graph_research.algebra.blocks import block_matrix_analysis


def research_tool_definitions(object_schema,graph_args):
    number={'type':'number','minimum':-1000000,'maximum':1000000}
    integer={'type':'integer','minimum':0,'maximum':127}
    expression={'anyOf':[{'type':'number','minimum':-10**12,'maximum':10**12},{'type':'string','minLength':1,'maxLength':1024}]}
    label={'type':['integer','string']}
    labels={'type':'array','items':label,'maxItems':128}
    hyperedges={'type':'array','maxItems':128,'items':{'type':'array','items':label,'minItems':2,'maxItems':128}}
    spec={'type':'object','maxProperties':16}
    parameters={'type':'object','maxProperties':8,'additionalProperties':{'type':'integer','minimum':0,'maximum':128}}
    weight={'anyOf':[number,object_schema({'real':number,'imag':number},['real','imag'])]}
    weighted_edges={'type':'array','maxItems':2048,'items':object_schema({'u':integer,'v':integer,'weight':weight},['u','v','weight'])}
    weighted={'n':{'type':'integer','minimum':1,'maximum':128},'edges':weighted_edges,'directed':{'type':'boolean'},'matrix':{'enum':['A','L','Q','alpha']},'alpha':{'type':'number','minimum':0,'maximum':1},'degree_mode':{'enum':['absolute','sum']},'exact':{'type':'boolean'}}
    sizes={'type':'array','items':{'type':'integer','minimum':1,'maximum':16},'minItems':1,'maxItems':16}
    order={'type':'array','items':{'type':'integer','minimum':0,'maximum':15},'maxItems':16,'uniqueItems':True}
    matrix={'type':'array','minItems':1,'maxItems':16,'items':{'type':'array','minItems':1,'maxItems':16,'items':expression}}
    names={'type':'array','maxItems':8,'uniqueItems':True,'items':{'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_]{0,31}$'}}
    return [
        ('weighted_graph_spectrum','带权/复权图的矩阵与谱',weighted_graph_spectrum,object_schema(weighted,['n','edges'])),
        ('graph_recipe','参数化普通图/超图构造与结构断言',graph_recipe,object_schema({'graph_type':{'enum':['graph','hypergraph']},'base':spec,'steps':{'type':'array','maxItems':16,'items':spec},'parameters':parameters,'assertions':spec},['graph_type','base'])),
        ('hypergraph_path_analysis','超图定向内部路及关联子矩阵',hypergraph_path_analysis,object_schema({'edges':hyperedges,'start':label,'end':label,'edge_indices':{'type':'array','minItems':1,'maxItems':64,'uniqueItems':True,'items':integer},'weights':{'type':'array','items':{'type':'number','exclusiveMinimum':0},'maxItems':128},'weighted_incidence':{'type':'boolean'},'alpha':{'type':'number','minimum':0,'exclusiveMaximum':1}},['edges','start','end'])),
        ('graph_batch_study','批量构图、计算及对照文件',graph_batch_study,object_schema({'cases':{'type':'array','minItems':1,'maxItems':12,'items':object_schema({'name':{'type':'string','minLength':1,'maxLength':80},'graph_type':{'enum':['graph','hypergraph','weighted']},'input':spec,'recipe':spec,'graph_document':{'type':'object','maxProperties':11}},['name'])},'calculations':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,'items':{'enum':['structure','spectrum','charpoly']}},'plot':{'type':'boolean'},'seed':{'type':'integer','minimum':0,'maximum':4294967295}},['cases'])),
        ('symbolic_analysis','符号求和与局部级数',symbolic_analysis,object_schema({'operation':{'enum':['summation','series']},'expression':expression,'variable':{'type':'string','maxLength':32},'parameters':names,'lower':expression,'upper':expression,'center':expression,'order':{'type':'integer','minimum':1,'maximum':16}},['operation','expression'])),
        ('block_matrix_analysis','精确分块及多项式伴随块',block_matrix_analysis,object_schema({'operation':{'enum':['extract','permute','multiply','companion_blocks']},'matrix':matrix,'row_sizes':sizes,'column_sizes':sizes,'row_order':order,'column_order':order,'right':matrix,'polynomials':{'type':'array','minItems':1,'maxItems':8,'items':{'type':'array','minItems':2,'maxItems':9,'items':expression}},'parameters':names},['operation'])),
        ('graph_class_certificate','广义线图判定与构造证书',graph_class_certificate,object_schema({**graph_args,'n':{'type':'integer','minimum':1,'maximum':10},'search_budget':{'type':'integer','minimum':1,'maximum':200000}})),
        ('graph_energy_study','有限参数域的精确能量比较',graph_energy_study,object_schema({'left':spec,'right':spec,'parameter':{'type':'string','maxLength':32},'values':{'type':'array','minItems':1,'maxItems':16,'uniqueItems':True,'items':{'type':'integer','minimum':0,'maximum':128}},'digits':{'type':'integer','minimum':4,'maximum':24}},['left','right'])),
        ('research_environment','三维与TeX可选环境检测',research_environment,object_schema({}))
    ]
