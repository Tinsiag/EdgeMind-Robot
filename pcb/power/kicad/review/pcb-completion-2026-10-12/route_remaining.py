"""按实际铜几何补全连接；输出经几何间距检查的 45 度路径。

运行环境：numpy/scipy/shapely。新增路径最终仍由 KiCad DRC 复核。
"""
import sys,json,math,heapq,time
import numpy as np
try:
    from scipy.ndimage import distance_transform_edt
except ImportError:
    def distance_transform_edt(mask):
        yy,xx=np.where(~mask);Y,X=np.indices(mask.shape)
        dx=np.maximum(np.maximum(xx.min()-X,X-xx.max()),0)
        dy=np.maximum(np.maximum(yy.min()-Y,Y-yy.max()),0)
        return np.maximum(dx,dy)+(math.sqrt(2)-1)*np.minimum(dx,dy)
from shapely import contains_xy,intersects_xy,prepare
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union
from shapely.ops import nearest_points

D=json.load(open(sys.argv[1])); items=[];result={'tracks':[],'vias':[]}
def polygons(ps):return unary_union([Polygon(p['outer'],p['holes']) for p in ps])
for p in D['pads']:
    items.append(dict(g=polygons(p['polys']),net=p['net'],layers=p['layers'],kind='pad',id=p['uuid'],ref=p['ref']+':'+p['num'],data=p))
for t in D['tracks']:
    items.append(dict(g=Point(t['start']).buffer(t['width']/2) if t['via'] else LineString([t['start'],t['end']]).buffer(t['width']/2),net=t['net'],layers=t['layers'],kind='via' if t['via'] else 'track',id=t['uuid'],data=t))
for z in D['zones']:
    for l,ps in z['filled'].items():
        for p in ps:
            items.append(dict(g=Polygon(p['outer'],p['holes']),net=z['net'],layers=[int(l)],kind='zone',id='zone',data=z))

def groups(net):
    nodes=[]
    for l in [0,2]:
        g=unary_union([a['g'].buffer(.0001) for a in items if a['net']==net and l in a['layers']])
        ps=list(g.geoms) if hasattr(g,'geoms') else [g]
        nodes.extend([(l,p) for p in ps if not p.is_empty])
    parent=list(range(len(nodes)))
    def root(i):
        while i!=parent[i]:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for a in items:
        if a['net']!=net or a['layers']!=[0,2] or a['kind']=='zone':continue
        links=[i for i,(l,g) in enumerate(nodes) if g.intersects(a['g'])]
        for i in links[1:]:parent[root(i)]=root(links[0])
    out=[]
    for r in sorted({root(i) for i in range(len(nodes))}):
        ns=[nodes[i] for i in range(len(nodes)) if root(i)==r]
        gs={l:unary_union([p for x,p in ns if x==l]) for l in [0,2]}
        refs=[a['ref'] for a in items if 'ref' in a and a['net']==net and any(gs[l].intersects(a['g']) for l in a['layers'])]
        out.append((gs,refs))
    return out

def anchor(net,ref=None,point=None,layer=None,whole=False):
    if ref:
        a=next(a for a in items if a.get('ref')==ref and a['net']==net)
        gs={l:a['g'] if l in a['layers'] else Polygon() for l in [0,2]}
    else:gs={l:Point(point).buffer(.31) if layer is None or l==layer else Polygon() for l in [0,2]}
    if whole:
        for gg,refs in groups(net):
            if any(gg[l].intersects(gs[l]) for l in [0,2]):return gg
        raise ValueError(('missing island',net,ref,point))
    return gs

def route(net,src,dst,width=.25,step=.1,via_size=.6,drill=.3,via_cost=12,front_cost=1,rear_cost=2.3,layers=[0,2],label='',ripup=False):
    stamp=time.time();print('ROUTE',net,label,'width',width,flush=True)
    x0,y0,x1,y1=D['outline'];xs=np.arange(math.ceil((x0+.5+width/2)/step)*step,x1-.5-width/2,step);ys=np.arange(math.ceil((y0+.5+width/2)/step)*step,y1-.5-width/2,step)
    X,Y=np.meshgrid(xs,ys);ny,nx=X.shape;N=nx*ny
    soft=[a for a in items if ripup and a['net']!=net and a['id']!='new' and a['kind'] in ['track','via'] and (a['net']=='GND' or (a['data']['width']<=.65 and a['net'] not in ['VM_SWITCHED','VM_R','VM_L','VLOGIC_IN','BAT_POS','VBAT_SYS']))]
    softids={a['id'] for a in soft}
    copper={l:unary_union([a['g'] for a in items if a['net']!=net and a['id'] not in softids and l in a['layers'] and not(a['kind']=='zone' and a['net']=='GND')]) for l in [0,2]}
    clearance=.205
    # Extra half-cell diagonal margin makes every raster step safe, including
    # a diagonal between two free cell centres beside a rounded obstacle.
    margin=.012
    blocked=[];starts=[];ends=[]
    for l in [0,2]:
        obstacles=copper[l].buffer(width/2+clearance+margin);prepare(obstacles)
        blocked.append(contains_xy(obstacles,X,Y) if l in layers else np.ones(X.shape,dtype=bool))
        starts.append(intersects_xy(src[l],X,Y));ends.append(intersects_xy(dst[l],X,Y))
    blocked=np.array(blocked);starts=np.array(starts)&~blocked;ends=np.array(ends)&~blocked
    if not starts.any() or not ends.any():
        print('NO ENDPOINT CELLS',starts.sum(),ends.sum(),flush=True);return False
    foreign=unary_union(list(copper.values())).buffer(via_size/2+clearance+margin)
    via_avoid=[foreign]
    for a in items:
        if a['kind']=='pad':via_avoid.append(a['g'].buffer(via_size/2+.1))
        if a['kind']=='via' and a['id'] not in softids:
            t=a['data'];via_avoid.append(Point(t['start']).buffer((t.get('drill',t['width']/2)+drill)/2+.255))
    vg=unary_union(via_avoid);prepare(vg)
    via_free=~contains_xy(vg,X,Y)&~blocked[0]&~blocked[1]
    via_free &= (X>x0+.5+via_size/2)&(X<x1-.5-via_size/2)&(Y>y0+.5+via_size/2)&(Y<y1-.5-via_size/2)
    penalty=np.zeros((2,ny,nx))
    for li,l in enumerate([0,2]):
        sg=unary_union([a['g'] for a in soft if l in a['layers']]).buffer(width/2+clearance+.02)
        penalty[li]=contains_xy(sg,X,Y)*5
    pf=penalty.ravel()
    h=distance_transform_edt(~(ends[0]|ends[1]))*step
    dist=np.full(2*N,np.inf);parent=np.full(2*N,-1,np.int32);closed=np.zeros(2*N,bool);heap=[]
    for s in np.flatnonzero(starts):dist[s]=0;heap.append((h.flat[s%N],int(s)))
    heapq.heapify(heap);goals=ends.ravel();bflat=blocked.ravel();vf=via_free.ravel();hf=h.ravel()
    offsets=[(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    costs=[front_cost,rear_cost];found=-1;visited=0
    while heap:
        f,i=heapq.heappop(heap)
        if closed[i]:continue
        if goals[i]:found=i;break
        closed[i]=True;visited+=1;l=i//N;q=i%N;y,x=divmod(q,nx);g=dist[i]
        for dy,dx in offsets:
            xx=x+dx;yy=y+dy
            if xx<0 or xx>=nx or yy<0 or yy>=ny:continue
            j=i+dy*nx+dx
            if bflat[j] or closed[j]:continue
            ng=g+step*(1.4142135623730951 if dx and dy else 1)*(costs[l]+pf[j])
            if ng+1e-9<dist[j]:dist[j]=ng;parent[j]=i;heapq.heappush(heap,(ng+hf[j%N],j))
        if vf[q]:
            j=(1-l)*N+q
            if not closed[j] and g+via_cost<dist[j]:dist[j]=g+via_cost;parent[j]=i;heapq.heappush(heap,(g+via_cost+hf[q],j))
    if found<0:print('NO PATH',visited,'states',round(time.time()-stamp,1),'s',flush=True);return False
    path=[];i=found
    while i>=0:
        l=i//N;y,x=divmod(i%N,nx);path.append((l,round(float(xs[x]),5),round(float(ys[y]),5)));i=parent[i]
    path.reverse();newtracks=[];newvias=[]
    # Snap the two ends to real existing copper. Raster cells are only search
    # guides; leaving an end at the cell centre creates an apparent dangling
    # stub even when the cell overlaps a pad or track by a fraction of a mm.
    for end_idx, geom in [(0,src),(len(path)-1,dst)]:
        li=path[end_idx][0]; g=geom[[0,2][li]]
        if not g.is_empty:
            q=nearest_points(g,Point(path[end_idx][1:]))[0]
            path[end_idx]=(li,float(q.x),float(q.y))
    chunks=[];chunk=[path[0]]
    for p in path[1:]:
        if p[0]!=chunk[-1][0]:
            chunks.append(chunk);chunk=[p];newvias.append({'net':net,'start':list(p[1:]),'width':via_size,'drill':drill,'layers':[0,2],'via':True})
        else:chunk.append(p)
    chunks.append(chunk)
    for chunk in chunks:
        # Compress collinear lattice steps; all corners remain 45 or 90 degrees.
        pts=[chunk[0]]
        for j in range(1,len(chunk)-1):
            a,c,d=chunk[j-1],chunk[j],chunk[j+1]
            if abs((c[1]-a[1])*(d[2]-c[2])-(c[2]-a[2])*(d[1]-c[1]))>1e-7:pts.append(c)
        if len(chunk)>1:pts.append(chunk[-1])
        # Remove raster staircases with clear 45-degree shortcuts.
        simple=[pts[0]];i=0
        while i<len(pts)-1:
            chosen=None
            for j in range(len(pts)-1,i,-1):
                a,c=pts[i],pts[j];dx=c[1]-a[1];dy=c[2]-a[2];m=min(abs(dx),abs(dy));sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
                for mid in [(a[0],a[1]+sx*m,a[2]+sy*m),(a[0],c[1]-sx*m,c[2]-sy*m)]:
                    seq=[a,mid,c];g=LineString([q[1:] for q in seq]).buffer(width/2)
                    if g.distance(copper[[0,2][a[0]]])<.205:continue
                    if ripup and any(g.distance(z['g'])<.205 for z in soft if [0,2][a[0]] in z['layers']):continue
                    chosen=(j,mid,c);break
                if chosen:break
            if chosen:
                j,mid,c=chosen
                if mid!=simple[-1]:simple.append(mid)
                if c!=simple[-1]:simple.append(c)
                i=j
            else:i+=1;simple.append(pts[i])
        for a,c in zip(simple,simple[1:]):
            t={'net':net,'start':list(a[1:]),'end':list(c[1:]),'width':width,'layers':[[0,2][a[0]]],'via':False}
            g=LineString([t['start'],t['end']]).buffer(width/2)
            assert g.distance(copper[t['layers'][0]])>=.2-1e-6
            newtracks.append(t)
    cuts=[]
    for a in soft:
        for t in newtracks+newvias:
            g=Point(t['start']).buffer(t['width']/2) if t['via'] else LineString([t['start'],t['end']]).buffer(t['width']/2)
            if set(a['layers'])&set(t['layers']) and g.distance(a['g'])<.21:
                cuts.append(a);break
    if cuts:
        result.setdefault('remove',[]).extend(a['id'] for a in cuts)
        result.setdefault('reroute_nets',[]).extend(sorted({a['net'] for a in cuts}))
        for a in cuts:items.remove(a)
        print('RIP',len(cuts),'items',sorted({a['net'] for a in cuts}),flush=True)
    for t in newtracks+newvias:
        g=Point(t['start']).buffer(t['width']/2) if t['via'] else LineString([t['start'],t['end']]).buffer(t['width']/2)
        items.append(dict(g=g,net=net,layers=t['layers'],kind='via' if t['via'] else 'track',id='new',data=t))
    result['tracks'].extend(newtracks);result['vias'].extend(newvias)
    print('DONE',len(newtracks),'segments',len(newvias),'vias;',visited,'states;',round(time.time()-stamp,1),'s',flush=True)
    json.dump(result,open(sys.argv[2],'w'),indent=2)
    return True

if __name__=='__main__':
    if len(sys.argv)>3 and sys.argv[3]=='report':
        for n in sorted({a['net'] for a in items}):
            gs=groups(n)
            if len(gs)>1:print(n,len(gs),[(r,[round(g[l].area,2) for l in [0,2]]) for g,r in gs])
        sys.exit()
    # Main motor bus connects the two independent shunt input via banks.
    net='VM_SWITCHED'
    route(net,anchor(net,point=(57.2375,94.8)),anchor(net,point=(90.2375,94.8)),3,step=.2,via_size=1.2,drill=.6,via_cost=35,rear_cost=1.3,label='两路分流电阻输入主干')
    # Low-profile support signals are allowed under the raised driver modules.
    net='Net-(U12A-~{R})';route(net,anchor(net,ref='U10:11',whole=True),anchor(net,ref='U12:1',whole=True),label='复位信号')
    for net,u,r in [('USB1_FAULT_PULSE_N','U7:7','R66:2'),('USB2_FAULT_PULSE_N','U8:7','R68:2')]:
        route(net,anchor(net,ref=u,whole=True),anchor(net,ref=r,whole=True),step=.075,label='USB 故障输出')
    # Wide power paths terminate at reservoir capacitors/module supply pads.
    for net,a,c,w in [('VLOGIC_IN','C101:1','C8:1',1.5),('VLOGIC_IN','C1:1','C108:1',1.2),
                      ('+5V_FPGA','C4:1','Q8:2',1.2),('VM_L','R84:2','U2:9',2),
                      ('VM_R','R94:2','U4:6',2),('VM_R','U4:6','U4:9',2),
                      ('VM_R','U4:9','C131:1',2),('VM_R','C131:1','J17:1',2)]:
        # The shunt can enter the rear through its three already-placed vias.
        if a in ['R84:2','R94:2']:
            pt=(66.7625,94.8) if a=='R84:2' else (99.7625,94.8)
            src=anchor(net,point=pt)
        else:src=anchor(net,ref=a)
        route(net,src,anchor(net,ref=c),w,step=.15,via_size=1.2,drill=.6,via_cost=25,rear_cost=1.35,label=a+' → '+c)
    # These are voltage-sense branches, not motor current conductors.
    for net,a,c in [('VM_L','R78:1','R84:2'),('VM_R','R80:1','R94:2')]:
        route(net,anchor(net,ref=a,whole=True),anchor(net,ref=c,whole=True),.3,label='采样支线')
