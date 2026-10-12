"""Keep the stock socket-strip courtyards; raised module space holds only SMDs."""
import sys,math
from pathlib import Path
import pcbnew as k
b=k.LoadBoard(sys.argv[1]);removed=[]
for ref in ['U2','U4']:
 f=b.FindFootprintByReference(ref);src=k.FootprintLoad(str(Path(__file__).resolve().parents[2]/'EdgeMind_Module.pretty'),str(f.GetFPID().GetLibItemName()))
 angle=math.radians(f.GetOrientationDegrees());c,s=math.cos(angle),math.sin(angle);x,y=k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y)
 def v(p):
  xx,yy=k.ToMM(p.x),k.ToMM(p.y);return k.VECTOR2I(k.FromMM(x+c*xx+s*yy),k.FromMM(y-s*xx+c*yy))
 for g in f.GraphicalItems():
  if g.GetLayer()==k.F_CrtYd:removed.append((f,g))
 for g in src.GraphicalItems():
  if g.GetLayer()!=k.F_CrtYd:continue
  q=k.PCB_SHAPE(f);q.SetShape(g.GetShape());q.SetLayer(k.F_CrtYd);q.SetStart(v(g.GetStart()));q.SetEnd(v(g.GetEnd()));q.SetWidth(g.GetWidth());f.Add(q)
for f,g in removed:f.Remove(g)
k.SaveBoard(sys.argv[1],b)
