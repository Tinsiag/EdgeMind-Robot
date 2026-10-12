"""Export native copper geometry for deterministic routing/preview checks."""
import sys,json
from pathlib import Path
import pcbnew as k
def xy(p):return [k.ToMM(p.x),k.ToMM(p.y)]
def polys(s):
    return [{'outer':[xy(s.COutline(i).CPoint(j)) for j in range(s.COutline(i).PointCount())],
             'holes':[[xy(s.CHole(i,h).CPoint(j)) for j in range(s.CHole(i,h).PointCount())] for h in range(s.HoleCount(i))]} for i in range(s.OutlineCount())]
b=k.LoadBoard(sys.argv[1]);d={'pads':[],'tracks':[],'zones':[],'parts':[],'outline':[]}
bb=b.GetBoardEdgesBoundingBox()
d['outline']=[k.ToMM(bb.GetLeft()),k.ToMM(bb.GetTop()),k.ToMM(bb.GetRight()),k.ToMM(bb.GetBottom())]
for f in b.GetFootprints():
    bb=f.GetBoundingBox(False,False)
    d['parts'].append({'ref':f.GetReference(),'pos':xy(f.GetPosition()),'box':[k.ToMM(bb.GetLeft()),k.ToMM(bb.GetTop()),k.ToMM(bb.GetRight()),k.ToMM(bb.GetBottom())]})
    for p in f.Pads():
        d['pads'].append({'ref':f.GetReference(),'num':p.GetNumber(),'net':p.GetNetname(),'pos':xy(p.GetPosition()),'layers':[n for n in [0,2] if p.IsOnLayer(n)],'polys':polys(p.GetEffectivePolygon(k.F_Cu)),'drill':xy(p.GetDrillSize()),'size':xy(p.GetSize()),'angle':p.GetOrientationDegrees(),'uuid':p.m_Uuid.AsString()})
for t in b.GetTracks():
    via=isinstance(t,k.PCB_VIA)
    d['tracks'].append({'net':t.GetNetname(),'start':xy(t.GetStart()),'end':xy(t.GetEnd()),'width':k.ToMM(t.GetWidth(k.F_Cu) if via else t.GetWidth()),'layers':[0,2] if via else [t.GetLayer()],'via':via,'uuid':t.m_Uuid.AsString()})
for z in b.Zones():
    d['zones'].append({'net':z.GetNetname(),'layers':[n for n in [0,2] if z.IsOnLayer(n)],'outline':polys(z.Outline()),'filled':{str(n):polys(z.GetFilledPolysList(n)) for n in [0,2] if z.HasFilledPolysForLayer(n)}})
Path(sys.argv[2]).write_text(json.dumps(d,ensure_ascii=False))
print('Geometry:',len(d['pads']),'pads',len(d['tracks']),'tracks/vias')
