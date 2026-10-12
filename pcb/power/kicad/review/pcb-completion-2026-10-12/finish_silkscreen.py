"""Expose reference labels without covering solder-mask openings or other silk."""
import sys,json,math
from pathlib import Path
import pcbnew as k
b=k.LoadBoard(sys.argv[1]);MM=k.FromMM
e=b.GetBoardEdgesBoundingBox();limits=[k.ToMM(v) for v in [e.GetLeft(),e.GetTop(),e.GetRight(),e.GetBottom()]]

def v(x,y):return k.VECTOR2I(MM(x),MM(y))
def box(o):
    a=o.GetBoundingBox();return [k.ToMM(a.GetLeft()),k.ToMM(a.GetTop()),k.ToMM(a.GetRight()),k.ToMM(a.GetBottom())]
def grown(a,d):return [a[0]-d,a[1]-d,a[2]+d,a[3]+d]
def hit(a,c):return a[0]<c[2] and a[2]>c[0] and a[1]<c[3] and a[3]>c[1]
obstacles=[]
for f in b.GetFootprints():
    f.Reference().SetVisible(False);f.Value().SetVisible(False)
    for p in f.Pads():
        if p.IsOnLayer(k.F_Mask):obstacles.append(grown(box(p),.18))
    for g in f.GraphicalItems():
        if g.GetLayer()!=k.F_SilkS:continue
        bb=box(g)
        if hasattr(g,'GetShape') and g.GetShape()==k.SHAPE_T_RECT:
            x1,y1,x2,y2=bb;w=k.ToMM(g.GetWidth())+.15
            obstacles.extend([[x1-w,y1-w,x2+w,y1+w],[x1-w,y2-w,x2+w,y2+w],[x1-w,y1-w,x1+w,y2+w],[x2-w,y1-w,x2+w,y2+w]])
        else:obstacles.append(grown(bb,.1))
placed=[];failed=[]
for f in sorted(b.GetFootprints(),key=lambda f:(not f.GetReference().startswith(('U','J','Q','RV','CN','USB','F')),f.GetReference())):
    r=f.Reference();r.SetTextSize(v(.8,.8));r.SetTextThickness(MM(.12));r.SetTextAngle(k.EDA_ANGLE(0,k.DEGREES_T));r.SetLayer(k.F_SilkS)
    bb=f.GetBoundingBox(False,False);x1,y1,x2,y2=[k.ToMM(t) for t in [bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()]]
    x=(x1+x2)/2;y=(y1+y2)/2
    # Component centre is useful for large outline-only modules and ICs.
    candidates=[(x,y,0),(x,y1-.8,0),(x,y2+.8,0),(x1-1.6,y,90),(x2+1.6,y,90)]
    for d in [.8,1.2,1.8,2.4,3.0,4.0,5.0,6.0,7.0]:
        for delta in [0,-1.5,1.5,-3,3]:
            candidates.extend([(x+delta,y1-d,0),(x+delta,y2+d,0),(x1-d,y+delta,90),(x2+d,y+delta,90)])
    for xx,yy,angle in candidates:
        r.SetPosition(v(xx,yy));r.SetTextAngle(k.EDA_ANGLE(angle,k.DEGREES_T));rb=grown(box(r),.08)
        if not(limits[0]+.5<rb[0] and rb[2]<limits[2]-.5 and limits[1]+.5<rb[1] and rb[3]<limits[3]-.5):continue
        if any(hit(rb,a) for a in obstacles):continue
        r.SetVisible(True);obstacles.append(grown(rb,.08));placed.append(f.GetReference());break
    else:failed.append(f.GetReference())
# Compact identification in a free area of the lower edge.
for txt,x,y,size in [('双层电源板',67,38,1),('电池入口',35,57.2,.8)]:
    t=k.PCB_TEXT(b);t.SetText(txt);t.SetLayer(k.F_SilkS);t.SetPosition(v(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(MM(.12))
    rb=grown(box(t),.12)
    if not any(hit(rb,a) for a in obstacles):b.Add(t);obstacles.append(rb)
k.SaveBoard(sys.argv[1],b)
Path(sys.argv[1]).with_suffix('.silk.json').write_text(json.dumps({'visible_refs':placed,'unplaced':failed},ensure_ascii=False,indent=2))
print('Reference silkscreen:',len(placed),'placed, missing:',failed)
