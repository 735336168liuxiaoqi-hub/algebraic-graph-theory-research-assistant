"""Shared cubic primitives for the native editor, SVG and TikZ exports."""
import math
from .document import SchematicDocument,length_parts


def length_tex(value):
    symbol,offset=length_parts(value)
    if symbol is None:return str(offset)
    parts=symbol.split('_');base=parts[0] if len(parts[0])==1 else r'\mathrm{'+parts[0]+'}'
    if len(parts)>1:base+='_{'+','.join(parts[1:])+'}'
    return base+(f'{offset:+d}' if offset else '')


def primitives(scene,vertex_labels=False):
    """Geometry in cm; anchor coordinates are preserved, no topology inferred from containment."""
    data=scene.to_dict() if isinstance(scene,SchematicDocument) else SchematicDocument(scene).to_dict()
    positions={v['id']:v['xy'] for v in data['vertices']};items=[];style=data['style']
    def point(origin,u,n,x,y):return [origin[i]+u[i]*x+n[i]*y for i in (0,1)]
    def path(commands,tag,fill='none',width=.018):items.append({'kind':'path','commands':commands,'tag':tag,'fill':fill,'width':width*style['line_width']/.018,'stroke':style['line_color']})
    def circle(xy,r,tag,role='dot'):items.append({'kind':'circle','xy':xy,'r':r*style['vertex_radius']/.03 if role in ('anchor','junction') else r,'tag':tag,'role':role,'color':style['line_color'] if role=='dot' else style['vertex_color']})
    def ellipse(center,rx,ry,angle,tag,partial=False):
        u=(math.cos(angle),math.sin(angle));n=(-u[1],u[0])
        def q(t):return point(center,u,n,rx*math.cos(t),ry*math.sin(t))
        def arc(a,b):
            s=4/3*math.tan((b-a)/4);pa=q(a);pb=q(b)
            da=[-rx*math.sin(a)*u[i]+ry*math.cos(a)*n[i] for i in (0,1)]
            db=[-rx*math.sin(b)*u[i]+ry*math.cos(b)*n[i] for i in (0,1)]
            return ['C',*[pa[i]+s*da[i] for i in (0,1)],*[pb[i]-s*db[i] for i in (0,1)],*pb]
        if partial:
            for a,b in [(math.radians(110),math.radians(250)),(math.radians(-70),math.radians(70))]:
                middle=(a+b)/2;path([['M',*q(a)],arc(a,middle),arc(middle,b)],tag)
        else:
            commands=[['M',*q(0)]]+[arc(i*math.pi/2,(i+1)*math.pi/2) for i in range(4)]+[['Z']]
            path(commands,tag,style['edge_fill'])
    def dots(a,b,tag):
        for fraction in (.43,.5,.57):circle([a[i]+(b[i]-a[i])*fraction for i in (0,1)],.012,tag)
    def edge(a,b,tag,inner=True):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if data['rank']==2:path([['M',*a],['L',*b]],tag)
        else:ellipse([(a[i]+b[i])/2 for i in (0,1)],length/2+.025,.085,math.atan2(dy,dx),tag)
        if inner and data['rank']!=2:dots(a,b,tag)
    for index,e in enumerate(data['edges']):
        tag=['edge',index];points=[positions[v] for v in e['vertices']]
        if data['rank']==2:edge(points[0],points[1],tag,False);continue
        center=[sum(p[i] for p in points)/len(points) for i in (0,1)]
        if e['shape']=='circle':rx=ry=max(math.dist(center,p) for p in points)+.12;angle=0
        else:
            a,b=max(((a,b) for a in points for b in points),key=lambda pair:math.dist(*pair))
            angle=math.atan2(b[1]-a[1],b[0]-a[0]);u=(math.cos(angle),math.sin(angle));n=(-u[1],u[0])
            coords=[(sum((p[i]-center[i])*u[i] for i in (0,1)),sum((p[i]-center[i])*n[i] for i in (0,1))) for p in points]
            rx=max(abs(p[0]) for p in coords)+.12;ry=max(.12,max(abs(p[1]) for p in coords)+.1)
            factor=max(1,max(math.hypot(x/rx,y/ry) for x,y in coords))*1.02;rx*=factor;ry*=factor
        ellipse(center,rx,ry,angle,tag)
        if e['vertex_ellipsis']:
            if len(points)==2:
                distance=math.dist(*points);axis=[(points[1][i]-points[0][i])/distance for i in (0,1)]
            else:axis=[1,0]
            # Radial clearance inside the rotated ellipse along the dot axis.
            u=(math.cos(angle),math.sin(angle));n=(-u[1],u[0])
            along=sum(axis[i]*u[i] for i in (0,1));across=sum(axis[i]*n[i] for i in (0,1))
            extent=1/math.hypot(along/rx,across/ry);gap=min(.06,extent*.25);radius=min(.012,gap*.3)
            for step in (-1,0,1):circle([center[i]+axis[i]*gap*step for i in (0,1)],radius,tag)
    for index,p in enumerate(data['paths']):
        tag=['path',index];a,b=positions[p['start']],positions[p['end']];length=math.dist(a,b)
        u=[(b[i]-a[i])/length for i in (0,1)];n=[-u[1],u[0]]
        def at(t):return [a[i]+(b[i]-a[i])*t for i in (0,1)]
        if not p['ellipsis']:
            count=p['length']
            for j in range(count):edge(at(j/count),at((j+1)/count),tag,p['vertex_ellipsis'])
            for j in range(1,count):circle(at(j/count),.026,tag,'junction')
        else:
            first,last=p['first_edges'],p['last_edges'];left=.30 if first else 0.;right=.70 if last else 1.
            for j in range(first):edge(at(left*j/first),at(left*(j+1)/first),tag,p['vertex_ellipsis'])
            for j in range(last):edge(at(right+(1-right)*j/last),at(right+(1-right)*(j+1)/last),tag,p['vertex_ellipsis'])
            for j in range(1,first+1):circle(at(left*j/first),.026,tag,'junction')
            for j in range(last):circle(at(right+(1-right)*j/last),.026,tag,'junction')
            aa,bb=at(left),at(right)
            if data['rank']==2:
                path([['M',*aa],['L',*at(left+(right-left)*.20)]],tag)
                path([['M',*at(right-(right-left)*.20)],['L',*bb]],tag)
            else:ellipse(at((left+right)/2),math.dist(aa,bb)/2+.025,.085,math.atan2(u[1],u[0]),tag,True)
            dots(aa,bb,tag)
        if p['brace']!='none':
            side=1 if p['brace']=='left' else -1;normal=[t*side for t in n];offset=p['label_offset'];amp=.065
            def bpoint(x,y):return point(a,u,normal,length*x,offset+y)
            commands=[['M',*bpoint(0,0)]]
            for group in [[(.04,0),(.03,amp),(.15,amp)],[(.42,amp),(.45,amp),(.5,2*amp)],
                          [(.55,amp),(.58,amp),(.85,amp)],[(.97,amp),(.96,0),(1,0)]]:
                commands.append(['C',*[v for xy in group for v in bpoint(*xy)]])
            path(commands,tag,width=.014)
            clearance=abs(normal[0])*(.22+.045*len(str(p['length'])))+abs(normal[1])*.16+.14
            items.append({'kind':'label','xy':bpoint(.5,2*amp+clearance),'text':'P_'+str(p['length']),
                          'tex':'$P_{'+length_tex(p['length'])+'}$','tag':tag,'role':'path_label'})
    for v in data['vertices']:
        circle(v['xy'],.030,['vertex',v['id']],'anchor')
        if vertex_labels:items.append({'kind':'label','xy':[v['xy'][0]+.13,v['xy'][1]+.12], 'text':str(v['id']),'tag':['vertex',v['id']],'role':'vertex_label'})
    # Fill every region before any outline. All three consumers use this order;
    # an edge added later can no longer paint over an earlier edge's boundary.
    layered=[]
    for item in items:
        if item['kind']=='path':
            if item['fill']!='none':layered.append({**item,'stroke':'none','layer':0})
            layered.append({**item,'fill':'none','layer':1})
        else:layered.append({**item,'layer':3 if item['kind']=='label' else 4 if item['role'] in ('anchor','junction') else 2})
    return sorted(layered,key=lambda item:item['layer'])


def bounds(items):
    points=[]
    for item in items:
        if item['kind']=='path':
            for command in item['commands']:
                points.extend(zip(command[1::2],command[2::2]))
        else:
            x,y=item['xy'];pad=item.get('r',.28)
            xpad=max(pad,len(item.get('text',''))*.075) if item['kind']=='label' else pad
            points.extend([(x-xpad,y-pad),(x+xpad,y+pad)])
    if not points:return [-1,-1,1,1]
    return [min(p[0] for p in points)-.18,min(p[1] for p in points)-.18,max(p[0] for p in points)+.18,max(p[1] for p in points)+.18]
