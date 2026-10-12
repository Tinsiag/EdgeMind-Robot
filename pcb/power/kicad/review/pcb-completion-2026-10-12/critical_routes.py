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
        if isinstance(t,k.PCB_VIA):via(nets[net],points[0][0]+43,points[0][1]-10,k.ToMM(t.GetWidth(k.F_Cu)),k.ToMM(t.GetDrillValue()))
        else:wire(nets[net],[(x+43,y-10) for x,y in points],k.ToMM(t.GetWidth()),t.GetLayer())
    # Both sides of the input protection use the plated component holes.
    for z in list(b.Zones()):
        if z.GetNetname() in ['BAT_POS','Net-(Q1-D)']:
            clone=z.Duplicate(False);clone.SetLayer(k.B_Cu);b.Add(clone)
    wire('VBAT_SYS',[pt('Q1',3),(44.5,79.3325)],1.6,k.B_Cu)
    wire('VBAT_SYS',[(44.5,79.3325),(44.5,84),(33.92,94.58)],4,k.B_Cu)
    wire('VBAT_SYS',[(33.92,94.58),pt('Q2',3)],1.8,k.B_Cu)
    wire('VBAT_SYS',[pt('Q1',3),(46,77.4875),pt('C58',1)],2,k.B_Cu)
    wire('VBAT_SYS',[pt('C58',1),(49.247323,70.2)],3,k.B_Cu)
    wire('VBAT_SYS',[(49.247323,70.2),pt('Q3',3)],1.6,k.B_Cu)
    # Switched motor trunk, 3--4 mm; shunt entrances enter from the outside.
    wire('VM_SWITCHED',[pt('Q2',2),(36.46,100.5)],1.8)
    wire('VM_SWITCHED',[(36.46,100.5),(41,105.04),(52,105.04)],4)
    wire('VM_SWITCHED',[(52,105.04),pt('R84',1)],2.8)
    wire('VM_SWITCHED',[(52,105.04),(52,122)],3)
    for yy in [122,130]:
        for xx in [50.8,52,53.2]:
            for dy in [-.6,.6]:via('VM_SWITCHED',xx,yy+dy)
        for layer in [k.F_Cu,k.B_Cu]:zone('VM_SWITCHED',[(50.2,yy-1.2),(53.8,yy-1.2),(53.8,yy+1.2),(50.2,yy+1.2)],layer)
    wire('VM_SWITCHED',[(52,122),(52,130)],3,k.B_Cu)
    wire('VM_SWITCHED',[(52,130),(52,139),(68,139),(71,142),pt('R94',1)],2.8)
    # Kelvin takeoffs depart the inner edge of each shunt, away from the load.
    for sh,ic in [('R84','U25'),('R94','U26')]:
        a,y=pt(sh,1);c,_=pt(sh,2);p3=pt(ic,3);p4=pt(ic,4)
        wire('VM_SWITCHED',[(a+.35,y),(a+.35,y-2.5),(p3[0],y-2.5),p3],.25)
        wire(pad(sh,2).GetNetname(),[(c-.35,y),(c-.35,y-2.5),(p4[0],y-2.5),p4],.25)
    # Local motor load feeds. Wide connections stop short of adjacent pins.
    wire('VM_L',[pt('R84',2),(60,106.9625),(60,111.54),pt('U2',9)],2)
    wire('VM_L',[(60,111.54),(58,113.54),(58,127),(44,127),(44,121.7),pt('U2',6)],2)
    link('U2',6,'C122',1,[(34,121.7),(32,123.7)],2)
    link('U2',6,'C123',1,[(36.35,121.7)],.8)
    wire('VM_R',[pt('R94',2),(84,144.0375),(84,146.54),pt('U4',9),(58,146.54),(58,164),(44,164),(44,156.7),pt('U4',6)],2)
    link('U4',6,'C131',1,[(34,156.7),(32,158.7)],2)
    link('U4',6,'C132',1,[(36.35,156.7)],.8)
    # Left dump branch changes layer with six parallel, 0.4 mm plated vias.
    for x in [64,65.2,66.4]:
        for y in [106,107.2]:via('VM_L',x,y)
    zone('VM_L',[(61.6,104.5),(67,104.5),(67,108),(61.6,108)])
    zone('VM_L',[(63.4,105.4),(67,105.4),(67,107.8),(63.4,107.8)],k.B_Cu)
    wire('VM_L',[(65.2,106.6),(68,103.8),(68,90),(72,86),(79,86),pt('J16',1)],2,k.B_Cu)
    link('R94',2,'J17',1,[(84,144.0375),(84,145),(93,145)],2)
    link('J16',2,'Q6',2,[(80.54,92.54)],2,k.B_Cu)
    link('J17',2,'Q7',2,[(97.54,151.54)],2,k.B_Cu)
    # Each H bridge output has a direct 1.8 mm path to its connector.
    for u,j,y in [('U2','J3',109),('U4','J4',144)]:
        link(u,1,j,1,width=1.8)
        link(u,2,j,6,[(36,y+2.54),(30,y+8.54),(30,y+12.5)],1.8)
    # Local AP63203 loop and bootstrap. Feedback is sampled at the output.
    link('U3',3,'C108',1,[(112.863,69.5125)],.65)
    link('U3',5,'L3',1,[(117,66),(119.975,68.975)],.7)
    link('U3',5,'C109',1,[(116.3,66),(118,64.575)],.3)
    link('U3',6,'C109',2,[(115.137,63.025)],.3)
    link('L3',2,'C110',1,[(129,69.7),(129,73.7),(122.05,73.7)],1)
    link('C110',1,'C111',1,[(122.05,74.5),(126.05,74.5)],1)
    link('C110',1,'U3',1,[(108,76),(108,62),(112.863,62)],.25)
    # A short rear bridge clears the existing battery comparator fanout.
    # Remaining distribution runs on the front, as requested.
    wire('VLOGIC_IN',[pt('C101',1),(60,67.8225),(60,83),(93,83)],2,k.B_Cu)
    for xx in [92,93,94]:
        for yy in [82.4,83.6]:via('VLOGIC_IN',xx,yy)
    for layer in [k.F_Cu,k.B_Cu]:zone('VLOGIC_IN',[(91.4,81.8),(94.6,81.8),(94.6,84.2),(91.4,84.2)],layer)
    wire('VLOGIC_IN',[(93,83),(104,83),(106.5,80.5),(106.5,50.55),pt('C8',1),pt('C10',1)],1.5)
    link('C101',1,'C1',1,[(63.271078,60.551422)],1.2)
    # The auxiliary buck now sits beside the main supply instead of on an
    # isolated extension. Its input branches directly from the distribution.
    for x,y in [(106.5,74),(110.5,70)]:
        for dy in [-.6,.6]:via('VLOGIC_IN',x,y+dy)
        for layer in [k.F_Cu,k.B_Cu]:zone('VLOGIC_IN',[(x-.5,y-1.1),(x+.5,y-1.1),(x+.5,y+1.1),(x-.5,y+1.1)],layer)
    wire('VLOGIC_IN',[(106.5,74),(110.5,70)],1.2,k.B_Cu)
    wire('VLOGIC_IN',[(110.5,70),(110.8,69.7),pt('C108',1)],1)
    # Converter outputs are broad locally; original feedback stays separate.
    for off,l,c,d in [(0,'L1','C4','C5'),(43,'L2','C12','C13')]:
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
