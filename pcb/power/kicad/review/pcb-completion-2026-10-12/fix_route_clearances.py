"""修正导入后加宽至 0.20 mm 所需的局部间距。"""
import sys, pcbnew as k
b=k.LoadBoard(sys.argv[1])
def adjusted(net,p):
    x,y=k.ToMM(p.x),k.ToMM(p.y)
    if net=='MOTOR_POWER_OK':
        if 38.1<x<38.3 and 103<y<103.6:x-=.04
        if 76.50<x<76.58 and 44.19<y<44.41:x-=.02
    if net=='VREF_R' and ((abs(x-91.4474)<.001 and 110.26<y<110.8) or (abs(x-91.7963)<.001 and abs(y-111.1464)<.001)):
        x+=.015;y-=.015
    return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
for t in b.GetTracks():
    if isinstance(t,k.PCB_VIA):continue
    t.SetStart(adjusted(t.GetNetname(),t.GetStart()))
    t.SetEnd(adjusted(t.GetNetname(),t.GetEnd()))
k.SaveBoard(sys.argv[1],b)
