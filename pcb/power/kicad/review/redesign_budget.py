"""Current R2: independent 3V3 by default, two 5V rails, 6P USB-C.

The existing PCB is read only. All physical packages are KiCad stock except
the two AT8236 socket carriers. Run this builder, then validate the native netlist.
"""
import redesign_schematic as g
from redesign_schematic import *

FUSE='Fuse:Fuseholder_Clip-5x20mm_Littelfuse_100_Inline_P20.50x4.60mm_D1.30mm_Horizontal'
INDUCTOR='Inductor_SMD:L_Changjiang_FXL0630'
USB6='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-17'
HUSB_DS='https://www.hynetek.com/uploadfiles/site/219/news/2a2293ad-5b62-48ab-b902-a09e7bf50a18.pdf'

def define_parts():
    g.CUSTOM.pop('EdgeMind_Power:TPS25940L',None)
    custom_symbol('HUSB305_02','U',[
      ('1','VIN','power_in',-15.24,7.62,0),('3','ISET','passive',-15.24,-7.62,0),
      ('4','NC','no_connect',-15.24,-12.7,0),('2','GND','power_in',0,-20.32,90),
      ('8','VBUS','power_out',15.24,7.62,180),('6','CC1','bidirectional',15.24,0,180),
      ('5','CC2','bidirectional',15.24,-5.08,180),('7','STAT','open_collector',15.24,-12.7,180)],
      description='Fixed 5V USB-C source; integrated attach detection, current limit and switched VBUS. STAT pulses on faults in -02 version.',
      fp='Package_TO_SOT_SMD:TSOT-23-8',datasheet=HUSB_DS)
    custom_symbol('AO4409','Q',[
      ('4','G','input',-10.16,0,0),
      *[(str(k),'S','passive',0,12.7,270) for k in [1,2,3]],
      *[(str(k),'D','passive',10.16,0,180) for k in [5,6,7,8]]],
      box=(-5.08,7.62,5.08,-7.62),description='30V P-channel MOSFET; SO8 pin4 G, pins1/2/3 S, pins5/6/7/8 D',fp=SO8,
      datasheet='https://www.aosmd.com/sites/default/files/res/datasheets/AO4409.pdf')
    # Stock quad AND drawing / pin numbers; explicitly CMOS HC rather than LS TTL.
    body=cached('74xx:74LS08').replace('74xx:74LS08','74HC08').replace('74LS08','74HC08')
    g.CUSTOM['EdgeMind_Power:74HC08']=body

def cmp_power(p,ref,x,y):
    u=p.sym('Comparator:LM393',ref,x,y,'LM393BIDR',SO8,unit=3,mpn='LM393BIDR')
    p.stub(u,8,'VBAT_SYS',3.81);p.ground(u.pin(4));decouple(p,x+17.78,y,'VBAT_SYS')

def threshold(p,x,y,ref,unit,rail,top,bottom,out,low=False):
    """OC pulls low below threshold (low=True) or above threshold."""
    u=p.sym('Comparator:LM393',ref,x,y,'LM393BIDR',SO8,unit=unit,mpn='LM393BIDR')
    cp,cn,co=(3,2,1) if unit==1 else (5,6,7)
    xx=x-38.1;my=u.pin(cp if low else cn)[1]
    rt=R(p,xx,my-12.7,top+' 0.1%');rb=R(p,xx,my+12.7,bottom+' 0.1%')
    p.stub(rt,1,rail,3.81);p.wire(rt.pin(2),(xx,my),rb.pin(1));p.ground(rb.pin(2));p.dot((xx,my))
    p.wire((xx,my),u.pin(cp if low else cn));p.stub(u,cn if low else cp,'VREF_2V495',7.62)
    p.stub(u,co,out,7.62)
    return u

def pm_switch(p,x,y,source,target,control,ref=None,large=False):
    """Source at input, drain at output; high control enables NPN gate sink."""
    if large:
        mos=p.sym('Transistor_FET:Q_PMOS_GDS',ref,x,y,'IRF4905',TO220,angle=270,mpn='IRF4905')
        sourcepin,drainpin,gatepin=3,2,1
    else:
        mos=p.sym('EdgeMind_Power:AO4409',ref,x,y,'AO4409',SO8,mpn='AO4409')
        sourcepin,drainpin,gatepin=1,5,4
    sp=mos.pin(sourcepin);gp=mos.pin(gatepin)
    p.stub(mos,sourcepin,source,5.08);p.stub(mos,drainpin,target,10.16)
    # Gate pull-up and 12V gate/source clamp guarantee OFF with absent control power.
    xx=x-25.4;rt=R(p,xx,y-10.16,'1k' if not large else '10k')
    p.stub(rt,1,source,5.08);gate=(xx,y+10.16)
    p.wire(rt.pin(2),gate,(gp[0],gate[1]),gp);p.dot(gate)
    z=p.sym('Device:D_Zener',None,x-10.16,y+25.4,'BZT52C12','Diode_SMD:D_SOD-123',angle=270)
    p.stub(z,1,source,5.08);p.wire(z.pin(2),(xx,z.pin(2)[1]),gate)
    tr=p.sym('Transistor_BJT:MMBT3904',None,xx-2.54,y+40.64,'MMBT3904','Package_TO_SOT_SMD:SOT-23',mpn='MMBT3904')
    p.wire(gate,tr.pin(3));p.ground(tr.pin(2))
    rb=R(p,xx-22.86,y+40.64,'4.7k',a=90);p.wire(rb.pin(2),tr.pin(1));p.stub(rb,1,control,7.62)
    return mos

def buck(p,y,uref,lref,cin,cout,rboot,cboot,cvcc,rhi,rlo,cff,out):
    x=86.36
    p.box(15,y-43.18,205,107.95,out+' / 5.10V / USB-C 3A target')
    u=p.sym('EdgeMind_Power:MP2236GJ-Z',uref,x,y,'MP2236GJ-Z','Package_TO_SOT_SMD:TSOT-23-8',mpn='MP2236GJ-Z')
    left=(35.56,u.pin(2)[1]);p.wire(left,u.pin(2));p.label('VLOGIC_IN',left,180)
    for i,ref in enumerate(cin):
        xx=38.1+i*12.7;cc=C(p,xx,y+2.54,'22uF 25V X5R',ref,fp=C8FP)
        p.wire(cc.pin(1),(xx,left[1]));p.dot((xx,left[1]));p.ground(cc.pin(2))
    p.stub(u,6,'BUCK_ENABLE',7.62)
    cc=C(p,35.56,y+31.75,'1uF 25V',cvcc,fp=C8FP)
    p.wire(u.pin(7),(43.18,u.pin(7)[1]),(43.18,cc.pin(1)[1]),cc.pin(1));p.ground(cc.pin(2))
    p.wire(u.pin(1),(u.pin(1)[0],y+25.4),(u.pin(4)[0],y+25.4),u.pin(4));p.ground((x,y+25.4));p.dot((x,y+25.4))
    ll=p.sym('Device:L',lref,132.08,u.pin(3)[1],'4.7uH FXL0630-4R7-M',INDUCTOR,angle=90,mpn='FXL0630-4R7-M')
    p.wire(u.pin(3),ll.pin(1));outpt=(205.74,u.pin(3)[1]);p.wire(ll.pin(2),outpt);p.flag(out,outpt)
    rr=R(p,127,y-31.75,'10R',rboot,a=90);cb=C(p,144.78,y-20.32,'100nF 50V',cboot)
    p.wire(u.pin(5),(109.22,u.pin(5)[1]),(109.22,y-31.75),rr.pin(1));p.wire(rr.pin(2),(144.78,y-31.75),cb.pin(1))
    p.wire(cb.pin(2),(144.78,y-12.7),(116.84,y-12.7),(116.84,u.pin(3)[1]));p.dot((116.84,u.pin(3)[1]))
    for i,ref in enumerate(cout):
        xx=193.04+i*12.7;cc=C(p,xx,y+20.32,'22uF 25V X5R',ref,fp=C8FP)
        p.wire(cc.pin(1),(xx,outpt[1]));p.dot((xx,outpt[1]));p.ground(cc.pin(2))
    rt=R(p,165.1,y+5.08,'82.5k 0.1%',rhi);rb=R(p,165.1,y+30.48,'11.0k 0.1%',rlo)
    mid=(165.1,y+17.78);p.wire(rt.pin(1),(165.1,outpt[1]));p.dot((165.1,outpt[1]))
    p.wire(rt.pin(2),mid,rb.pin(1));p.wire(u.pin(8),(149.86,u.pin(8)[1]),(149.86,mid[1]),mid);p.dot(mid);p.ground(rb.pin(2))
    cc=C(p,177.8,y+5.08,'220pF C0G',cff);p.wire(cc.pin(1),(177.8,outpt[1]));p.dot((177.8,outpt[1]));p.wire(cc.pin(2),(177.8,mid[1]),mid)

def usb_port(p,y,out,icref,usbref):
    p.box(230,y-43.18,165,107.95,usbref+' / 6P power-only / fixed 5V')
    u=p.sym('EdgeMind_Power:HUSB305_02',icref,279.4,y,'HUSB305-02','Package_TO_SOT_SMD:TSOT-23-8',mpn='HUSB305-02')
    vin=(243.84,u.pin(1)[1]);p.wire(vin,u.pin(1));p.flag(out+'_PROT',vin)
    ci=C(p,243.84,y+5.08,'1uF 25V',fp=C8FP);p.wire(ci.pin(1),vin);p.dot(vin);p.ground(ci.pin(2))
    rs=R(p,251.46,y+26.67,'150k 1%');p.wire(u.pin(3),(251.46,u.pin(3)[1]),rs.pin(1));p.ground(rs.pin(2));p.ground(u.pin(2));p.nc(u,4)
    con=p.sym('Connector:USB_C_Receptacle_PowerOnly_6P',usbref,360.68,y-15.24,'TYPE-C-31-M-17 / 6P',USB6,angle=180,mpn='TYPE-C-31-M-17',datasheet='https://omo-oss-file.thefastfile.com/portal-saas/new2023011311465142457/cms/file/134891b2-9b01-4104-89d3-96207243f692.pdf')
    p.wire(u.pin(8),con.pin('A9'));p.label(usbref+'_VBUS',(312.42,u.pin(8)[1]))
    for k,cp,xx in [(6,'A5',327.66),(5,'B5',335.28)]:
        p.wire(u.pin(k),(xx,u.pin(k)[1]),(xx,con.pin(cp)[1]),con.pin(cp))
    co=C(p,312.42,y+26.67,'4.7uF 10V X7R',fp=C8FP);p.wire(co.pin(1),(312.42,u.pin(8)[1]));p.dot((312.42,u.pin(8)[1]));p.ground(co.pin(2))
    p.ground(con.pin('A12'));p.ground(con.pin('SH'));p.stub(u,7,usbref+'_FAULT_PULSE_N',7.62)
    pull(p,347.98,y+36.83,usbref+'_FAULT_PULSE_N')
    p.text('CC attach detection + integrated VBUS switch\nISET 150k: 3.6A typ / Rp advertises 3A\nNo external Rp, USB data or PD voltage negotiation',235,y+56,0.95)

def build():
    assert hashlib.sha256((ROOT/(STEM+'.kicad_pcb')).read_bytes()).hexdigest()==EXPECTED_BOARD
    g.USED.clear();g.COMPONENTS.clear();g.COUNTS.update(R=50,C=100,U=20,J=8,D=1,Q=2,L=3,F=1,RV=0,TP=0)
    define_parts()
    root=Schematic(STEM+'.kicad_sch','EdgeMind Robot power / 2x5V + independent 3V3',1,'User')
    specs=[('01_power_input','3S input and voltage protection'),('02_usb_5v','Two MP2236 / 6P USB-C sources'),('03_aux_3v3','Independent 3V3 and source selector'),('04_motor_safety','E-stop and explicit arm latch'),('05_motor_left','Left AT8236 and current monitor'),('06_motor_right','Right AT8236 and current monitor'),('07_motor_dump','Regeneration dump'),('08_rail_protection','Low-cost output OV disconnect'),('09_control_io','FPGA control and monitor interfaces')]
    pages=[Schematic(f+'.kicad_sch',t,i+2,'User') for i,(f,t) in enumerate(specs)]
    power,usb,aux,safe,ml,mr,dump,prot,io=pages
    root.text('两路独立 5V + 默认独立 3.3V；USB-C 使用 6P 供电插座。',20,25,1.6)
    root.text('区内实线连接；跨模块标签。AT8236 使用两排排母；原 PCB 不更新。',20,35,1.3)
    root.text('3S protected battery -> fuse / reverse protection -> VBAT_SYS\nLogic switch -> VLOGIC_IN -> two 5V bucks + independent 3V3 buck\nMotor arm switch -> branch fuses / shunts -> VM_L / VM_R\nJP1: 1-2 ONBOARD (default); 2-3 FPGA IN (optional, confirm current headroom)',20,50,1.1)
    for i,page in enumerate(pages):
        xx=20+(i%3)*128;yy=89+(i//3)*57
        root.items.append(f'(sheet (at {xx} {yy}) (size 116 32) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid("sheet:"+page.file))}) (property "Sheetname" {q(page.title)} (at {xx} {yy-1.27} 0) {effects(0.95,justify="left")}) (property "Sheetfile" {q(page.file)} (at {xx} {yy+34} 0) {effects(0.9,justify="left")}) (instances (project {q(STEM)} (path {q("/"+ROOT_ID)} (page {q(page.index)})))))')
    root.text('Schematic R2 / PCB intentionally unchanged. Bench validation required before fabrication.\nExternal 3S cell protection required. Stepper drivers and FPGA RTL are separate system work.',20,270,1.05)

    # Raw input chain: detailed stock XT60, fuse holder, reverse-source PMOS.
    p=power;p.box(15,15,380,94,'INPUT / 3S pack + external BMS / fuse + reverse polarity')
    con=hdr(p,30.48,54.61,2,'CN1','XT60PW-M / 3S','Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal',a=180)
    p.ground(con.pin(1));p.flag('GND',(con.pin(1)[0],con.pin(1)[1]+3.81))
    f=p.sym('Device:Fuse','F1',76.2,con.pin(2)[1],'10A 32VDC ATO (initial)','Fuse:Fuseholder_Blade_ATO_Littelfuse_Pudenz_2_Pin',angle=90)
    p.wire(con.pin(2),f.pin(1))
    rev=p.sym('Transistor_FET:Q_PMOS_GDS','Q1',111.76,66.04,'IRF4905',TO220,mpn='IRF4905',angle=90)
    p.wire(f.pin(2),(96.52,f.pin(2)[1]),(96.52,rev.pin(2)[1]),rev.pin(2))
    end=(187.96,rev.pin(3)[1]);p.wire(rev.pin(3),end);p.flag('VBAT_SYS',end)
    rg=R(p,111.76,85.09,'100k');p.wire(rev.pin(1),rg.pin(1));p.ground(rg.pin(2))
    z=p.sym('Device:D_Zener',None,139.7,80.01,'BZT52C12','Diode_SMD:D_SOD-123',angle=270)
    p.wire(z.pin(1),(139.7,end[1]));p.dot((139.7,end[1]));p.wire(z.pin(2),(124.46,z.pin(2)[1]),(124.46,76.2),(111.76,76.2));p.dot((111.76,76.2))
    p.wire(end,(end[0],50.8),(269.24,50.8))
    for xx,ref,v,polar in [(205.74,'C58','470uF 35V low-ESR',True),(226.06,'C59','10uF 50V',False),(246.38,'C60','100nF 50V',False)]:cap(p,xx,66.04,'VBAT_SYS',v,ref,polar,bus=(xx,50.8))
    tv=p.sym('Device:D_TVS','D1',269.24,66.04,'SMBJ15CA','Diode_SMD:D_SMB',angle=270,mpn='SMBJ15CA');p.wire(tv.pin(1),(269.24,50.8));p.ground(tv.pin(2))
    p.text('Q1: D=BAT input / S=VBAT_SYS\nTVS handles transients, not a 17V clamp.\nFuse rating must match copper and harness.',290,56,1.0)
    p.box(15,118,177,140,'RAW-BUS reference / logic input switch')
    tl=p.sym('Reference_Voltage:TL431DBZ',None,53.34,148.59,'TL431BIDBZR','Package_TO_SOT_SMD:SOT-23',angle=90,mpn='TL431BIDBZR')
    p.wire(tl.pin(2),(tl.pin(2)[0],tl.pin(1)[1]),tl.pin(1));p.dot(tl.pin(1));p.ground(tl.pin(3))
    rb=R(p,53.34,133.35,'2.2k');p.stub(rb,1,'VBAT_SYS',3.81);p.wire(rb.pin(2),tl.pin(1));p.label('VREF_2V495',tl.pin(1))
    pm_switch(p,129.54,162.56,'VBAT_SYS','VLOGIC_IN','BUCK_ENABLE',large=True)
    p.flag('VLOGIC_IN',(172.72,233.68));cap(p,157.48,241.3,'VLOGIC_IN','100uF 25V',polar=True)
    p.box(204,118,191,140,'UV / OV WINDOW: logic 9.0-14.1V, motor 9.65-14.1V')
    u=threshold(p,260.35,152.4,None,1,'VBAT_SYS','26.1k','10.0k','BUCK_ENABLE',True)
    threshold(p,350.52,152.4,u.ref,2,'VBAT_SYS','46.4k','10.0k','BUCK_ENABLE')
    cmp_power(p,u.ref,242.57,233.68)
    pull(p,276.86,222.25,'BUCK_ENABLE','10k',to='VBAT_SYS')
    u=threshold(p,260.35,204.47,None,1,'VBAT_SYS','28.7k','10.0k','MOTOR_POWER_OK',True)
    threshold(p,350.52,204.47,u.ref,2,'VBAT_SYS','46.4k','10.0k','MOTOR_POWER_OK')
    cmp_power(p,u.ref,310.515,241.3);pull(p,360.68,240.03,'MOTOR_POWER_OK')
    p.text('OC outputs wired-AND. Motor faults clear the arm latch; voltage recovery does not re-arm.\nTotal voltage monitoring does not replace cell protection. Validate threshold/overshoot on bench.',18,273,1.05)

    # Existing two buck values / references retained where practical; integrated cheaper source IC.
    buck(usb,72.39,'U5','L1',['C1','C2','C3'],['C4','C5'],'R1','C6','C11','R2','R3','C7','+5V_FPGA')
    usb_port(usb,72.39,'+5V_FPGA','U7','USB1')
    buck(usb,185.42,'U1','L2',['C8','C9','C10'],['C12','C13'],'R6','C14','C16','R11','R12','C15','+5V_AI')
    usb_port(usb,185.42,'+5V_AI','U8','USB2')
    usb.text('两路 5V 不并联。实际负载、板端电压、线缆压降和温升需实测；USB-C 不宣告 4A。',18,280,1.0)

    # Independent fixed 3V3 buck, populated by default; physically exclusive source jumper.
    p=aux;p.box(15,15,217,129,'DEFAULT: independent 3.3V buck / initial load budget 0.5A')
    u=p.sym('Regulator_Switching:AP63203WU','U3',93.98,67.31,'AP63203WU-7','Package_TO_SOT_SMD:TSOT-23-6',mpn='AP63203WU-7')
    v=(45.72,u.pin(3)[1]);p.wire(v,u.pin(3));p.label('VLOGIC_IN',v,180)
    ci=C(p,45.72,83.82,'10uF 25V',fp=C8FP);p.wire(ci.pin(1),v);p.dot(v);p.ground(ci.pin(2))
    p.stub(u,2,'BUCK_ENABLE',7.62);p.ground(u.pin(4))
    ll=p.sym('Device:L','L3',146.05,u.pin(5)[1],'4.7uH FXL0630-4R7-M',INDUCTOR,angle=90,mpn='FXL0630-4R7-M');p.wire(u.pin(5),ll.pin(1))
    out=(207.01,ll.pin(2)[1]);p.wire(ll.pin(2),out);p.flag('+3V3_RAW',out)
    bs=C(p,124.46,87.63,'100nF 50V');p.wire(u.pin(6),(116.84,u.pin(6)[1]),(116.84,bs.pin(2)[1]),bs.pin(2));p.wire(bs.pin(1),(124.46,u.pin(5)[1]));p.dot((124.46,u.pin(5)[1]))
    for xx in [177.8,198.12]:
        co=C(p,xx,85.09,'22uF 10V X7R',fp=C8FP);p.wire(co.pin(1),(xx,out[1]));p.dot((xx,out[1]));p.ground(co.pin(2))
    p.wire(u.pin(1),(161.29,u.pin(1)[1]),(161.29,out[1]));p.dot((161.29,out[1]))
    p.text('2A IC capacity does not define connector/load budget.\nFeedback senses the buck output before protection.\n4.7uH matches the allowed 2.2-10uH range.',22,121,1.0)
    p.box(244,15,151,129,'JP1: one shunt only / source selection')
    j=hdr(p,294.64,49.53,3,'JP1','1-2 ONBOARD / 2-3 FPGA',nets=['+3V3_ONBOARD','+3V3','3V3_FPGA_IN'])
    p.flag('+3V3',(309.88,49.53));p.flag('3V3_FPGA_IN',(309.88,72.39))
    hdr(p,375.92,93.98,2,None,'OPTIONAL FPGA 3V3 IN',nets=['3V3_FPGA_IN','GND'])
    p.text('Default shunt 1-2: onboard 3V3.\n2-3 only after verifying FPGA headroom.\nNever fit two shunts. No hard paralleling.\nOnboard buck remains populated by default.',250,116,1.0)
    p.box(15,153,380,106,'FILTERED SENSOR POWER / finished 3.3V-compatible modules only')
    bead=p.sym('Device:FerriteBead',None,55.88,179.07,'220R@100MHz 1A','Inductor_SMD:L_0805_2012Metric',angle=90)
    p.stub(bead,1,'+3V3',7.62);end=(111.76,179.07);p.wire(bead.pin(2),end);p.label('+3V3_SENS',end)
    for xx,value in [(86.36,'10uF 10V X7R'),(105.41,'100nF 50V')]:cap(p,xx,194.31,'+3V3_SENS',value,bus=(xx,179.07))
    for i,name in enumerate(['IMU PWR','TOF1 PWR','TOF2 PWR','TOF3 PWR']):
        xx=185.42+(i%2)*123.19;yy=185.42+(i//2)*49.53
        h=hdr(p,xx,yy,2,None,name,'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',nets=['+3V3_SENS','GND']);decouple(p,xx+43.18,yy,'+3V3_SENS')
    hdr(p,104.14,238.76,2,None,'3V3 AUX OUT',TERM,nets=['+3V3','GND'])
    p.text('Default +3V3 powers encoders, current monitors and safety logic. Sensor signals connect to FPGA.\nBare sensor chips and finished modules may need different supply levels; confirm actual modules.',18,276,1.0)

    # Four physical AND gates + asynchronous-clear FF: wired local chain.
    p=safe;p.box(15,15,380,251,'MOTOR HARDWARE LATCH: power-on OFF / NC E-stop / explicit ARM rising edge')
    est=hdr(p,50.8,52.07,2,None,'ESTOP NC LOOP',TERM,nets=['+3V3','ESTOP_OK']);down(p,83.82,64.77,'ESTOP_OK')
    down(p,40.64,93.98,'MOTOR_PERMIT');down(p,71.12,93.98,'MOTOR_ARM');pull(p,102.87,64.77,'EXT_KILL_N')
    rst=p.sym('Power_Supervisor:MCP100-300D','U13',157.48,54.61,'MCP100-300DI/TO','Package_TO_SOT_THT:TO-92_Inline',mpn='MCP100-300DI/TO')
    p.stub(rst,2,'+3V3',3.81);p.ground(rst.pin(3));p.stub(rst,1,'POR_OK',7.62);decouple(p,179.07,87.63)
    def ga(unit,x,y,an,bn):
        c=p.sym('EdgeMind_Power:74HC08','U10',x,y,'74HC08D',SO14,unit=unit,mpn='SN74HC08DR')
        aa,bb,oo={1:(1,2,3),2:(4,5,6),3:(9,10,8),4:(12,13,11)}[unit]
        if an:p.stub(c,aa,an,7.62)
        if bn:p.stub(c,bb,bn,7.62)
        return c,aa,bb,oo
    a,ai,aj,ao=ga(1,243.84,63.5,'ESTOP_OK','MOTOR_PERMIT')
    b,bi,bj,bo=ga(2,243.84,104.14,'POR_OK','EXT_KILL_N')
    c,ci,cj,co=ga(3,307.34,83.82,None,None)
    p.wire(a.pin(ao),(274.32,a.pin(ao)[1]),(274.32,c.pin(ci)[1]),c.pin(ci));p.wire(b.pin(bo),(281.94,b.pin(bo)[1]),(281.94,c.pin(cj)[1]),c.pin(cj))
    d,di,dj,do=ga(4,243.84,144.78,None,'MOTOR_POWER_OK')
    p.wire(c.pin(co),(332.74,c.pin(co)[1]),(332.74,125.73),(218.44,125.73),(218.44,d.pin(di)[1]),d.pin(di))
    ff=p.sym('74xx:74HC74','U12',320.04,180.34,'74HC74D',SO14,unit=1,mpn='SN74HC74DR')
    p.wire(d.pin(do),(294.64,d.pin(do)[1]),(294.64,ff.pin(1)[1]),ff.pin(1))
    p.stub(ff,2,'+3V3',5.08);p.stub(ff,3,'MOTOR_ARM',7.62);p.stub(ff,4,'+3V3',5.08);p.stub(ff,5,'MOTOR_ARMED',7.62);p.nc(ff,6)
    ffu=p.sym('74xx:74HC74','U12',172.72,185.42,'74HC74D',SO14,unit=2,mpn='SN74HC74DR')
    for k in [11,12,13]:p.stub(ffu,k,'GND',3.81)
    p.stub(ffu,10,'+3V3',3.81);p.nc(ffu,8);p.nc(ffu,9)
    for lib,ref,unit,x in [('EdgeMind_Power:74HC08','U10',5,53.34),('74xx:74HC74','U12',3,116.84)]:
        u=p.sym(lib,ref,x,223.52,'74HC08D' if ref=='U10' else '74HC74D',SO14,unit=unit,mpn='SN74HC08DR' if ref=='U10' else 'SN74HC74DR');p.stub(u,14,'+3V3',3.81);p.ground(u.pin(7));decouple(p,x+20.32,233.68)
    down(p,369.57,219.71,'MOTOR_ARMED','4.7k')
    p.text('Open E-stop / low PERMIT / external KILL / undervoltage / overcurrent clears immediately.\nRestore conditions then pulse ARM: no automatic restart. FPGA must drop PERMIT on watchdog/stall.\nHC08/HC74 are CMOS parts running at 3.3V. Do not substitute 74LS parts.',18,278,1.0)

    # Common motor high-side switch. Small E-stop carries only logic current.
    p=dump;p.box(15,15,170,131,'MOTOR POWER SWITCH / not a small slider in the motor path')
    pm_switch(p,106.68,58.42,'VBAT_SYS','VM_SWITCHED','MOTOR_ARMED','Q2',large=True)
    p.flag('VM_SWITCHED',(43.18,119.38));tp(p,159,119.38,'VM_SWITCHED')
    p.box(200,15,195,244,'REGEN DUMP / external chassis resistors')
    br=None
    for i,side in enumerate(['L','R']):
        yy=63.5+i*104.14
        cmp=p.sym('Comparator:LM393',br,264.16,yy,'LM393BIDR',SO8,unit=i+1,mpn='LM393BIDR');br=cmp.ref
        cp,cn,co=(3,2,1) if i==0 else (5,6,7)
        rt=R(p,224.79,yy-13.97,'51.1k 0.1%');rb=R(p,224.79,yy+11.43,'10.0k 0.1%');m=(224.79,yy-2.54)
        p.stub(rt,1,'VM_'+side,3.81);p.wire(rt.pin(2),m,rb.pin(1));p.ground(rb.pin(2));p.wire(m,cmp.pin(cp));p.dot(m);p.stub(cmp,cn,'VREF_2V495',5.08)
        gate=(302.26,yy);p.wire(cmp.pin(co),gate)
        rg=R(p,302.26,yy-17.78,'4.7k');p.stub(rg,1,'VM_'+side,3.81);p.wire(rg.pin(2),gate);p.dot(gate)
        mos=p.sym('Transistor_FET:Q_NMOS_GDS',None,332.74,yy,'IRLZ44N',TO220,mpn='IRLZ44N');p.wire(gate,mos.pin(1));p.ground(mos.pin(3))
        z=p.sym('Device:D_Zener',None,312.42,yy+20.32,'BZT52C12','Diode_SMD:D_SOD-123',angle=270);p.wire(z.pin(1),(312.42,yy));p.dot((312.42,yy));p.ground(z.pin(2))
        rh=R(p,264.16,yy+33.02,'1M',a=90);p.wire(rh.pin(1),(224.79,yy+33.02),rb.pin(1));p.dot(rb.pin(1));p.wire(rh.pin(2),(289.56,yy+33.02),(289.56,yy),gate);p.dot((289.56,yy))
        conn=hdr(p,386.08,yy-15.24,2,None,side+' DUMP / external 3R3',TERM)
        p.stub(conn,1,'VM_'+side,5.08);p.wire(conn.pin(2),(mos.pin(2)[0],conn.pin(2)[1]),mos.pin(2))
    cmp_power(p,br,243.84,239.395)
    p.text('Dump turns ON ~15.39V; verify OFF threshold and worst-case overshoot.\nUse two 3.3ohm >=100W chassis resistors if the supply/BMS cannot absorb regen.\nCircuit operates from raw bus even when local 3V3 is absent. MOSFET cooling required.',18,277,1.0)

    # Motor modules: correct opposing row order, old row pitch retained.
    for i,(p,side,modref,row,jref) in enumerate([(ml,'L','U2',23.0005,'J3'),(mr,'R','U4',23.1275,'J4')]):
        p.box(15,15,380,99,side+' MOTOR / branch fuse / bus current monitor / local bulk')
        f=p.sym('Device:Fuse',None,45.72,50.8,'3.15A slow 5x20 (initial)',FUSE,angle=90);p.stub(f,1,'VM_SWITCHED',7.62)
        sh=p.sym('Device:R',None,106.68,50.8,'0.020R 1% 1W','Resistor_SMD:R_2512_6332Metric',angle=90)
        p.wire(f.pin(2),sh.pin(1));bus=(167.64,50.8);p.wire(sh.pin(2),bus,(254,50.8));p.flag('VM_'+side,(254,50.8))
        for xx,value,polar in [(226.06,'470uF 25V low-ESR',True),(246.38,'100nF 50V',False)]:cap(p,xx,73.66,'VM_'+side,value,polar=polar,bus=(xx,50.8))
        mon=p.sym('Amplifier_Current:INA180A1',None,157.48,81.28,'INA180A1IDBVR',SOT5,mpn='INA180A1IDBVR')
        p.wire(sh.pin(1),(86.36,50.8),(86.36,mon.pin(3)[1]),mon.pin(3));p.dot((86.36,50.8))
        p.wire(sh.pin(2),(121.92,50.8),(121.92,mon.pin(4)[1]),mon.pin(4));p.dot((121.92,50.8))
        p.stub(mon,5,'+3V3',3.81);p.ground(mon.pin(2));decouple(p,195.58,102.87)
        ri=R(p,194.31,81.28,'1k',a=90);p.wire(mon.pin(1),ri.pin(1));target=(209.55,81.28);p.wire(ri.pin(2),target);p.label('VM_'+side+'_IMON',target)
        cf=C(p,209.55,96.52,'1uF 25V');p.wire(cf.pin(1),target);p.dot(target);p.ground(cf.pin(2))
        p.text('Gain 20 / shunt 20mohm -> 0.4V/A\n1ms output filter; bus current != winding current\nFault threshold ~3.04A bus, needs bench setting',280,75,1.0)
        p.box(15,122,380,139,side+' AT8236 / A channel / VREF adjustable / female sockets')
        at=p.sym('EdgeMind_Power:AT8236_Dual_Module',modref,220.98,189.23,'AT8236 dual module',module_fp(row),mpn='AT8236 dual module / vendor-specific')
        p.stub(at,6,'VM_'+side,7.62);p.ground(at.pin(7))
        rv=p.sym('Device:R_Potentiometer',None,132.08,147.32,'10k 3296W / VREF','Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical',mpn='3296W-1-103LF')
        p.stub(rv,1,'+3V3_SENS',3.81);p.ground(rv.pin(3));rs=R(p,157.48,147.32,'1k',a=90);p.wire(rv.pin(2),rs.pin(1))
        vref=(181.61,147.32);p.wire(rs.pin(2),vref,(at.pin(5)[0],147.32),at.pin(5));p.label('VREF_'+side,vref)
        for xx,value,typ in [(181.61,'100k','R'),(199.39,'1uF 25V','C')]:
            c=R(p,xx,162.56,value) if typ=='R' else C(p,xx,162.56,value);p.wire(c.pin(1),(xx,147.32));p.dot((xx,147.32));p.ground(c.pin(2))
        for k in [5]:p.dot((at.pin(k)[0],147.32))
        for j,k in enumerate([12,11]):
            unit=1+i*2+j;gy=189.23+j*25.4
            gate=p.sym('EdgeMind_Power:74HC08','U11',111.76,gy,'74HC08D',SO14,unit=unit,mpn='SN74HC08DR')
            aa,bb,oo={1:(1,2,3),2:(4,5,6),3:(9,10,8),4:(12,13,11)}[unit]
            p.stub(gate,aa,side+'_PWM_'+('FWD_RAW' if j==0 else 'REV_RAW'),7.62);p.stub(gate,bb,'MOTOR_ARMED',7.62)
            xx=165.1+j*12.7;p.wire(gate.pin(oo),(xx,gy),(xx,at.pin(k)[1]),at.pin(k))
            rd=R(p,xx,gy+13.97,'10k');p.wire(rd.pin(1),(xx,at.pin(k)[1]));p.dot((xx,at.pin(k)[1]));p.ground(rd.pin(2))
        if i==0:
            pp=p.sym('EdgeMind_Power:74HC08','U11',48.26,154.94,'74HC08D',SO14,unit=5,mpn='SN74HC08DR');p.stub(pp,14,'+3V3',3.81);p.ground(pp.pin(7));decouple(p,67.31,161.29)
        p.wire(at.pin(3),(200.66,at.pin(3)[1]),(200.66,at.pin(4)[1]),at.pin(4));p.ground((200.66,at.pin(4)[1]));p.dot((200.66,at.pin(4)[1]));p.nc(at,13);p.nc(at,14)
        mot=hdr(p,292.1,191.77,6,jref,'MG513 / verify harness','Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical')
        p.wire(at.pin(1),(264.16,at.pin(1)[1]),(264.16,mot.pin(1)[1]),mot.pin(1));p.wire(at.pin(2),(256.54,at.pin(2)[1]),(256.54,mot.pin(6)[1]),mot.pin(6))
        for k,net in [(2,'+3V3'),(3,'ENC_'+side+'_A'),(4,'ENC_'+side+'_B'),(5,'GND')]:p.stub(mot,k,net,5.08)
        for j,ch in enumerate(['A','B']):
            yy=238.76;xx=55.88+j*109.22;renc=R(p,xx,yy,'100R',a=90);p.stub(renc,1,'ENC_'+side+'_'+ch,3.81)
            n=(xx+12.7,yy);p.wire(renc.pin(2),n);p.label('ENC_'+side+'_'+ch+'_FPGA',n)
            cc=C(p,xx+12.7,yy+12.7,'1nF C0G');p.wire(cc.pin(1),n);p.dot(n);p.ground(cc.pin(2))
            rp=R(p,xx+35.56,yy-12.7,'10k');p.stub(rp,1,'+3V3',3.81);p.wire(rp.pin(2),(rp.pin(2)[0],yy),n)
        decouple(p,342.9,187.96)
        p.text(f'ROW={row:.4f}mm, from existing PCB. Opposing row numbering corrected.\nItrip=VREF/(10 x Rsense); measure module Rsense and calibrate before fitting motors.\n10=FWD / 01=REV / 00=coast / 11=brake. B unused. Encoder type/pinout must match harness.',18,279,1.0)

    # Output OV monitors drive discrete disconnects; no premium eFuses.
    p=prot
    for i,(source,target,top) in enumerate([('+5V_FPGA','+5V_FPGA_PROT','11.5k'),('+5V_AI','+5V_AI_PROT','11.5k')]):
        xx=15+i*194.31;p.box(xx,15,184,117,'5V OV cutoff ~5.364V / '+target)
        u=threshold(p,xx+63.5,60.96,None,1,source,top,'10.0k',source+'_OK')
        pu=p.sym('Comparator:LM393',u.ref,xx+63.5,108,'LM393BIDR',SO8,unit=2,mpn='LM393BIDR');p.stub(pu,5,'GND',3.81);p.stub(pu,6,'VREF_2V495',3.81);p.nc(pu,7)
        cmp_power(p,u.ref,xx+109.22,109.22);pull(p,xx+20.32,109.22,source+'_OK','10k',to='VBAT_SYS')
        pm_switch(p,xx+154.94,45.72,source,target,source+'_OK')
    p.box(15,142,183,116,'3V3 onboard OV cutoff ~3.451V')
    u=threshold(p,78.74,184.15,None,1,'+3V3_RAW','3.83k','10.0k','3V3_ONBOARD_OK')
    # 3V3-compatible low-threshold PMOS, source=2 drain=3, gate=1.
    q3=p.sym('Transistor_FET:AO3401A',None,160.02,167.64,'AO3401A','Package_TO_SOT_SMD:SOT-23',angle=270,mpn='AO3401A')
    p.stub(q3,2,'+3V3_RAW',5.08);p.stub(q3,3,'+3V3_ONBOARD',5.08)
    gate=q3.pin(1);rr=R(p,160.02,189.23,'1k');p.wire(gate,rr.pin(1));p.stub(rr,2,'+3V3_RAW',5.08)
    # Gate is pulled low in the good state by a common NPN.
    tr=p.sym('Transistor_BJT:MMBT3904',None,139.7,219.71,'MMBT3904','Package_TO_SOT_SMD:SOT-23',mpn='MMBT3904');p.wire(gate,(142.24,gate[1]),tr.pin(3));p.ground(tr.pin(2))
    rb=R(p,111.76,219.71,'4.7k',a=90);p.wire(rb.pin(2),tr.pin(1));p.stub(rb,1,'3V3_ONBOARD_OK',5.08);pull(p,88.9,239.395,'3V3_ONBOARD_OK','10k',to='VBAT_SYS')
    cmp_power(p,u.ref,34.29,239.395)
    # Spare half: battery low warning ~10.2V.
    warning=threshold(p,281.94,170.18,u.ref,2,'VBAT_SYS','30.9k','10.0k','BAT_WARN_N',True);pull(p,318.77,147.32,'BAT_WARN_N')
    p.box(208,188,186,71,'MOTOR overcurrent / filtered bus current / common latch clear')
    oc=None
    for i,side in enumerate(['L','R']):
        yy=216.535+i*29.21;cc=p.sym('Comparator:LM393',oc,281.94,yy,'LM393BIDR',SO8,unit=i+1,mpn='LM393BIDR');oc=cc.ref
        cp,cn,co=(3,2,1) if i==0 else (5,6,7)
        p.stub(cc,cp,'CURRENT_REF_1V217',7.62);p.stub(cc,cn,'VM_'+side+'_IMON',7.62);p.stub(cc,co,'MOTOR_POWER_OK',7.62)
    cmp_power(p,oc,355.6,230.505)
    rh=R(p,226.06,215.9,'10.5k 0.1%');rl=R(p,226.06,241.3,'10.0k 0.1%');p.stub(rh,1,'VREF_2V495',3.81);p.wire(rh.pin(2),rl.pin(1));p.label('CURRENT_REF_1V217',(226.06,228.6));p.dot((226.06,228.6));p.ground(rl.pin(2))
    p.text('Discrete OV disconnects are cost-oriented. Verify fault-step overshoot and thermal behavior.\nNo claim of true reverse-current blocking: use supply selection/isolation on attached boards.\nMotor bus current threshold ~3.04A plus tolerance; fuse is harness protection, not winding limit.',18,276,1.0)

    p=io;p.box(15,15,380,241,'CONTROL / power direction / explicit source selection')
    hdr(p,160.02,63.5,8,'J1','LEFT CTRL',nets=['L_PWM_FWD_RAW','L_PWM_REV_RAW','MOTOR_ARM','MOTOR_PERMIT','GND','3V3_FPGA_IN','ENC_L_A_FPGA','ENC_L_B_FPGA'])
    hdr(p,345.44,63.5,8,'J2','RIGHT CTRL',nets=['ENC_R_B_FPGA','ENC_R_A_FPGA','3V3_FPGA_IN','GND','R_PWM_FWD_RAW','R_PWM_REV_RAW','EXT_KILL_N','MOTOR_ARMED'])
    hdr(p,160.02,172.72,12,None,'POWER MONITOR / external ADC',nets=['+3V3','GND','BAT_ADC','BAT_WARN_N','VM_L_IMON','VM_R_IMON','MOTOR_POWER_OK','MOTOR_ARMED','USB1_FAULT_PULSE_N','USB2_FAULT_PULSE_N','ESTOP_OK','POR_OK'])
    # ADC battery divider with local filter.
    rt=R(p,245.11,177.8,'100k 0.1%');rb=R(p,245.11,203.2,'27.4k 0.1%');p.stub(rt,1,'VBAT_SYS',3.81);p.wire(rt.pin(2),rb.pin(1));n=(245.11,190.5);p.label('BAT_ADC',n);p.dot(n);p.ground(rb.pin(2))
    cc=C(p,266.7,203.2,'100nF 25V');p.wire(cc.pin(1),(266.7,190.5),n);p.ground(cc.pin(2))
    p.text('BAT_ADC: 12.6V -> 2.71V; requires external ADC.\nJ1.6 and J2.3 = same FPGA 3V3 INPUT,\nnot local 3V3 OUTPUT. JP1 isolates by default.\nOnly connect one FPGA supply domain.\nPERMIT low during reset / watchdog timeout.\nARM rising edge after safety checks.\nKILL_N accepts external open-drain fault.\nLichee Pi GPIO needs appropriate level translation.',294.64,182.88,1.0)
    p.text('Do not fabricate the existing PCB using this schematic. Synchronization/layout is separate work.\nAT8236 Rsense / encoder variant / ACG720 Type-C supply path remain hardware verification items.',18,276,1.0)

    for page in [root]+pages:page.finish()
    (ROOT/'EdgeMind_Power.kicad_sym').write_text('(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor")\n'+'\n'.join(g.CUSTOM.values())+'\n)\n',encoding='utf-8')
    (ROOT/'review'/'redesign-components.json').write_text(json.dumps(g.COMPONENTS,ensure_ascii=False,indent=2),encoding='utf-8')
    assert hashlib.sha256((ROOT/(STEM+'.kicad_pcb')).read_bytes()).hexdigest()==EXPECTED_BOARD
    print('Generated',len(pages)+1,'native sheets; PCB SHA256 unchanged:',EXPECTED_BOARD)

if __name__=='__main__':build()
