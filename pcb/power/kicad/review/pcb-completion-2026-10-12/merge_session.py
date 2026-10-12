"""导入新增布线，并保留 DSN 中已保护、因而未写入 SES 的原有铜线。"""
import sys
import pcbnew as k

baseline, session, output = sys.argv[1:4]
b = k.LoadBoard(baseline)
original = []
for t in b.GetTracks():
    original.append(dict(via=isinstance(t, k.PCB_VIA), net=t.GetNetname(),
        start=k.VECTOR2I(t.GetStart()), end=k.VECTOR2I(t.GetEnd()),
        width=t.GetWidth(k.F_Cu) if isinstance(t, k.PCB_VIA) else t.GetWidth(),
        drill=t.GetDrillValue() if isinstance(t, k.PCB_VIA) else 0,
        layer=t.GetLayer(), uuid=t.m_Uuid.AsString()))
pad_nets = {(f.GetReference(), p.GetNumber()):p.GetNetname()
            for f in b.GetFootprints() for p in f.Pads()}
assert k.ImportSpecctraSES(b, session)
def key(t):
    via=isinstance(t,k.PCB_VIA)
    return (via,t.GetNetname(),t.GetLayer(),
            tuple(sorted([(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)])),
            t.GetWidth(k.F_Cu) if via else t.GetWidth())
existing={key(t) for t in b.GetTracks()}
restored=0
for d in original:
    t=k.PCB_VIA(b) if d['via'] else k.PCB_TRACK(b)
    t.SetStart(d['start']);t.SetEnd(d['end'])
    t.SetWidth(d['width']);t.SetNet(b.FindNet(d['net']))
    if d['via']:
        t.SetDrill(d['drill']);t.SetLayerPair(k.F_Cu,k.B_Cu)
    else:t.SetLayer(d['layer'])
    t.SetUuid(k.KIID(d['uuid']))
    if key(t) not in existing:
        b.Add(t);existing.add(key(t));restored+=1
for t in b.GetTracks():
    t.SetLocked(False)
    if not isinstance(t,k.PCB_VIA) and t.GetWidth()<k.FromMM(.2):
        t.SetWidth(k.FromMM(.2))
assert pad_nets == {(f.GetReference(), p.GetNumber()):p.GetNetname()
                    for f in b.GetFootprints() for p in f.Pads()}
assert b.GetCopperLayerCount()==2
b.BuildConnectivity();k.SaveBoard(output,b)
print('Restored',restored,'protected tracks/vias; total',len(b.GetTracks()))
