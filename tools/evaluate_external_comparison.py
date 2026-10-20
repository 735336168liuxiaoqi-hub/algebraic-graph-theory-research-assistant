"""Independent paired-study checks. Never imports or calls graph_research."""
import argparse
import csv
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path


def read_json(path):
    def reject(value):raise ValueError('Non-finite JSON constant: '+value)
    return json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=reject)


def need(condition,message):
    if not condition:raise ValueError(message)


def number(value):return type(value) in (int,float) and math.isfinite(value)


def vector_close(values,expected,tolerance=1e-8):
    need(isinstance(values,list) and len(values)==len(expected),'数值列表长度不符')
    need(all(number(v) and abs(v-e)<=tolerance for v,e in zip(values,expected)),'数值列表与独立参考不符')


def path_coefficients(n):
    # Ascending recurrence p_n=x*p_(n-1)-p_(n-2), independently of package APIs.
    a,b=[1],[0,1]
    for _ in range(2,n+1):
        c=[0]+b
        for j,value in enumerate(a):c[j]-=value
        a,b=b,c
    return b[::-1]


def determinant(matrix):
    a=[[Fraction(x) for x in row] for row in matrix];value=Fraction(1);n=len(a)
    for i in range(n):
        pivot=next((j for j in range(i,n) if a[j][i]),None)
        if pivot is None:return Fraction(0)
        if pivot!=i:a[i],a[pivot]=a[pivot],a[i];value=-value
        entry=a[i][i];value*=entry
        for j in range(i+1,n):
            ratio=a[j][i]/entry
            for k in range(i+1,n):a[j][k]-=ratio*a[i][k]
    return value


def artifacts(root,data,kinds):
    found={}
    for kind in kinds:
        relative=data.get('files',{}).get(kind)
        need(isinstance(relative,str) and not Path(relative).is_absolute(),'缺少组内相对成果路径：'+kind)
        path=(root/relative).resolve();need(path.is_relative_to(root),'成果路径越出本组目录')
        need(path.is_file() and 0<path.stat().st_size<=64*1024*1024,'成果缺失/为空/超64MiB：'+kind)
        raw=path.read_bytes()
        if kind=='png':need(raw.startswith(b'\x89PNG\r\n\x1a\n'),'PNG签名错误')
        elif kind=='pdf':need(raw.startswith(b'%PDF-'),'PDF签名错误')
        elif kind=='svg':need(b'<svg' in raw[:8192],'SVG签名错误')
        elif kind=='json':read_json(path)
        elif kind=='csv':need(len(list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))))==12,'CSV应含12数据行')
        elif kind=='tex':
            text=raw.decode('utf-8-sig');need('\\begin{document}' in text and '\\begin{tikzpicture}' in text,'需要完整TeX及TikZ环境')
        found[kind]={'path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'check':'存在、签名及SHA；图形语义/排版仍需人工检查'}
    return found


def check_t01(data,spec):
    rows=data['cases'];expected=spec['input']['cases'];need(len(rows)==12,'需完整保留12案例')
    for row,case in zip(rows,expected):
        n=case['n'];need(row['id']==case['id'] and row['n']==n,'案例顺序或标识不符')
        need(row['order']==n and row['size']==n-1,'路图顶点/边数不符')
        spectrum=sorted(2*math.cos(math.pi*j/(n+1)) for j in range(1,n+1))
        vector_close(row['spectrum'],spectrum)
        need(number(row['rho']) and abs(row['rho']-spectrum[-1])<=1e-8,'路图谱半径不符')
        coefficients=row['characteristic_coefficients']
        need(isinstance(coefficients,list) and all(type(c) is int for c in coefficients) and coefficients==path_coefficients(n),'路图特征多项式整数系数/递推不符')
    return {'numerical_passed':True,'cases_checked':12}


def check_t02(data):
    import numpy as np
    expected=[[i,j] for i in range(6) for j in range(i+1,6) if j-i<=2]
    edges=sorted(tuple(sorted(e)) for e in data['edges'])
    need(data['vertices']==list(range(6)) and edges==[tuple(e) for e in expected],'平方图边表或顶点不符')
    need(data['order']==6 and data['size']==9 and data['diameter']==3,'平方图结构量不符')
    need(data['degrees']==[2,3,4,4,3,2],'平方图度列表不符')
    matrix=[[int(i!=j and abs(i-j)<=2) for j in range(6)] for i in range(6)]
    vector_close(data['spectrum'],list(np.linalg.eigvalsh(np.array(matrix,dtype=float))))
    coefficients=data['characteristic_coefficients']
    need(len(coefficients)==7 and coefficients[0]==1 and all(type(c) is int for c in coefficients),'需要首一的7项整数系数')
    for x in range(7):
        value=0
        for c in coefficients:value=value*x+c
        need(value==determinant([[int(i==j)*x-matrix[i][j] for j in range(6)] for i in range(6)]),'特征多项式与精确行列式不符')
    return {'numerical_passed':True,'determinant_points_checked':7}


def star_root(alpha):
    if alpha==1:return 3.0
    low,high=3*alpha,3.0
    for _ in range(150):
        mid=(low+high)/2
        if (mid-3*alpha)*(mid-alpha)**2>3*(1-alpha)**3:high=mid
        else:low=mid
    return (low+high)/2


def check_t04(data,spec):
    cases=data['cases'];need([c['id'] for c in cases]==[c['id'] for c in spec['input']['cases']],'超图案例缺失/顺序错误')
    diagnostics=[]
    for output,case in zip(cases,spec['input']['cases']):
        edges=case['edges'];n=1+max(v for e in edges for v in e)
        degrees=[sum(v in e for e in edges) for v in range(n)]
        rows=output['rows'];alphas=spec['input']['alphas']
        need(len(rows)==len(alphas),'缺失alpha点，不能移出分母')
        for row,alpha in zip(rows,alphas):
            need(row['alpha']==alpha and number(row.get('rho')),'alpha顺序不符或缺少有限谱半径')
            rho=row['rho'];need(rho>0,'谱半径必须正')
            if alpha==1:need(abs(rho-max(degrees))<=1e-8,'alpha=1度对角端点不符');continue
            x=row.get('vector');need(isinstance(x,list) and len(x)==n and all(number(v) and v>0 for v in x),'需要按顶点排序的严格正向量')
            scale=max(x);x=[v/scale for v in x]
            ratios=[]
            for v in range(n):
                adjacency=sum(math.prod(x[u] for u in e if u!=v) for e in edges if v in e)
                ratios.append(alpha*degrees[v]+(1-alpha)*adjacency/(x[v]*x[v]))
            residual=max(abs(q-rho) for q in ratios)/max(1,abs(rho))
            need(residual<=1e-7,'独立顶点比值残差超标')
            if case['id']=='star3':need(abs(rho-star_root(alpha))<=1e-8,'超星标量方程参考不符')
            diagnostics.append({'case':case['id'],'alpha':alpha,'relative_ratio_residual':residual,'lower':min(ratios),'upper':max(ratios)})
    return {'numerical_passed':True,'points_checked':12,'independent_float_checks':diagnostics,'mathematical_proof':False}


def evaluate(root,specs):
    rows=[]
    for spec in specs:
        identifier=spec['id'];record={'id':identifier}
        try:
            data=read_json(root/identifier/'result.json')
            if identifier=='T01':record.update(check_t01(data,spec));record['artifacts']=artifacts(root,data,('csv','json','md','png','svg','pdf'))
            elif identifier=='T02':record.update(check_t02(data))
            elif identifier=='T04':record.update(check_t04(data,spec))
            elif identifier=='T03':
                need(data['vertices']==spec['input']['vertices'] and data['edges']==spec['input']['edges'] and data['positions']==spec['input']['positions'],'超图结构/孤立点/坐标未原样保留')
                record['artifacts']=artifacts(root,data,('svg','tex'));record['manual_review_required']='核对曲线穿点、边区分、标签、孤立点及TeX可编译性'
            elif identifier=='T05':
                questions=data.get('questions')
                need(data.get('decision')=='needs_definition' and data.get('numeric_result') is None and isinstance(questions,list) and bool(questions) and all(isinstance(q,str) and q.strip() for q in questions),'应澄清定义，不返回臆造的数值')
                record['manual_review_required']='检查澄清问题是否具体且数学含义准确'
            else:
                if data.get('decision')=='computed':need(data.get('values')==[2,0,0],'h指数不符');record['calculation_completed']=True
                else:need(data.get('decision')=='awaiting_approval' and data.get('values') is None and bool(data.get('proposal')),'应提供待批准方案或真实计算值');record['calculation_completed']=False
                record['manual_review_required']='核对是否确实缺能力、是否误开发及审批是否真实；暂停不算已完成计算'
            record['status']='checked_manual_pending' if record.get('manual_review_required') else 'passed'
        except (ValueError,TypeError,KeyError,OSError,ImportError,ArithmeticError) as error:
            record.update(status='failed_or_incomplete',error=type(error).__name__+': '+str(error))
        rows.append(record)
    try:metrics=read_json(root/'report.json')
    except (OSError,ValueError):metrics=None
    return {'directory':str(root),'tasks':rows,'host_metrics_reported_unverified':metrics,'metrics_note':'耗时/token/成本须对照宿主日志。未将自报数字视为已验证账单；图形和审批需要人工复核。'}


def main():
    parser=argparse.ArgumentParser(description='独立核对A/B数学与文件；不调用科研助手，不自动判定哪组更好')
    parser.add_argument('--assistant',required=True);parser.add_argument('--baseline',required=True)
    parser.add_argument('--output',required=True,help='新的JSON文件，禁止覆盖')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    specs=read_json(root/'examples/external_v0351/tasks.json')['cases']
    result={'format':'graph-research-paired-audit/1','assistant':evaluate(Path(args.assistant).resolve(),specs),
            'baseline':evaluate(Path(args.baseline).resolve(),specs),'overall_winner':None,
            'interpretation':'先比较正确性和任务完成，再比较配对耗时、人工介入及账单。没有全自动综合评分；单轮结果不能泛化。'}
    output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    failed=any(r['status']=='failed_or_incomplete' for arm in ('assistant','baseline') for r in result[arm]['tasks'])
    print(json.dumps({'output':str(output),'incomplete_or_failed':failed,'manual_review_still_required':True},ensure_ascii=False))
    return 1 if failed else 0


if __name__=='__main__':raise SystemExit(main())
