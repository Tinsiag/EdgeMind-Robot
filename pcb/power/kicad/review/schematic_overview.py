"""Native hierarchy: real sheet pins and wires, preserving existing global nets."""
import re
from kicad_tools import parse,children,child
from redesign_schematic import q,uid,effects,num

def build_overview(root,pages):
    byfile={p.file.split('.')[0]:p for p in pages}
    root.items=[];root.wires.clear();root.junctions.clear()
    root.text('电源板功能连接总图：两路5V、独立3.3V与双电机驱动',20,18,1.8)
    root.text('实线为实际层级网络连接；远距离控制、监测信号采用同名标签。',20,27,1.1)
    configs=[
      ('01_power_input',20.32,40.64,90.17,74.93,'板载总保险、防反接与电压窗口',[
       ('VLOGIC_IN','降压输入','R',52.07),('BUCK_ENABLE','使能','R',66.04),('VBAT_SYS','电池母线','B',43.18),('MOTOR_POWER_OK','动力正常','B',90.17)]),
      ('02_usb_5v',154.94,40.64,90.17,74.93,'两路降压与六针供电口',[
       ('VLOGIC_IN','降压输入','L',52.07),('BUCK_ENABLE','使能','L',66.04),
       ('+5V_FPGA','逻辑5V','R',52.07),('+5V_AI','计算5V','R',66.04),
       ('+5V_FPGA_PROT','逻辑5V保护','R',80.01),('+5V_AI_PROT','计算5V保护','R',93.98)]),
      ('08_rail_protection',289.56,40.64,90.17,74.93,'输出过压与动力过流检测',[
       ('+5V_FPGA','逻辑5V','L',52.07),('+5V_AI','计算5V','L',66.04),
       ('+5V_FPGA_PROT','逻辑5V保护','L',80.01),('+5V_AI_PROT','计算5V保护','L',93.98),
       ('+3V3_RAW','板载3.3V','B',309.88),('+3V3_ONBOARD','保护后3.3V','B',347.98)]),
      ('03_aux_3v3',20.32,149.86,90.17,64.77,'独立降压、跳帽选择与传感器滤波',[
       ('VLOGIC_IN','降压输入','T',50.8),('BUCK_ENABLE','使能','T',100.33),
       ('+3V3_RAW','板载3.3V','R',158.75),('+3V3_ONBOARD','保护后3.3V','R',171.45),
       ('+3V3','本板3.3V','R',184.15),('+3V3_SENS','传感器电源','B',76.2)]),
      ('04_motor_safety',154.94,149.86,90.17,64.77,'急停、上电复位与解锁锁存',[
       ('+3V3','本板3.3V','L',184.15),('MOTOR_POWER_OK','动力正常','L',158.75),
       ('MOTOR_ARM','解锁脉冲','R',158.75),('MOTOR_PERMIT','运行许可','R',171.45),
       ('EXT_KILL_N','外部故障','R',184.15),('MOTOR_ARMED','已解锁','B',190.5)]),
      ('09_control_io',289.56,149.86,90.17,64.77,'逻辑板控制与电源监测接口',[
       ('MOTOR_ARM','解锁脉冲','L',158.75),('MOTOR_PERMIT','运行许可','L',171.45),
       ('EXT_KILL_N','外部故障','L',184.15),('MOTOR_ARMED','已解锁','L',196.85),
       ('L_PWM_FWD_RAW','左正转','B',299.72),('L_PWM_REV_RAW','左反转','B',320.04),
       ('R_PWM_FWD_RAW','右正转','B',340.36),('R_PWM_REV_RAW','右反转','B',360.68)]),
      ('07_motor_dump',20.32,250.19,90.17,48.26,'动力总开关与回生泄放',[
       ('VBAT_SYS','电池母线','T',43.18),('MOTOR_ARMED','已解锁','T',90.17),('VM_SWITCHED','电机总电源','R',264.16)]),
      ('05_motor_left',154.94,250.19,90.17,48.26,'左侧AT8236、编码器与电流监测',[
       ('VM_SWITCHED','电机总电源','L',264.16),('+3V3','本板3.3V','T',168.91),
       ('MOTOR_ARMED','已解锁','T',190.5),('+3V3_SENS','传感器电源','T',222.25),
       ('L_PWM_FWD_RAW','正转脉宽','L',278.13),('L_PWM_REV_RAW','反转脉宽','L',290.83)]),
      ('06_motor_right',289.56,250.19,90.17,48.26,'右侧AT8236、编码器与电流监测',[
       ('VM_SWITCHED','电机总电源','L',264.16),('+3V3','本板3.3V','T',303.53),
       ('MOTOR_ARMED','已解锁','T',325.12),('+3V3_SENS','传感器电源','T',356.87),
       ('R_PWM_FWD_RAW','正转脉宽','L',278.13),('R_PWM_REV_RAW','反转脉宽','L',290.83)]),
    ]
    ports={};sheetrows=[]
    for file,x,y,w,h,description,pins in configs:
        p=byfile[file];pinitems=[]
        for net,alias,side,offset in pins:
            # Promote one real child net attachment to a hierarchy port.
            prefix='(global_label '+q(net)+' '
            index=next(i for i,v in enumerate(p.items) if v.startswith(prefix))
            item=p.items[index];node=parse(item);property_nodes=children(node,'property')
            for n in sorted(property_nodes,key=lambda n:n.start,reverse=True):item=item[:n.start]+item[n.end:]
            item=item.replace(prefix,'(hierarchical_label '+q(alias)+' ',1)
            p.items[index]=item
            point={'L':(x,offset),'R':(x+w,offset),'T':(offset,y),'B':(offset,y+h)}[side]
            angle={'L':180,'R':0,'T':90,'B':270}[side]
            ports[file,net]=(point,side)
            pinitems.append(f'(pin {q(alias)} passive (at {num(point[0])} {num(point[1])} {angle}) {effects(0.85)} (uuid {q(uid(file+":overview:"+net))}))')
        root.items.append(f'(sheet (at {num(x)} {num(y)}) (size {num(w)} {num(h)}) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(uid("sheet:"+p.file))}) (property "Sheetname" {q(p.title)} (at {num(x)} {num(y-1.27)} 0) {effects(0.95,justify="left")}) (property "Sheetfile" {q(p.file)} (at {num(x)} {num(y+h+2.54)} 0) {effects(0.7,hide=True)}) '+''.join(pinitems)+f' (instances (project {q(root.file.split(".")[0])} (path {q("/"+root.id)} (page {q(p.index)})))))')
        root.text(description,x+4,y+h-8.89,0.95)
        sheetrows.append({'sheet':p.file,'ports':len(pins)})
    connected=set();names={}
    def path(net,*keys,via=()):
        ps=[ports[k,net][0] for k in keys];root.wire(ps[0],*via,ps[-1]);connected.update((k,net) for k in keys)
        anchor=ps[0];end=(anchor[0]+7.62,anchor[1])
        if anchor[0]!=ps[-1][0] and anchor[1]==ps[-1][1]:
            end=(anchor[0]+7.62,anchor[1])
        else:end=via[0] if via else anchor
        if net not in names:root.label(net,end);names[net]=end
    path('VLOGIC_IN','01_power_input','02_usb_5v')
    root.wire((133.35,52.07),(133.35,133.35),(50.8,133.35),ports['03_aux_3v3','VLOGIC_IN'][0]);root.dot((133.35,52.07));connected.add(('03_aux_3v3','VLOGIC_IN'))
    path('BUCK_ENABLE','01_power_input','02_usb_5v')
    for net in ['+5V_FPGA','+5V_AI','+5V_FPGA_PROT','+5V_AI_PROT']:path(net,'02_usb_5v','08_rail_protection')
    path('+3V3','03_aux_3v3','04_motor_safety')
    for net in ['MOTOR_ARM','MOTOR_PERMIT','EXT_KILL_N']:path(net,'04_motor_safety','09_control_io')
    path('VBAT_SYS','01_power_input','07_motor_dump',via=((43.18,123.19),(12.7,123.19),(12.7,238.76),(43.18,238.76)))
    path('MOTOR_ARMED','04_motor_safety','07_motor_dump',via=((190.5,231.14),(90.17,231.14)))
    path('VM_SWITCHED','07_motor_dump','05_motor_left')
    root.wire((133.35,264.16),(133.35,240.03),(266.7,240.03),(266.7,264.16),ports['06_motor_right','VM_SWITCHED'][0]);root.dot((133.35,264.16));connected.add(('06_motor_right','VM_SWITCHED'))
    for key,(point,side) in ports.items():
        if key in connected:continue
        net=key[1];dx,dy={'L':(-7.62,0),'R':(7.62,0),'T':(0,-5.08),'B':(0,5.08)}[side]
        end=(point[0]+dx,point[1]+dy);root.wire(point,end)
        root.label(net,end,180 if side=='L' else 0)
    root.text('默认短接JP1的1-2：板载3.3V。只安装一个跳帽；电机故障恢复后须重新发解锁脉冲。',20,316,1.05)
    root.text('电池经XT60接入板载MINI总保险；单体电芯保护仍须落实。PCB封装与网络已同步，布局布线待完成。',20,324,1.05)
    return sheetrows
