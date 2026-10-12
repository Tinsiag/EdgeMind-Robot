import sys,pcbnew as k
b=k.LoadBoard(sys.argv[1]);rm=[]
for t in b.GetTracks():
 if t.GetNetname()=='MOTOR_POWER_OK':
  for get,setter in [(t.GetStart,t.SetStart),(t.GetEnd,t.SetEnd)]:
   p=get();x,y=k.ToMM(p.x),k.ToMM(p.y)
   if 76.49<x<76.57 and 44.19<y<44.41:setter(k.VECTOR2I(k.FromMM(76.52),p.y))
 if t.GetNetname()=='GND':
  if any((96.8<k.ToMM(p.x)<97.4 and 49<k.ToMM(p.y)<50.7) or (83.3<k.ToMM(p.x)<83.7 and 49.4<k.ToMM(p.y)<51.1) for p in [t.GetStart(),t.GetEnd()]):rm.append(t)
for t in rm:b.Remove(t)
k.SaveBoard(sys.argv[1],b);print('removed',len(rm))
