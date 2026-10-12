import pcbnew as k,json,sys
p=sys.argv[1];b=k.LoadBoard(p);F={f.GetReference():f for f in b.GetFootprints()}
for q in json.load(open(sys.argv[2])):
 f=F[q['ref']];f.SetOrientationDegrees(f.GetOrientationDegrees()+q['rotation_delta']);f.SetPosition(k.VECTOR2I(k.FromMM(q['x']),k.FromMM(q['y'])))
k.SaveBoard(p,b)
