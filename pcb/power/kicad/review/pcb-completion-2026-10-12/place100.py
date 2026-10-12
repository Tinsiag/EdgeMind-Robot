"""100 mm two-layer layout; retain routed cores and repack the remaining parts."""
import sys,json,csv,math
from pathlib import Path
import pcbnew as k
root=Path(__file__).resolve().parents[2]
b=k.LoadBoard(sys.argv[1]);fp={f.GetReference():f for f in b.GetFootprints()};old={r:(k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y),f.GetOrientationDegrees()) for r,f in fp.items()}
def put(r,x,y,a):fp[r].SetOrientationDegrees(a);fp[r].SetPosition(k.VECTOR2I(k.FromMM(x),k.FromMM(y)))
plans={}
for row in csv.DictReader((root/'review/all-layout/元件布局索引.csv').open(encoding='utf-8-sig')):
 if row['局部X毫米']:plans.setdefault(row['局部组'],{})[row['位号']]=tuple(float(row[c]) for c in ['局部X毫米','局部Y毫米','KiCad角度度'])
origins={'aux_buck':(93,56),'aux_select':(105,73),'aux_ports':(104,89),'protect3':(91,66),'motor_switch':(29,86),'dumpL':(50,84),'dumpR':(89,86),'L_module':(23,89),'R_module':(73,89),'L_sense':(52,80.8),'R_sense':(85,80.8),'L_ref':(54,122),'R_ref':(85,122),'dump_compare':(65,82),'overcurrent':(38,43),'pwm_gate':(41,120),'safety':(93,94),'L_encoder':(41,83),'R_encoder':(69,96)}
moved=set()
for group,(ox,oy) in origins.items():
 for r,(x,y,a) in plans[group].items():put(r,x+ox,y+oy,a);moved.add(r)
mp=dict(U5='U1',L1='L2',C1='C8',C2='C9',C3='C10',C4='C12',C5='C13',R1='R6',C6='C14',C11='C16',R2='R11',R3='R12',C7='C15')
for a,r in mp.items():
 x,y,t=old[a];put(r,x,y+50,t);moved.add(r)
custom={'J3':(29,99,-90),'J4':(117,112.5,90),'U4':(108.1275,114.24,180),'C122':(38,122.5,0),'C131':(95.5,122.5,0),'C130':(39,99,0),'C138':(101,99,0),'C124':(67,89.8,0),'C133':(99.5,89.8,0),'TP1':(49,97.5,0),'Q2':(46,94,0),'Q6':(30.5,70,90),'Q7':(71,95,0),'C110':(105,72.5,0),'C111':(105,75,0),'J16':(30.9,82.5,-90),'J17':(67.5,127,0),'J15':(52.08,42,180),'J14':(115.5,82.5,90),
'J1':(62,130.2,-90),'J2':(99,130.2,-90),'J18':(118.5,38,0),'J9':(113,48,90),'JP1':(108,50,0),
'J10':(111,39.5,180),'J11':(117.5,90,-90),'J12':(117.5,120,-90),'J13':(117.5,128,-90),'C114':(111,95,-90),'C115':(111,103,-90),'C116':(111,111,-90),'C117':(111,119,-90),
'RV1':(55,122.5,0),'RV2':(89.5,124,0),'R86':(49,126.8,0),'C126':(52.5,126.8,0),'R87':(56,126.8,0),'R96':(83,127.8,0),'C135':(87,127.8,0),'R97':(91,127.8,0),
'U10':(42,106,0),'C118':(42,112,0),'U11':(51,106,0),'C127':(51,112,0),'U12':(101,106,0),'C119':(101,112,0),'U13':(70,99,90),'C120':(74,99,0),
'Q12':(110,59,180),'Q13':(114,60,180),'U29':(109,53,0),'C141':(114.8,54,0),'R116':(104.5,79,180),'R117':(111,85,90),'R114':(100,84,90),'R115':(100,88,90),'R118':(101,81,0),'R119':(108,92,90),'R120':(104,92,0),'R121':(108.5,89.7,0),
'R90':(39,114,0),'R91':(43,114,0),'C128':(47,114,0),'R92':(51,114,0),'R93':(54,114,0),'C129':(54,111.5,90),'R100':(89,100,0),'R101':(93,100,0),'C136':(89,103,0),'R102':(93,106,0),'R103':(89,109,0),'C137':(93,112,0),'R69':(40,101,0),'R70':(44,101,0),'R71':(100,100,0),'R72':(42,110.7,0),'R73':(104,100,0),'R124':(88,84,0),'R125':(85,86,90),'C143':(82,86,180),'R66':(100.25,53.25,0),'R68':(82,56.5,0)}
for r,(x,y,a) in custom.items():put(r,x,y,a);moved.add(r)
fixed=(set(fp)-moved)|set(mp.values())|set(plans['aux_buck'])|{'Q2','TP1'}
fixed |= {'U2','U4','J3','J4','C122','C131','C130','C138','Q6','Q7','J16','J17','R84','R94','U25','U26','C124','C133','R66','R68','J1','J2','J9','J10','J11','J12','J13','J14','J15','J18'}
# Correct a misassigned original island before routing.
for z in b.Zones():
 if z.GetNetname()=='+5V_FPGA_PROT' and k.ToMM(z.GetPosition().x)<80:z.SetNet(b.FindNet('+5V_AI_PROT'))
for a,c in zip([(25,36),(121,36),(121,133),(25,133)],[(121,36),(121,133),(25,133),(25,36)]):
 e=k.PCB_SHAPE(b);e.SetShape(k.SHAPE_T_SEGMENT);e.SetLayer(k.Edge_Cuts);e.SetStart(k.VECTOR2I(k.FromMM(a[0]),k.FromMM(a[1])));e.SetEnd(k.VECTOR2I(k.FromMM(c[0]),k.FromMM(c[1])));e.SetWidth(k.FromMM(.05));b.Add(e)
# Raised sockets allow low-profile SMDs underneath the daughterboard.
# Courtyards follow the two physical socket strips; module envelope stays on Fab.
removals=[]
for ref in ['U2','U4']:
 f=fp[ref];rows=sorted({round(k.ToMM(p.GetPosition().x-f.GetPosition().x),4) for p in f.Pads()})
 for g in list(f.GraphicalItems()):
  if g.GetLayer()==k.F_CrtYd:removals.append((f,g))
 x=k.ToMM(f.GetPosition().x);y=min(k.ToMM(p.GetPosition().y) for p in f.Pads())
 for dx in rows:
  g=k.PCB_SHAPE(f);g.SetShape(k.SHAPE_T_RECT);g.SetLayer(k.F_CrtYd);g.SetWidth(k.FromMM(.05));g.SetStart(k.VECTOR2I(k.FromMM(x+dx-1.75),k.FromMM(y-1.75)));g.SetEnd(k.VECTOR2I(k.FromMM(x+dx+1.75),k.FromMM(y+17)));f.Add(g)
for f in fp.values():f.Value().SetVisible(False);f.Reference().SetVisible(False)
for f,g in removals:f.Remove(g)
k.SaveBoard(sys.argv[2],b)
json.dump({'fixed':sorted(fixed),'initial':old},open(sys.argv[2]+'.packing.json','w'),indent=2)
print('Fixed cores:',len(fixed),'repack:',len(fp)-len(fixed))
