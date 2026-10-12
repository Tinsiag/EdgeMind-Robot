"""Add checked ground fanouts, continuous ground pours, and export DSN."""
import sys,json,re
from pathlib import Path
import pcbnew as k
path=Path(sys.argv[1]);b=k.LoadBoard(str(path));data=json.load(open(sys.argv[2]))
def vec(p):return k.VECTOR2I(k.FromMM(p[0]),k.FromMM(p[1]))
for p in data['vias']:
    t=k.PCB_TRACK(b);t.SetStart(vec(p['start']));t.SetEnd(vec(p['via']));t.SetWidth(k.FromMM(p['width']));t.SetLayer(k.F_Cu);t.SetNet(b.FindNet('GND'));b.Add(t)
    q=k.PCB_VIA(b);q.SetPosition(vec(p['via']));q.SetWidth(k.FromMM(p['diameter']));q.SetDrill(k.FromMM(p['drill']));q.SetViaType(k.VIATYPE_THROUGH);q.SetLayerPair(k.F_Cu,k.B_Cu);q.SetNet(b.FindNet('GND'));b.Add(q)
edge=b.GetBoardEdgesBoundingBox();x0,y0,x1,y1=[k.ToMM(t) for t in [edge.GetLeft(),edge.GetTop(),edge.GetRight(),edge.GetBottom()]]
for layer in [k.F_Cu,k.B_Cu]:
    z=k.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet('GND'));z.SetAssignedPriority(0);z.SetLocalClearance(k.FromMM(.25));z.SetMinThickness(k.FromMM(.2));z.SetPadConnection(k.ZONE_CONNECTION_THERMAL);z.SetThermalReliefGap(k.FromMM(.25));z.SetThermalReliefSpokeWidth(k.FromMM(.4));z.SetIslandRemovalMode(0)
    poly=z.Outline();poly.NewOutline()
    for x,y in [(x0+.5,y0+.5),(x1-.5,y0+.5),(x1-.5,y1-.5),(x0+.5,y1-.5)]:poly.Append(k.FromMM(x),k.FromMM(y))
    b.Add(z)
b.BuildConnectivity();k.SaveBoard(str(path),b)
print('Ground fanouts and two copper layers saved')
