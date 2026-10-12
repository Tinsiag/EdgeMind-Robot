"""Choose short local ground vias with native polygon clearance checks.

Runs in Python with shapely; does not edit the board. Outputs checked proposals.
"""
import json,sys,math
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
D=json.load(open(sys.argv[1]));items=[];allpads=[]
for p in D['pads']:
    g=unary_union([Polygon(x['outer'],x['holes']) for x in p['polys']]);p['geom']=g
    items.append((g,p['net'],p['layers'],'pad'));allpads.append(g)
for t in D['tracks']:
    g=Point(t['start']).buffer(t['width']/2) if t['via'] else LineString([t['start'],t['end']]).buffer(t['width']/2)
    items.append((g,t['net'],t['layers'],'via' if t['via'] else 'track'))
for z in D['zones']:
    for layer,polys in z['filled'].items():
        if polys:items.append((unary_union([Polygon(p['outer'],p['holes']) for p in polys]),z['net'],[int(layer)],'zone'))
tree=STRtree([i[0] for i in items]);pad_tree=STRtree(allpads)
def clear(g,layers,net='GND',clearance=.205):
    search=g.buffer(clearance)
    for i in tree.query(search):
        a,n,ls,typ=items[int(i)]
        if n!=net and set(ls)&set(layers) and a.distance(g)<clearance:return False
    return True
proposals=[];failed=[]
existing=[Point(t['start']) for t in D['tracks'] if t['via'] and t['net']=='GND']
for p in D['pads']:
    if p['net']!='GND' or 2 in p['layers']:continue
    x,y=p['pos'];candidates=[]
    # 45-degree exits are preferred, with extra directions only as fallback.
    for dist in [.9,1.1,1.3,1.5,1.8,2.1,2.5,3.0]:
        for a in range(0,360,45):
            q=(round(x+math.cos(math.radians(a))*dist,4),round(y+math.sin(math.radians(a))*dist,4))
            disk=Point(q).buffer(.3);trace=LineString([(x,y),q]).buffer(.15)
            if any(allpads[int(i)].distance(disk)<.10 for i in pad_tree.query(disk.buffer(.10))):continue
            if not clear(disk,[0,2]) or not clear(trace,[0]):continue
            if not (D['outline'][0]+.8<q[0]<D['outline'][2]-.8 and D['outline'][1]+.8<q[1]<D['outline'][3]-.8):continue
            if any(Point(q).distance(v)<.8 for v in existing):continue
            candidates.append((dist,q));break
        if candidates:break
    if not candidates:failed.append(p['ref']+':'+p['num']);continue
    _,q=min(candidates);proposals.append({'ref':p['ref'],'pad':p['num'],'start':p['pos'],'via':q,'net':'GND','width':.3,'diameter':.6,'drill':.3});existing.append(Point(q))
json.dump({'vias':proposals,'failed':failed},open(sys.argv[2],'w'),ensure_ascii=False,indent=2)
print('Ground fanout:',len(proposals),'placed;',len(failed),'require remaining routing:',failed)
