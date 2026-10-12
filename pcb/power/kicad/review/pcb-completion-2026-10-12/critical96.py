"""Explicit power paths and local converter/Kelvin routing before signal routing."""
import argparse, json, copy
from pathlib import Path
import pcbnew as k

MM=k.FromMM
def v(p):return k.VECTOR2I(MM(p[0]),MM(p[1]))
def xy(p):return (k.ToMM(p.x),k.ToMM(p.y))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('board');args=ap.parse_args()
    path=Path(args.board);b=k.LoadBoard(str(path));F={f.GetReference():f for f in b.GetFootprints()}
    def pad(r,n):return next(p for p in F[r].Pads() if p.GetNumber()==str(n))
    def pt(r,n):return xy(pad(r,n).GetPosition())
    def wire(net,points,width=.3,layer=k.F_Cu):
        for a,c in zip(points,points[1:]):
            if a==c:continue
            t=k.PCB_TRACK(b);t.SetStart(v(a));t.SetEnd(v(c));t.SetWidth(MM(width));t.SetLayer(layer);t.SetNet(b.FindNet(net));b.Add(t)
    def link(a,n,c,m,points=(),width=.3,layer=k.F_Cu):
        net=pad(a,n).GetNetname();assert net==pad(c,m).GetNetname(),(a,n,c,m)
        wire(net,[pt(a,n),*points,pt(c,m)],width,layer)
    def via(net,x,y,size=.8,drill=.4):
        q=k.PCB_VIA(b);q.SetPosition(v((x,y)));q.SetWidth(MM(size));q.SetDrill(MM(drill));q.SetViaType(k.VIATYPE_THROUGH);q.SetLayerPair(k.F_Cu,k.B_Cu);q.SetNet(b.FindNet(net));b.Add(q)
    def zone(net,points,layer=k.F_Cu,priority=5):
        z=k.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet(net));z.SetLocalClearance(MM(.25));z.SetMinThickness(MM(.2));z.SetPadConnection(k.ZONE_CONNECTION_FULL);z.SetAssignedPriority(priority)
        p=z.Outline();p.NewOutline()
        for x,y in points:p.Append(MM(x),MM(y))
        b.Add(z);return z
    F['J9'].SetPosition(v((114.8,44)));F['J9'].SetOrientationDegrees(0)
    F['R71'].SetPosition(v((95.7,108)));F['R71'].SetOrientationDegrees(90)
    F['C110'].SetOrientationDegrees(180);F['C111'].SetOrientationDegrees(180)
    # Remove only the identified, 20 um dangling endpoint from the old board.
    dangling=[t for t in b.GetTracks() if not isinstance(t,k.PCB_VIA) and t.GetNetname()=='VBAT_SYS' and t.GetLength()<MM(.021)]
    # Duplicate only the routed converter core, not any cross-channel copper.
    nets={'Net-(U5-SW)':'Net-(U1-SW)','Net-(U5-FB)':'Net-(U1-FB)',
          'Net-(U5-BST)':'Net-(U1-BST)','Net-(U5-VCC)':'Net-(U1-VCC)',
          'Net-(C6-Pad1)':'Net-(C14-Pad1)','+5V_FPGA':'+5V_AI','VLOGIC_IN':'VLOGIC_IN'}
    for t in list(b.GetTracks()):
        net=t.GetNetname()
        if net not in nets:continue
        points=[xy(t.GetStart()),xy(t.GetEnd())]
        if net in ['+5V_FPGA','VLOGIC_IN'] and not all(65<=x<=82 and 52<=y<=70 for x,y in points):continue
        if isinstance(t,k.PCB_VIA):via(nets[net],points[0][0],points[0][1]+50,k.ToMM(t.GetWidth(k.F_Cu)),k.ToMM(t.GetDrillValue()))
        else:wire(nets[net],[(x,y+50) for x,y in points],k.ToMM(t.GetWidth()),t.GetLayer())
    # Both sides of the input protection use the plated component holes.
    for z in list(b.Zones()):
        if z.GetNetname() in ['BAT_POS','Net-(Q1-D)']:
            clone=z.Duplicate(False);clone.SetLayer(k.B_Cu);b.Add(clone)
    wire('VBAT_SYS',[pt('Q1',3),(44.5,79.3325)],1.6,k.B_Cu)
    wire('VBAT_SYS',[(44.5,79.3325),(44.5,84),(51.08,90.58)],3,k.B_Cu)
    wire('VBAT_SYS',[(51.08,90.58),pt('Q2',3)],1.8,k.B_Cu)
    wire('VBAT_SYS',[pt('Q1',3),(46,77.4875),pt('C58',1)],2,k.B_Cu)
    wire('VBAT_SYS',[pt('C58',1),(49.247323,70.2)],3,k.B_Cu)
    wire('VBAT_SYS',[(49.247323,70.2),pt('Q3',3)],1.6,k.B_Cu)
    # Compact auxiliary buck: ceramic input, switch loop and bootstrap.
    link('U3',3,'C108',1,[(101.8625,69.7)],.65)
    link('U3',5,'L3',1,[(106,66),(108.975,68.975)],.7)
    link('U3',5,'C109',1,[(105.3,66),(107,64.575)],.3)
    link('U3',6,'C109',2,[(104.1375,63.025)],.3)
    link('L3',2,'C110',1,[(117.2,69.7),(117.2,72.5),(115.5,74.2),(108,74.2),(107.2,73.4)],1)
    link('C110',1,'C111',1,width=1)
    link('C111',1,'U3',1,[(105.95,76.3),(100.8,76.3),(100.8,64),(101.8625,64)],.25)
    link('C101',1,'C1',1,[(63.271078,60.551422)],1.2)
    # Shunt sense traces are routed before motor power to preserve Kelvin exits.
    for sh,ic in [('R84','U25'),('R94','U26')]:
        a,y=pt(sh,1);c,_=pt(sh,2);p3=pt(ic,3);p4=pt(ic,4)
        wire('VM_SWITCHED',[(a+.35,y),(a+.35,y-2.5),(p3[0],y-2.5),p3],.25)
        wire(pad(sh,2).GetNetname(),[(c-.35,y),(c-.35,y-2.5),(p4[0],y-2.5),p4],.25)
    # Six vias at each shunt carry power independently of the Kelvin traces.
    for sh in ['R84','R94']:
        for num,side in [(1,-1),(2,1)]:
            x,y=pt(sh,num);net=pad(sh,num).GetNetname();vx=x+side*1.8
            for dy in [-.9,0,.9]:via(net,vx,y+dy)
            for layer in [k.F_Cu,k.B_Cu]:
                lo,hi=sorted([x-side*.3,vx+side*.5]);zone(net,[(lo,y-1.45),(hi,y-1.45),(hi,y+1.45),(lo,y+1.45)],layer)
    # The left discharge terminal faces outwards along the left edge.
    link('J16',2,'Q6',2,[(27.3,87.58),(27.3,68.8),(28.64,67.46)],1.8)
    # Converter outputs are broad locally; original feedback stays separate.
    for off,l,c,d in [(0,'L1','C4','C5'),(0,'L2','C12','C13')]:
        link(l,2,c,1,width=1.5)
        link(c,1,d,1,width=1.2)
    # Move the two pull-ups out of the USB power channel; their former location
    # forced a long 0.20 mm / 3 A bottleneck between the resistor's pads.
    for r,x,y in [('R66',100.25,53.25),('R68',82,56.5)]:F[r].SetPosition(v((x,y)))
    for t in b.GetTracks():
        if t.GetNetname() in ['USB1_FAULT_PULSE_N','USB2_FAULT_PULSE_N']:dangling.append(t)
        if isinstance(t,k.PCB_VIA):continue
        if t.GetNetname() in ['USB1_VBUS','USB2_VBUS'] and t.GetWidth()==MM(.2):
            if t.GetLength()>MM(4):dangling.append(t)
            else:t.SetWidth(MM(.4))
        if t.GetNetname() in ['+5V_FPGA_PROT','+5V_AI_PROT']:
            if t.GetWidth()==MM(.2):t.SetWidth(MM(.4))
            elif t.GetWidth()==MM(.5):t.SetWidth(MM(1))
    for u,j in [('U7','USB1'),('U8','USB2')]:
        x,y=pt(u,8);wire(pad(u,8).GetNetname(),[(x,y),(x,y-1.2)],.4)
        wire(pad(u,8).GetNetname(),[(x,y-1.2),pt(j,'A9')],.85)
    # Major return pads connect solidly, not through narrow thermal spokes.
    heavy=['CN1','C58','C101','C122','C131','Q6','Q7','U2','U4','J3','J4','USB1','USB2']
    for r in heavy:
        for p in F[r].Pads():
            if p.GetNetname()=='GND':p.SetLocalZoneConnection(k.ZONE_CONNECTION_FULL)
    track_count=len(b.GetTracks())-len(dangling)
    for t in dangling:b.Remove(t)
    b.BuildConnectivity();k.SaveBoard(str(path),b)
    # Normal signals keep the existing 0.20 mm clearance; only intrinsic
    # same-package TSOT pads receive the footprint's 0.15 mm clearance.
    conditions=' || '.join(f"(A.memberOfFootprint('{r}') && B.memberOfFootprint('{r}'))" for r in ['U1','U5','U7','U8'])
    path.with_suffix('.kicad_dru').write_text('(version 1)\n(rule "TSOT23-8 原生焊盘间距"\n (condition "A.Type == \'Pad\' && B.Type == \'Pad\' && ('+conditions+')")\n (constraint clearance (min 0.15mm)))\n')
    pro=path.with_suffix('.kicad_pro');data=json.loads(pro.read_text());data['board']['design_settings']['track_widths']=[0,.2,.25,.3,.5,.8,1,1.5,2,3,4]
    data['board']['design_settings']['via_dimensions']=[{'diameter':.6,'drill':.3},{'diameter':.8,'drill':.4}]
    data['net_settings']['classes'][0]['track_width']=.25
    pro.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Critical routes:',track_count,'tracks/vias;',len(list(b.Zones())),'zones')

if __name__=='__main__':main()
