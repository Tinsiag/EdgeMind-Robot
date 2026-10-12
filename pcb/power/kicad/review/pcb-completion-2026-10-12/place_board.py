"""Continue the existing PCB; retain the routed area and place remaining groups.

Run with KiCad's Python. Inputs and output are explicit to avoid overwriting
the user's PCB accidentally. Local placements come from the existing atlas.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import pcbnew as k

ROOT = Path(__file__).resolve().parents[2]
MM = k.FromMM
def vec(x, y): return k.VECTOR2I(MM(x), MM(y))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source'); ap.add_argument('output')
    args = ap.parse_args()
    board = k.LoadBoard(args.source)
    fp = {f.GetReference(): f for f in board.GetFootprints()}
    initial = {r: (k.ToMM(f.GetPosition().x), k.ToMM(f.GetPosition().y), f.GetOrientationDegrees()) for r,f in fp.items()}
    plans = {}
    with (ROOT/'review/all-layout/元件布局索引.csv').open(encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row['局部X毫米']:
                plans.setdefault(row['局部组'], {})[row['位号']] = tuple(float(row[c]) for c in ['局部X毫米','局部Y毫米','KiCad角度度'])
    origins = {
        'aux_buck': (104,56,0), 'aux_select': (106,83,0),
        'aux_ports': (138,110,-90), 'protect3': (108,68,0),
        'motor_switch': (29,86,0), 'dumpL': (68,86,0),
        'L_module': (29,99,0), 'L_sense': (49,91,0), 'L_ref': (69,108,0),
        'R_module': (29,134,0), 'R_sense': (69,128,0), 'R_ref': (69,149,0),
        'dumpR': (85,145,0), 'dump_compare': (85,97,0),
        'overcurrent': (85,83,0), 'pwm_gate': (81,127,0),
        'safety': (91,108,0),
        'L_encoder': (99,140,0), 'R_encoder': (99,157,0),
    }
    placed = {}
    def place(r,x,y,a,group):
        fp[r].SetOrientationDegrees(a)
        fp[r].SetPosition(vec(x,y))
        placed[r] = {'group':group,'old':initial[r],'new':(x,y,a)}
    for name,(ox,oy,a) in origins.items():
        rad=math.radians(a); c,s=math.cos(rad),math.sin(rad)
        for r,(x,y,ang) in plans[name].items():
            place(r,ox+c*x+s*y,oy-s*x+c*y,ang+a,name)
    # Use the user's already-routed first converter as the second channel's
    # placement reference, retaining pin orientations and component spacing.
    mapping = dict(U5='U1',L1='L2',C1='C8',C2='C9',C3='C10',C4='C12',C5='C13',R1='R6',C6='C14',C11='C16',R2='R11',R3='R12',C7='C15')
    for old,new in mapping.items():
        x,y,a=initial[old]; place(new,x+43,y-10,a,'ai_buck')
    custom = {'J1':(125,151,-90),'J2':(125,168,-90), 'J18':(134.5,143.5,0),
              'R124':(121,155,0),'R125':(126,157,90),'C143':(123,160,180),
              'C130':(33.5,105.5,0),'C138':(33.5,140.5,0), 'J15':(114,107,0),
              'Q12':(129,80,180),'Q13':(129,84,180),'R116':(124.5,80,180),
              'R117':(129,88.5,90),'R118':(115,84,0),
              'R114':(113,88,90),'R115':(113,91.5,90),'U29':(120,89,0),
              'C141':(125.8,87.1,0),'R119':(127,95,90),'R120':(123,93.8,0),
              'R121':(126,91.7,0),'JP1':(135,85,0),'J9':(135,77,0),
              'C112':(120,96,0),'C113':(120,99,0),'FB1':(115,97,0),'J14':(126,105,0),
              'J10':(133,114,-90),'C114':(127.5,115,-90),
              'J11':(133,121.5,-90),'C115':(127.5,122.5,-90),
              'J12':(133,129,-90),'C116':(127.5,130,-90),
              'J13':(133,136.5,-90),'C117':(127.5,137.5,-90),
              'R90':(102,140,0),'R91':(107,143,-90),'C128':(107,146,-90),
              'R92':(113,144,0),'R93':(117,143,-90),'C129':(117,146,-90),
              'R100':(103,161,0),'R101':(107,160,-90),'C136':(107,163,-90),
              'R102':(113,161,0),'R103':(117,160,-90),'C137':(117,163,-90)}
    for r,(x,y,a) in custom.items():place(r,x,y,a,'control')
    untouched=set(fp)-set(placed)
    assert all(initial[r][0]<105 and initial[r][1]<91 for r in untouched), sorted(untouched)
    # Correct the right-hand 5 V protection island to its actual output net.
    for z in board.Zones():
        if z.GetNetname()=='+5V_FPGA_PROT' and k.ToMM(z.GetPosition().x)<80:
            z.SetNet(board.FindNet('+5V_AI_PROT'))
    # Establish an explicit board outline; no original edge existed.
    assert not any(d.GetLayer()==k.Edge_Cuts for d in board.GetDrawings())
    corners=[(21,36),(139,36),(139,174),(21,174)]
    for i,a in enumerate(corners):
        edge=k.PCB_SHAPE(board);edge.SetShape(k.SHAPE_T_SEGMENT);edge.SetLayer(k.Edge_Cuts)
        edge.SetStart(vec(*a));edge.SetEnd(vec(*corners[(i+1)%4]));edge.SetWidth(MM(.05));board.Add(edge)
    for f in fp.values():
        f.Value().SetVisible(False)
    board.BuildConnectivity()
    k.SaveBoard(args.output,board)
    details={'outline_mm':corners,'unchanged_parts':sorted(untouched),'moved_parts':placed,'group_bounds':{}}
    for group in [*origins,'ai_buck','control']:
        refs=[r for r,p in placed.items() if p['group']==group]
        if not refs:continue
        boxes=[fp[r].GetBoundingBox(False,False) for r in refs]
        details['group_bounds'][group]=[round(k.ToMM(v),3) for v in [min(b.GetLeft() for b in boxes),min(b.GetTop() for b in boxes),max(b.GetRight() for b in boxes),max(b.GetBottom() for b in boxes)]]
    Path(args.output).with_suffix('.placement.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
    print(json.dumps({'retained':len(untouched),'placed':len(placed),'bounds':details['group_bounds']},indent=2))

if __name__=='__main__': main()
