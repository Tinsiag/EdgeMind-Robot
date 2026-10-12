"""将已校验的增量路径写入 PCB；不改变封装或现有网络。"""
import sys,json,pcbnew as k
b=k.LoadBoard(sys.argv[1]);data=json.load(open(sys.argv[2]))
def v(p):return k.VECTOR2I(k.FromMM(p[0]),k.FromMM(p[1]))
for d in data['tracks']:
    t=k.PCB_TRACK(b);t.SetStart(v(d['start']));t.SetEnd(v(d['end']));t.SetWidth(k.FromMM(d['width']));t.SetLayer(d['layers'][0]);t.SetNet(b.FindNet(d['net']));b.Add(t)
for d in data['vias']:
    t=k.PCB_VIA(b);t.SetPosition(v(d['start']));t.SetWidth(k.FromMM(d['width']));t.SetDrill(k.FromMM(d['drill']));t.SetLayerPair(k.F_Cu,k.B_Cu);t.SetNet(b.FindNet(d['net']));b.Add(t)
rm=[t for t in b.GetTracks() if t.m_Uuid.AsString() in data.get('remove',[])]
for t in rm:b.Remove(t)
b.BuildConnectivity();k.SaveBoard(sys.argv[1],b)
print('Added',len(data['tracks']),'tracks and',len(data['vias']),'vias')
